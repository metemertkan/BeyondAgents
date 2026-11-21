"""How the two agents hand work to each other, four ways. Fixed before any results.

Every design splits Penny into a front desk (talks to the customer, sends the one reply) and a
billing agent (looks up charges, refunds through Episode 1's production executor, asks the
operator). They talk over A2A (the a2a-sdk, JSON-RPC). The reference is one agent: Episode 5's
"Penny as shipped".

- chat           Act 1, the way the A2A samples do it: the front desk writes a request in its own
                 words, the billing agent answers in text. Errors go back to the front desk's model.
- whole_ticket   Act 2: the same, plus the customer's ticket, word for word, with every request.
- retry          Act 2: the same as chat, plus: when a hand-off times out, send the same message again.
- contract       Act 3: a typed work order (intent, the front desk's note, the customer's words as
                 data), a message id that comes from the ticket, a billing agent that does the work
                 once per message id (the spec's "MAY be idempotent"), refunds keyed by ticket and
                 charge, receipts back as data, and a reply checked against those receipts.
"""
from __future__ import annotations

from dataclasses import dataclass

MODEL = "qwen3:8b"
CONDITIONS = ("clean", "lost_handoff")


@dataclass(frozen=True)
class Design:
    key: str
    name: str
    act: int
    whole_ticket: bool = False
    retry: bool = False
    contract: bool = False
    conditions: tuple[str, ...] = CONDITIONS


DESIGNS = {d.key: d for d in [
    Design("chat", "Two agents, the A2A sample way", 1),
    Design("whole_ticket", "Hand over the whole ticket", 2, whole_ticket=True),
    # On a clean day nothing times out, so retry runs exactly like chat: only the bad day is run.
    Design("retry", "Retry when a hand-off times out", 2, retry=True, conditions=("lost_handoff",)),
    Design("contract", "A contract between agents", 3, whole_ticket=True, retry=True, contract=True),
]}
