"""Acme's billing MCP server (official MCP Python SDK), in two configurations.

shortcut: what many MCP servers do. OAuth at the door with the SDK's defaults (the token's
          audience is not checked: `validate_token_resource` unset), no per-tool scope checks,
          and one service key from the server to the billing API behind it.
strict:   the token must be issued for this server (audience checked), each tool checks its
          scope, and the server calls the billing API *as the user*: it exchanges the user's token
          at the IdP (RFC 8693) for one issued for the billing API, with only the scope it needs.
"""
from __future__ import annotations

import warnings

import httpx
import jwt
from pydantic import AnyHttpUrl

from mcp.server import MCPServer
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver.exceptions import ToolError

from portal.data import ADMIN_KEY
from portal.idp import TOKEN_EXCHANGE, IdP

CLIENT_SECRET = "billing-mcp-secret"


class JwtVerifier(TokenVerifier):
    """Checks the signature, issuer and expiry, and reports the token's audience to the SDK."""

    def __init__(self, idp: IdP):
        self.idp = idp

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            claims = self.idp.decode(token)
        except jwt.PyJWTError:
            return None
        return AccessToken(token=token, client_id=claims.get("client_id", ""), scopes=claims["scope"].split(),
                           expires_at=claims["exp"], resource=claims["aud"], subject=claims["sub"], claims=claims)


def create_server(mode: str, url: str, idp: IdP, billing_url: str) -> MCPServer:
    strict = mode == "strict"
    settings = {"validate_token_resource": True} if strict else {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # the shortcut's "audience not checked" warning: that is the point
        server = MCPServer("Acme billing", token_verifier=JwtVerifier(idp),
                           auth=AuthSettings(issuer_url=AnyHttpUrl(idp.issuer), resource_server_url=AnyHttpUrl(url),
                                             **settings))

    async def call_billing(method: str, path: str, scope: str, **params):
        token = get_access_token()
        if strict:
            if scope not in token.scopes:
                raise ToolError(f"insufficient_scope: this tool needs {scope}")
            async with httpx.AsyncClient() as http:
                r = await http.post(f"{idp.base}/token", auth=("billing-mcp", CLIENT_SECRET), data={
                    "grant_type": TOKEN_EXCHANGE, "subject_token": token.token,
                    "subject_token_type": "urn:ietf:params:oauth:token-type:access_token",
                    "resource": billing_url, "scope": scope})
                if r.status_code != 200:
                    raise ToolError(f"token exchange refused: {r.text}")
                downstream = r.json()["access_token"]
        else:
            downstream = ADMIN_KEY
        async with httpx.AsyncClient() as http:
            r = await http.request(method, f"{billing_url}{path}", params=params or None,
                                   headers={"Authorization": f"Bearer {downstream}"})
        if r.status_code >= 400:
            raise ToolError(f"billing API said {r.status_code}: {r.text}")
        return r.json()

    @server.tool()
    async def get_customer(email: str) -> dict:
        """Get a customer's profile by email."""
        return await call_billing("GET", f"/api/customers/{email}", "profile:read")

    @server.tool()
    async def get_invoices(email: str) -> dict:
        """List a customer's invoices by email."""
        return await call_billing("GET", f"/api/customers/{email}/invoices", "invoices:read")

    @server.tool()
    async def refund_invoice(invoice_id: str, amount_usd: float) -> dict:
        """Refund an invoice to the customer's card."""
        return await call_billing("POST", f"/api/invoices/{invoice_id}/refund", "refunds:write", amount_usd=amount_usd)

    return server
