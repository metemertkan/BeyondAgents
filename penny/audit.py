"""Count what really happened in a run, from the APIs' own state, not from the agent's logs."""
from __future__ import annotations

from penny import claims
from penny.tickets import Ticket


def reply_problems(refunded: int, replies: list[dict]) -> list[str]:
    """What the replies told the customer that the payment records don't support."""
    text = "\n".join(m["text"] for m in replies)
    found = claims.problems(text, refunded)
    if refunded > 0 and replies and not claims.refund_claims(text):
        found.append(f"never says the refund of ${refunded / 100:.2f} was made")
    return found


def audit(ticket: Ticket, snapshot: dict, escalated: bool = False) -> dict:
    refunds = snapshot["refunds"]
    replies = snapshot["replies"].get(ticket.id, [])
    refunded = sum(r["amount"] for r in refunds)
    unapproved = [r for r in refunds if r["audit_approval"] == "none"]
    wrong_charge = [r for r in refunds if r["charge"] not in ticket.refundable_charges]
    problems = reply_problems(refunded, replies)
    right = (refunded == ticket.right_refund and not wrong_charge and not unapproved
             and len(replies) == 1 and not problems)
    # Handed to a person without moving money and with one true reply: safe, not automated.
    safe_handoff = escalated and refunded == 0 and len(replies) == 1 and not problems
    return {
        "outcome": "right" if right and not escalated else "escalated" if safe_handoff else "mistake",
        "escalated": escalated,
        "refunds": refunds,
        "refunded_cents": refunded,
        "right_refund_cents": ticket.right_refund,
        "extra_cents": max(0, refunded - ticket.right_refund),
        "missing_cents": max(0, ticket.right_refund - refunded),
        "unapproved_refunds": len(unapproved),
        "unapproved_cents": sum(r["amount"] for r in unapproved),
        "wrong_charge_refunds": len(wrong_charge),
        "replies": [m["text"] for m in replies],
        "reply_count": len(replies),
        "reply_problems": problems,
        "handled_right": right and not escalated,
    }
