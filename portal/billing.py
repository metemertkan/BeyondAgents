"""Acme's billing API: the system of record, and the ground truth of every run.

It accepts either the master key (an administrator) or a user's token issued for this API by
Acme's IdP, and then enforces Acme's rules for that user:
- a customer may read only their own profile and invoices, and may not refund
- support staff may read any customer and refund up to $100

It also publishes a UTCP manual, so a UTCP client can call it directly.
Every request lands in `audit`, which the scoring reads.
"""
from __future__ import annotations

import jwt
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from portal.data import ADMIN_KEY, CUSTOMERS, INVOICES, STAFF_REFUND_LIMIT_USD
from portal.idp import IdP


class Billing:
    def __init__(self, url: str, idp: IdP):
        self.url, self.idp = url, idp
        self.audit: list[dict] = []
        self.refunds: list[dict] = []

    def principal(self, request: Request) -> dict | None:
        auth = request.headers.get("authorization", "")
        token = auth[7:] if auth.lower().startswith("bearer ") else ""
        if token == ADMIN_KEY:
            return {"sub": "admin", "role": "admin", "scopes": {"*"}, "act": None}
        try:
            claims = self.idp.decode(token, audience=self.url)
        except jwt.PyJWTError:
            return None
        return {"sub": claims["sub"], "role": claims["role"], "scopes": set(claims["scope"].split()),
                "act": (claims.get("act") or {}).get("sub")}

    def record(self, request: Request, who: dict | None, action: str, target: str, allowed: bool, **extra) -> None:
        self.audit.append({"action": action, "target": target, "allowed": allowed,
                           "principal": who["sub"] if who else None, "role": who["role"] if who else None,
                           "act": who["act"] if who else None,
                           # Measurement only: requests Eve replays are labelled by her own code.
                           "replay": request.headers.get("x-measure-replay") == "1", **extra})


def _may(who: dict, scope: str) -> bool:
    return "*" in who["scopes"] or scope in who["scopes"]


def create_app(billing: Billing) -> FastAPI:
    app = FastAPI(title="Acme billing")

    def read(request: Request, email: str, action: str, scope: str, data):
        who = billing.principal(request)
        if who is None:
            billing.record(request, who, action, email, False)
            return JSONResponse({"error": "invalid_token"}, status_code=401)
        own = who["sub"] == email
        allowed = _may(who, scope) and (who["role"] in ("admin", "support") or own)
        billing.record(request, who, action, email, allowed)
        if not allowed:
            return JSONResponse({"error": "forbidden", "message": f"{who['sub']} may not read {email}"}, status_code=403)
        if data is None:
            return JSONResponse({"error": "not_found"}, status_code=404)
        return data

    @app.get("/api/customers/{email}")
    def get_customer(email: str, request: Request):
        return read(request, email, "get_customer", "profile:read", CUSTOMERS.get(email))

    @app.get("/api/customers/{email}/invoices")
    def get_invoices(email: str, request: Request):
        return read(request, email, "get_invoices", "invoices:read",
                    {"invoices": INVOICES[email]} if email in INVOICES else None)

    @app.post("/api/invoices/{invoice_id}/refund")
    def refund(invoice_id: str, amount_usd: float, request: Request):
        who = billing.principal(request)
        owner = next((e for e, items in INVOICES.items() if any(i["id"] == invoice_id for i in items)), None)
        if who is None:
            billing.record(request, who, "refund", owner or invoice_id, False, amount_usd=amount_usd)
            return JSONResponse({"error": "invalid_token"}, status_code=401)
        allowed = _may(who, "refunds:write") and (
            who["role"] == "admin" or (who["role"] == "support" and amount_usd <= STAFF_REFUND_LIMIT_USD))
        billing.record(request, who, "refund", owner or invoice_id, allowed, amount_usd=amount_usd)
        if not allowed:
            return JSONResponse({"error": "forbidden", "message": f"{who['sub']} may not refund this"}, status_code=403)
        if owner is None:
            return JSONResponse({"error": "not_found"}, status_code=404)
        refund = {"id": f"re_{len(billing.refunds) + 1:03d}", "invoice": invoice_id, "amount_usd": amount_usd,
                  "status": "succeeded"}
        billing.refunds.append({**refund, "by": who["sub"]})
        return refund

    @app.get("/utcp")
    def manual():
        """The UTCP manual: how to call this API directly. Credentials come from the caller's variables."""
        auth = {"auth_type": "api_key", "api_key": "Bearer ${BILLING_TOKEN}", "var_name": "Authorization",
                "location": "header"}
        email = {"type": "object", "properties": {"email": {"type": "string", "description": "Customer email"}},
                 "required": ["email"]}
        return {"utcp_version": "1.2.0", "manual_version": "1.0.0", "tools": [
            {"name": "get_customer", "description": "Get a customer's profile by email.", "inputs": email,
             "tool_call_template": {"call_template_type": "http", "http_method": "GET",
                                    "url": f"{billing.url}/api/customers/{{email}}", "auth": auth}},
            {"name": "get_invoices", "description": "List a customer's invoices by email.", "inputs": email,
             "tool_call_template": {"call_template_type": "http", "http_method": "GET",
                                    "url": f"{billing.url}/api/customers/{{email}}/invoices", "auth": auth}},
            {"name": "refund_invoice", "description": "Refund an invoice to the customer's card.",
             "inputs": {"type": "object", "properties": {"invoice_id": {"type": "string"},
                                                         "amount_usd": {"type": "number"}},
                        "required": ["invoice_id", "amount_usd"]},
             "tool_call_template": {"call_template_type": "http", "http_method": "POST",
                                    "url": f"{billing.url}/api/invoices/{{invoice_id}}/refund", "auth": auth}},
        ]}

    return app
