"""The services the month-end job talks to. They run outside the worker, so they outlive its crashes.

payments    refunds; a charge can't be refunded beyond its amount (like Stripe), and the same
            Idempotency-Key with the same parameters replays the first answer
helpdesk    replies to customers; no idempotency key (like Slack), but replies carry metadata
approvals   a person approves each refund; scripted: says yes after a short delay if the amount is
            right for the customer. An optional client key makes a repeated request the same request.

Every call is recorded; the scoring reads these records, never the worker's own logs.
"""
from __future__ import annotations

import hashlib
import json
import threading
import time

from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse

from month_end.data import BY_ID, right_refund

APPROVAL_DELAY = 1.0   # seconds; stands in for a person taking minutes or hours


class Ledger:
    def __init__(self):
        self.lock = threading.Lock()
        self.refunds: list[dict] = []
        self.replies: list[dict] = []
        self.approvals: dict[str, dict] = {}
        self.approval_keys: dict[str, str] = {}
        self.idempotency: dict[str, tuple[str, int, dict]] = {}

    def state(self) -> dict:
        with self.lock:
            return {"refunds": list(self.refunds), "replies": list(self.replies),
                    "approvals": list(self.approvals.values())}


def create_app(ledger: Ledger) -> FastAPI:
    app = FastAPI(title="Acme month-end services")

    @app.post("/refunds")
    async def refund(request: Request, idempotency_key: str | None = Header(default=None)):
        body = await request.json()
        with ledger.lock:
            digest = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
            if idempotency_key and idempotency_key in ledger.idempotency:
                seen = ledger.idempotency[idempotency_key]
                if seen[0] != digest:
                    return JSONResponse({"error": "idempotency_error"}, status_code=400)
                return JSONResponse(seen[2], status_code=seen[1], headers={"Idempotent-Replayed": "true"})
            customer, amount = body.get("customer"), float(body.get("amount_usd", 0))
            done = sum(r["amount_usd"] for r in ledger.refunds if r["customer"] == customer)
            if customer not in BY_ID or amount <= 0 or done + amount > BY_ID[customer]["charged_usd"]:
                status, out = 400, {"error": "amount_too_large" if customer in BY_ID else "no_such_customer"}
            else:
                refund = {"id": f"re_{len(ledger.refunds) + 1:03d}", "customer": customer, "amount_usd": amount,
                          "status": "succeeded"}
                ledger.refunds.append(refund)
                status, out = 200, refund
            if idempotency_key:
                ledger.idempotency[idempotency_key] = (digest, status, out)
        return JSONResponse(out, status_code=status)

    @app.post("/replies")
    async def reply(request: Request):
        body = await request.json()
        with ledger.lock:
            msg = {"id": f"msg_{len(ledger.replies) + 1:03d}", "customer": body.get("customer"),
                   "text": body.get("text", ""), "metadata": body.get("metadata") or {}}
            ledger.replies.append(msg)
        return msg

    @app.get("/replies")
    def replies(customer: str):
        with ledger.lock:
            return {"data": [m for m in ledger.replies if m["customer"] == customer]}

    @app.post("/approvals")
    async def request_approval(request: Request):
        body = await request.json()
        with ledger.lock:
            key = body.get("client_key")
            if key and key in ledger.approval_keys:
                return ledger.approvals[ledger.approval_keys[key]]
            aid = f"apr_{len(ledger.approvals) + 1:03d}"
            ledger.approvals[aid] = {"id": aid, "customer": body.get("customer"),
                                     "amount_usd": float(body.get("amount_usd", 0)), "asked_at": time.time()}
            if key:
                ledger.approval_keys[key] = aid
            return ledger.approvals[aid]

    @app.get("/approvals/{aid}")
    def approval(aid: str):
        with ledger.lock:
            a = dict(ledger.approvals[aid])
        if time.time() - a["asked_at"] < APPROVAL_DELAY:
            return {**a, "status": "pending"}
        ok = abs(a["amount_usd"] - right_refund(a["customer"])) < 0.005
        return {**a, "status": "approved" if ok else "rejected"}

    return app
