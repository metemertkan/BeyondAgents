"""Acme's identity provider: a small local OAuth 2.1 authorization server.

What it does, and only that:
- authorization code with PKCE (S256); the user "logs in" with an `X-Login-User` header,
  standing in for the login page
- resource indicators (RFC 8707): every token names the one server it is for, in `aud`
- token exchange (RFC 8693): a trusted service swaps a user's token for a new one, for another
  server, with fewer scopes; the new token keeps the user (`sub`) and names the service (`act`)
- RS256-signed JWT access tokens
"""
from __future__ import annotations

import base64
import hashlib
import secrets
import time
from dataclasses import dataclass, field
from urllib.parse import urlencode

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI, Form, Header, Request
from fastapi.responses import JSONResponse, RedirectResponse

from portal.data import USERS

TOKEN_EXCHANGE = "urn:ietf:params:oauth:grant-type:token-exchange"


@dataclass
class IdP:
    issuer: str
    resources: dict[str, set[str]] = field(default_factory=dict)     # resource URL -> scopes it understands
    clients: dict[str, dict] = field(default_factory=dict)            # client_id -> {redirect_uris, secret, exchange_from}
    key: rsa.RSAPrivateKey = field(default_factory=lambda: rsa.generate_private_key(public_exponent=65537, key_size=2048))
    codes: dict[str, dict] = field(default_factory=dict)
    issued: list[dict] = field(default_factory=list)

    @property
    def base(self) -> str:
        return self.issuer.rstrip("/")

    @property
    def public_key(self):
        return self.key.public_key()

    def mint(self, user: str, resource: str, scopes: list[str], client_id: str, act: str | None = None,
             lifetime: int = 600) -> str:
        """Sign an access token for one user and one resource."""
        u = USERS[user]
        now = int(time.time())
        claims = {"iss": self.issuer, "sub": u["sub"], "aud": resource, "scope": " ".join(scopes),
                  "role": u["role"], "name": u["name"], "client_id": client_id, "iat": now, "exp": now + lifetime,
                  "jti": secrets.token_hex(8)}
        if act:
            claims["act"] = {"sub": act}
        self.issued.append({"user": user, "aud": resource, "scope": claims["scope"], "act": act})
        return jwt.encode(claims, self.key, algorithm="RS256", headers={"kid": "acme-1"})

    def decode(self, token: str, audience: str | None = None) -> dict:
        """Verify a token this IdP signed. With `audience`, also check it was issued for that server."""
        options = {"verify_aud": audience is not None}
        return jwt.decode(token, self.public_key, algorithms=["RS256"], issuer=self.issuer, audience=audience,
                          options=options)

    def grant(self, user: str, resource: str, requested: list[str] | None) -> list[str]:
        """Scopes = what the user may have ∩ what the resource understands ∩ what was asked for."""
        allowed = set(USERS[user]["scopes"]) & self.resources.get(resource, set())
        if requested:
            allowed &= set(requested)
        return sorted(allowed)


def user_of(sub: str) -> str:
    return next(name for name, u in USERS.items() if u["sub"] == sub)


def create_app(idp: IdP) -> FastAPI:
    app = FastAPI(title="Acme IdP")

    @app.get("/.well-known/oauth-authorization-server")
    def metadata():
        return {"issuer": idp.issuer, "authorization_endpoint": f"{idp.base}/authorize",
                "token_endpoint": f"{idp.base}/token", "jwks_uri": f"{idp.base}/jwks",
                "response_types_supported": ["code"], "code_challenge_methods_supported": ["S256"],
                "grant_types_supported": ["authorization_code", TOKEN_EXCHANGE],
                "token_endpoint_auth_methods_supported": ["none", "client_secret_post", "client_secret_basic"],
                "authorization_response_iss_parameter_supported": True,
                "scopes_supported": sorted({s for scopes in idp.resources.values() for s in scopes})}

    @app.get("/jwks")
    def jwks():
        return {"keys": [{**jwt.algorithms.RSAAlgorithm.to_jwk(idp.public_key, as_dict=True), "kid": "acme-1",
                          "alg": "RS256", "use": "sig"}]}

    @app.get("/authorize")
    def authorize(client_id: str, redirect_uri: str, code_challenge: str, state: str = "",
                  code_challenge_method: str = "S256", scope: str = "", resource: str = "",
                  response_type: str = "code", x_login_user: str | None = Header(default=None)):
        client = idp.clients.get(client_id)
        if client is None or redirect_uri not in client["redirect_uris"]:
            return JSONResponse({"error": "invalid_client"}, status_code=400)
        if response_type != "code" or code_challenge_method != "S256" or x_login_user not in USERS:
            return JSONResponse({"error": "invalid_request"}, status_code=400)
        code = secrets.token_urlsafe(16)
        idp.codes[code] = {"user": x_login_user, "client_id": client_id, "redirect_uri": redirect_uri,
                           "challenge": code_challenge, "resource": resource, "scope": scope.split()}
        return RedirectResponse(f"{redirect_uri}?{urlencode({'code': code, 'state': state, 'iss': idp.issuer})}",
                                status_code=302)

    @app.post("/token")
    async def token(request: Request):
        form = dict(await request.form())
        client_id, secret = form.get("client_id"), form.get("client_secret")
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("basic "):
            client_id, _, secret = base64.b64decode(auth[6:]).decode().partition(":")
        client = idp.clients.get(client_id or "")
        if client is None or (client.get("secret") and secret != client["secret"]):
            return JSONResponse({"error": "invalid_client"}, status_code=401)

        if form.get("grant_type") == "authorization_code":
            entry = idp.codes.pop(form.get("code", ""), None)
            verifier = form.get("code_verifier", "")
            challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
            if not entry or entry["client_id"] != client_id or entry["redirect_uri"] != form.get("redirect_uri") \
                    or challenge != entry["challenge"]:
                return JSONResponse({"error": "invalid_grant"}, status_code=400)
            resource = form.get("resource") or entry["resource"]
            if resource not in idp.resources:
                return JSONResponse({"error": "invalid_target"}, status_code=400)
            scopes = idp.grant(entry["user"], resource, entry["scope"] or form.get("scope", "").split())
            return {"access_token": idp.mint(entry["user"], resource, scopes, client_id), "token_type": "Bearer",
                    "expires_in": 600, "scope": " ".join(scopes)}

        if form.get("grant_type") == TOKEN_EXCHANGE:
            try:
                subject = idp.decode(form.get("subject_token", ""))
            except jwt.PyJWTError:
                return JSONResponse({"error": "invalid_grant"}, status_code=400)
            # A service may only exchange tokens that were issued for it.
            if subject["aud"] not in client.get("exchange_from", []):
                return JSONResponse({"error": "invalid_grant", "error_description": "not your token"}, status_code=400)
            resource = form.get("resource", "")
            if resource not in idp.resources:
                return JSONResponse({"error": "invalid_target"}, status_code=400)
            user = user_of(subject["sub"])
            requested = form.get("scope", "").split() or subject["scope"].split()
            scopes = sorted(set(idp.grant(user, resource, requested)) & set(subject["scope"].split()))
            return {"access_token": idp.mint(user, resource, scopes, client_id, act=client_id, lifetime=120),
                    "issued_token_type": "urn:ietf:params:oauth:token-type:access_token", "token_type": "Bearer",
                    "expires_in": 120, "scope": " ".join(scopes)}

        return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)

    return app
