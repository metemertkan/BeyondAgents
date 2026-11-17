"""One run's world: Acme's IdP, billing API and billing MCP server, and Eve's FX4Free, all on localhost."""
from __future__ import annotations

from portal import billing as billing_mod
from portal import billing_mcp, eve as eve_mod, idp as idp_mod
from portal.servers import Served, free_port

BROKER_SECRET = "broker-secret"
PENNY_REDIRECT = "http://127.0.0.1:1/callback"   # never followed: the login is scripted
ALL_SCOPES = {"profile:read", "invoices:read", "refunds:write", "fx:convert"}
BILLING_SCOPES = {"profile:read", "invoices:read", "refunds:write"}


class World:
    def __init__(self, billing_mcp_mode: str = "shortcut"):
        ports = {name: free_port() for name in ("idp", "billing", "billing_mcp", "fx", "fx_mcp")}
        self.idp_url = f"http://127.0.0.1:{ports['idp']}"
        self.billing_url = f"http://127.0.0.1:{ports['billing']}"
        self.billing_mcp_url = f"http://127.0.0.1:{ports['billing_mcp']}/mcp"
        self.fx_url = f"http://127.0.0.1:{ports['fx']}"
        self.fx_mcp_url = f"http://127.0.0.1:{ports['fx_mcp']}/mcp"
        self.broker_url = "urn:acme:penny-broker"   # the broker's own audience; it serves no HTTP here

        self.idp = idp_mod.IdP(issuer=self.idp_url + "/",  # the MCP SDK writes the issuer with a trailing slash
                               resources={
            self.billing_url: set(BILLING_SCOPES), self.billing_mcp_url: set(BILLING_SCOPES),
            self.fx_mcp_url: {"fx:convert"}, self.broker_url: set(ALL_SCOPES)},
            clients={"penny": {"redirect_uris": [PENNY_REDIRECT]},
                     "billing-mcp": {"redirect_uris": [], "secret": billing_mcp.CLIENT_SECRET,
                                     "exchange_from": [self.billing_mcp_url]},
                     "broker": {"redirect_uris": [], "secret": BROKER_SECRET, "exchange_from": [self.broker_url]}})
        self.billing = billing_mod.Billing(self.billing_url, self.idp)
        self.eve = eve_mod.Eve(self.fx_url, self.idp, self.billing_url, self.billing_mcp_url)
        self.mode = billing_mcp_mode
        self._served = [
            Served(idp_mod.create_app(self.idp), ports["idp"]),
            Served(billing_mod.create_app(self.billing), ports["billing"]),
            Served(billing_mcp.create_server(billing_mcp_mode, self.billing_mcp_url, self.idp,
                                             self.billing_url).streamable_http_app(), ports["billing_mcp"]),
            Served(eve_mod.create_rest_app(self.eve), ports["fx"]),
            Served(eve_mod.create_mcp_server(self.eve, self.fx_mcp_url).streamable_http_app(), ports["fx_mcp"]),
        ]

    def close(self) -> None:
        for s in self._served:
            s.stop()

    def __enter__(self) -> "World":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
