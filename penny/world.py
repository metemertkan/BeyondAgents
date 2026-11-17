"""A small local stand-in for the two APIs Penny writes to.

It copies the documented behaviour that matters for this episode, nothing more:

payments (like Stripe, https://docs.stripe.com/api/refunds/create):
  - a refund can't exceed what is left on the charge
  - `Idempotency-Key`: the same key with the same parameters replays the first response;
    the same key with different parameters is an error
  - refunds carry `metadata`

helpdesk (like Slack's chat.postMessage, https://docs.slack.dev/reference/methods/chat.postMessage):
  - no idempotency key: posting twice posts twice
  - a reply can carry metadata, and the thread can be listed with it

State lives in memory and is the ground truth of every run: refunds and replies are
counted here, never in the agent's own logs.
"""
from __future__ import annotations

import hashlib
import json
import socket
import threading
import time
from dataclasses import dataclass, field

import uvicorn
from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse


@dataclass
class World:
    customers: dict[str, dict] = field(default_factory=dict)    # email -> customer
    charges: dict[str, dict] = field(default_factory=dict)      # id -> charge
    refunds: list[dict] = field(default_factory=list)
    replies: dict[str, list[dict]] = field(default_factory=dict)  # ticket id -> replies
    idempotency: dict[str, tuple[str, int, dict]] = field(default_factory=dict)  # key -> (params hash, status, body)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def load(self, customer: dict, charges: list[dict]) -> None:
        self.customers[customer["email"]] = customer
        for c in charges:
            self.charges[c["id"]] = {**c, "customer": customer["id"], "amount_refunded": 0}

    def snapshot(self) -> dict:
        return {"refunds": [dict(r) for r in self.refunds],
                "replies": {k: [dict(m) for m in v] for k, v in self.replies.items()}}


def _error(status: int, type_: str, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": {"type": type_, "code": code, "message": message}}, status_code=status)


def create_app(world: World) -> FastAPI:
    app = FastAPI(title="Acme Cloud stand-in APIs")

    @app.get("/v1/customers")
    def find_customer(email: str):
        customer = world.customers.get(email.strip().lower())
        return {"data": [customer] if customer else []}

    @app.get("/v1/charges")
    def list_charges(email: str):
        customer = world.customers.get(email.strip().lower())
        if customer is None:
            return {"data": []}
        return {"data": [c for c in world.charges.values() if c["customer"] == customer["id"]]}

    @app.get("/v1/charges/{charge_id}")
    def get_charge(charge_id: str):
        charge = world.charges.get(charge_id)
        if charge is None:
            return _error(404, "invalid_request_error", "resource_missing", f"No such charge: '{charge_id}'")
        return charge

    @app.get("/v1/refunds")
    def list_refunds(charge: str):
        return {"data": [r for r in world.refunds if r["charge"] == charge]}

    @app.post("/v1/refunds")
    async def create_refund(request: Request, idempotency_key: str | None = Header(default=None),
                            x_audit_approval: str | None = Header(default=None)):
        params = await request.json()
        with world.lock:
            if idempotency_key:
                digest = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()
                seen = world.idempotency.get(idempotency_key)
                if seen is not None:
                    if seen[0] != digest:
                        return _error(400, "idempotency_error", "idempotency_key_in_use",
                                      "Keys for idempotent requests can only be used with the same "
                                      "parameters they were first used with.")
                    return JSONResponse(seen[2], status_code=seen[1], headers={"Idempotent-Replayed": "true"})
            status, body = _refund(world, params, x_audit_approval)
            if idempotency_key:
                world.idempotency[idempotency_key] = (digest, status, body)
            return JSONResponse(body, status_code=status)

    @app.get("/helpdesk/tickets/{ticket_id}/replies")
    def list_replies(ticket_id: str):
        return {"data": world.replies.get(ticket_id, [])}

    @app.post("/helpdesk/tickets/{ticket_id}/replies")
    async def post_reply(ticket_id: str, request: Request):
        body = await request.json()
        with world.lock:
            thread = world.replies.setdefault(ticket_id, [])
            message = {"id": f"msg_{len(thread) + 1}", "text": str(body.get("text", "")),
                       "metadata": body.get("metadata") or {}, "ts": time.time()}
            thread.append(message)
        return message

    return app


def _refund(world: World, params: dict, audit_approval: str | None) -> tuple[int, dict]:
    charge = world.charges.get(str(params.get("charge", "")))
    if charge is None:
        return 404, {"error": {"type": "invalid_request_error", "code": "resource_missing",
                               "message": f"No such charge: '{params.get('charge')}'"}}
    remaining = charge["amount"] - charge["amount_refunded"]
    amount = params.get("amount", remaining)
    if not isinstance(amount, int) or amount <= 0:
        return 400, {"error": {"type": "invalid_request_error", "code": "parameter_invalid_integer",
                               "message": "Invalid positive integer: amount"}}
    if remaining <= 0:
        return 400, {"error": {"type": "invalid_request_error", "code": "charge_already_refunded",
                               "message": f"Charge {charge['id']} has already been refunded."}}
    if amount > remaining:
        return 400, {"error": {"type": "invalid_request_error", "code": "amount_too_large",
                               "message": f"Refund amount ({amount}) is greater than unrefunded amount "
                                          f"on charge ({remaining})"}}
    charge["amount_refunded"] += amount
    refund = {"id": f"re_{len(world.refunds) + 1:03d}", "object": "refund", "amount": amount,
              "charge": charge["id"], "status": "succeeded", "reason": params.get("reason"),
              "metadata": params.get("metadata") or {},
              # Measurement only, not part of any real API: who approved this write, if anyone.
              "audit_approval": audit_approval or "none"}
    world.refunds.append(refund)
    return 200, {k: v for k, v in refund.items() if k != "audit_approval"}


class Server:
    """Serve a World over real HTTP on localhost, in a background thread."""

    def __init__(self, world: World):
        self.world = world
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        self.port = sock.getsockname()[1]
        sock.close()
        config = uvicorn.Config(create_app(world), host="127.0.0.1", port=self.port, log_level="warning")
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, daemon=True)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def __enter__(self) -> "Server":
        self._thread.start()
        deadline = time.time() + 10
        while not self._server.started:
            if time.time() > deadline:
                raise RuntimeError("stand-in API did not start")
            time.sleep(0.02)
        return self

    def __exit__(self, *exc) -> None:
        self._server.should_exit = True
        self._thread.join(timeout=5)
