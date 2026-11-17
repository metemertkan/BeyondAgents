"""Acme Cloud's refund policy, in code.

The model tells us what the customer is asking for. This module decides what, if anything, gets
refunded, from the billing records alone. Nothing written in a ticket can change the outcome.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

INTENTS = ("duplicate_charge", "wrong_price", "cancel", "question", "other")
DUPLICATE_WINDOW_MINUTES = 10


@dataclass(frozen=True)
class Decision:
    action: str                 # "refund", "no_refund" or "escalate"
    facts: str                  # what may be told to the customer, addressed to them
    charge_id: str | None = None
    amount: int = 0


def _usd(cents: int) -> str:
    return f"${cents / 100:.2f}"


def _when(charge: dict) -> datetime:
    return datetime.strptime(charge["created"], "%Y-%m-%d %H:%M")


def find_duplicate(charges: list[dict]) -> dict | None:
    """The later of two charges with the same amount and description, minutes apart, nothing refunded."""
    ordered = sorted(charges, key=_when)
    for i, a in enumerate(ordered):
        for b in ordered[i + 1:]:
            close = (_when(b) - _when(a)).total_seconds() <= DUPLICATE_WINDOW_MINUTES * 60
            if close and a["amount"] == b["amount"] and a["description"] == b["description"] \
                    and a["amount_refunded"] == 0 and b["amount_refunded"] == 0:
                return b
    return None


def decide(intent: str, customer: dict, charges: list[dict]) -> Decision:
    latest = max(charges, key=_when) if charges else None
    charge_list = "; ".join(f"{_usd(c['amount'])} on {c['created'][:10]} ({c['description']})"
                            for c in sorted(charges, key=_when))
    if intent == "duplicate_charge":
        dup = find_duplicate(charges)
        if dup is None:
            return Decision("no_refund", f"We found no duplicate charge. Your charges are: {charge_list}. "
                                         f"Each one is for a different period, so nothing was refunded.")
        return Decision("refund", f"The {_usd(dup['amount'])} charge on {dup['created'][:10]} ({dup['description']}) "
                                  f"was a duplicate", dup["id"], dup["amount"])
    if intent == "wrong_price":
        if latest is None:
            return Decision("escalate", "No charges were found.")
        over = latest["amount"] - latest["amount_refunded"] - customer["plan_price"]
        if over <= 0:
            return Decision("no_refund", f"The {_usd(latest['amount'])} charge on {latest['created'][:10]} matches "
                                         f"your {customer['plan']} plan price of {_usd(customer['plan_price'])}, "
                                         f"so nothing was refunded.")
        return Decision("refund", f"Your {customer['plan']} plan costs {_usd(customer['plan_price'])} but "
                                  f"{_usd(latest['amount'])} was charged on {latest['created'][:10]}",
                        latest["id"], over)
    if intent == "cancel":
        return Decision("no_refund", "Your request to cancel was passed on to the team. Past charges are not "
                                     "refunded when an account is cancelled, so nothing was refunded.")
    if intent == "question":
        return Decision("no_refund", f"You are on the {customer['plan']} plan "
                                     f"({_usd(customer['plan_price'])} a month). Your charges: {charge_list}. "
                                     f"Nothing was refunded.")
    return Decision("escalate", "This ticket needs a person.")
