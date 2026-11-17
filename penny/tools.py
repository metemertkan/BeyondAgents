"""The tools Penny sees, and the HTTP calls behind them.

The model chooses the tool and its arguments. It never chooses whose account: the ticket
being handled decides the customer and the thread. Where the tools come from (your own code,
Zapier, n8n, an integration platform) doesn't change anything in this episode.
"""
from __future__ import annotations

import httpx

TOOLS = [
    {"type": "function", "function": {
        "name": "find_charges",
        "description": "List the customer's recent charges, with how much of each one was already refunded.",
        "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {
        "name": "refund_charge",
        "description": "Refund a charge, fully or partly. The money goes back to the customer's card.",
        "parameters": {"type": "object", "properties": {
            "charge_id": {"type": "string"},
            "amount": {"type": "integer", "description": "Amount to refund, in cents"},
            "reason": {"type": "string", "enum": ["duplicate", "requested_by_customer", "fraudulent"]}},
            "required": ["charge_id", "amount", "reason"]}}},
    {"type": "function", "function": {
        "name": "ask_operator",
        "description": "Ask the support operator a question, for example for approval. Returns their answer.",
        "parameters": {"type": "object", "properties": {
            "question": {"type": "string"}},
            "required": ["question"]}}},
    {"type": "function", "function": {
        "name": "reply_to_customer",
        "description": "Send a reply to the customer on the ticket.",
        "parameters": {"type": "object", "properties": {
            "message": {"type": "string"}},
            "required": ["message"]}}},
]

WRITES = {"refund_charge", "reply_to_customer"}


class Backend:
    """HTTP calls to the payments and helpdesk APIs for one ticket."""

    def __init__(self, base_url: str, transport: httpx.BaseTransport, ticket, timeout: float = 30.0):
        self.http = httpx.Client(base_url=base_url, transport=transport, timeout=timeout)
        self.ticket = ticket

    def close(self) -> None:
        self.http.close()

    def find_charges(self) -> httpx.Response:
        return self.http.get("/v1/charges", params={"email": self.ticket.email})

    def get_charge(self, charge_id: str) -> httpx.Response:
        return self.http.get(f"/v1/charges/{charge_id}")

    def refund(self, charge_id: str, amount: int, reason: str | None, *, idempotency_key: str | None = None,
               metadata: dict | None = None, audit_approval: str | None = None) -> httpx.Response:
        headers = {}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        if audit_approval:
            headers["X-Audit-Approval"] = audit_approval  # measurement only
        body = {"charge": charge_id, "amount": amount, "reason": reason}
        if metadata:
            body["metadata"] = metadata
        return self.http.post("/v1/refunds", json=body, headers=headers)

    def reply(self, text: str, metadata: dict | None = None) -> httpx.Response:
        return self.http.post(f"/helpdesk/tickets/{self.ticket.id}/replies",
                              json={"text": text, "metadata": metadata or {}})

    def replies(self) -> httpx.Response:
        return self.http.get(f"/helpdesk/tickets/{self.ticket.id}/replies")
