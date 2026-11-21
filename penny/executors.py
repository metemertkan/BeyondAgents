"""Two executors behind one interface: what most demos do, and what production needs.

The executor sits between the model and the APIs. The model asks for a tool call; the
executor decides what actually happens. Same model, same prompt, same tools: only this
file changes between the two versions of Penny.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Callable

import httpx

from penny import claims
from penny.tickets import Ticket, approver
from penny.tools import Backend


def _usd(cents: int) -> str:
    return f"${cents / 100:.2f}"


class DemoExecutor:
    """Rules live in the prompt. Errors go back to the model as text, which is what most demos do.

    Approval happens only if the model calls ask_operator; nothing checks that it did.
    """

    name = "demo"

    def __init__(self, backend: Backend, ticket: Ticket):
        self.backend, self.ticket = backend, ticket
        self.operator_said_yes = False
        self.questions = 0
        self.log: list[dict] = []

    def execute(self, tool: str, args: dict) -> str:
        result = self._execute(tool, args)
        self.log.append({"tool": tool, "args": args, "result": result})
        return result

    def _execute(self, tool: str, args: dict) -> str:
        if tool == "ask_operator":
            self.questions += 1
            ok, answer = approver(self.ticket, str(args.get("question", "")))
            self.operator_said_yes |= ok
            return answer
        try:
            if tool == "find_charges":
                r = self.backend.find_charges()
            elif tool == "refund_charge":
                r = self.backend.refund(str(args.get("charge_id", "")), _int(args.get("amount")),
                                        args.get("reason"),
                                        audit_approval="operator" if self.operator_said_yes else None)
            elif tool == "reply_to_customer":
                r = self.backend.reply(str(args.get("message", "")))
            else:
                return f"Error: unknown tool {tool}"
        except httpx.HTTPError as e:
            return f"Error: {type(e).__name__}: {e}"
        if r.status_code >= 400:
            return f"Error: {r.status_code} {r.reason_phrase}: {r.text}"
        return r.text


@dataclass
class Approval:
    id: str
    args_hash: str
    card: str
    approved: bool
    answer: str


@dataclass
class Receipt:
    kind: str                  # "refund" or "reply"
    key: str                   # idempotency key used on every attempt
    args_hash: str
    outcome: str               # "done", "failed" or "unknown"
    attempts: int
    approval_id: str | None = None
    provider_id: str | None = None
    amount: int = 0
    notes: list[str] = field(default_factory=list)


class ProductionExecutor:
    """Rules live in code.

    1. Ask first: every refund stops for approval here, whatever the model or the ticket says.
       The card is written by code from the exact arguments and the live charge.
    2. Pay once: the approval id is the idempotency key; the same refund again returns the receipt.
    3. Say only what's true: a write has three outcomes (done, not done, unknown). Unknown is
       resolved before retrying, and a reply may only state what the receipts show.
    """

    name = "production"

    def __init__(self, backend: Backend, ticket: Ticket, sleep: Callable[[float], None] = time.sleep,
                 max_attempts: int = 4):
        self.backend, self.ticket = backend, ticket
        self.sleep, self.max_attempts = sleep, max_attempts
        self.approvals: dict[str, Approval] = {}
        self.receipts: list[Receipt] = []
        self.questions = 0
        self.blocked_replies = 0
        self.log: list[dict] = []
        # Episode 6 hooks (both off by default): extra metadata on every refund, and approval ids
        # (which are the idempotency keys) derived from the request instead of random.
        self.refund_metadata: dict = {}
        self.approval_id_for: Callable[[str, int], str] | None = None

    # -- the interface --------------------------------------------------------------------------

    def execute(self, tool: str, args: dict) -> str:
        if tool == "find_charges":
            result = self._read(self.backend.find_charges)
        elif tool == "ask_operator":
            self.questions += 1
            result = approver(self.ticket, str(args.get("question", "")))[1]
        elif tool == "refund_charge":
            result = self._refund(args)
        elif tool == "reply_to_customer":
            result = self._reply(args)
        else:
            result = f"Error: unknown tool {tool}"
        self.log.append({"tool": tool, "args": args, "result": result})
        return result

    def records(self) -> dict:
        return {"approvals": [asdict(a) for a in self.approvals.values()],
                "receipts": [asdict(r) for r in self.receipts]}

    # -- reads are safe to retry ----------------------------------------------------------------

    def _read(self, call: Callable[[], httpx.Response]) -> str:
        for attempt in range(self.max_attempts):
            try:
                r = call()
            except httpx.TransportError:
                self.sleep(0.5 * 2 ** attempt)
                continue
            if r.status_code == 429 or r.status_code >= 500:
                self.sleep(_retry_after(r, 0.5 * 2 ** attempt))
                continue
            if r.status_code >= 400:
                return f"Error: {_message(r)}"
            return r.text
        return "Error: the API did not answer. Try again later."

    # -- writes: three outcomes -------------------------------------------------------------------

    def _write(self, call: Callable[[], httpx.Response], receipt: Receipt,
               look_up: Callable[[], dict | None] | None = None) -> dict | None:
        """Run a write until it is done or failed. Returns the API's answer, or None."""
        for attempt in range(1, self.max_attempts + 1):
            receipt.attempts = attempt
            try:
                r = call()
            except (httpx.ConnectError, httpx.ConnectTimeout):
                receipt.notes.append("not done: could not connect; retrying")
                self.sleep(0.5 * 2 ** attempt)
                continue
            except httpx.TransportError as e:
                receipt.notes.append(f"unknown: {type(e).__name__}")
                if look_up is not None:          # no idempotency key: look before retrying
                    found = look_up()
                    if found is not None:
                        receipt.notes.append("found it: it had worked")
                        receipt.outcome = "done"
                        return found
                    receipt.notes.append("not found: retrying")
                else:                            # same key: the API replays the first answer
                    receipt.notes.append("retrying with the same key")
                self.sleep(0.5)
                continue
            if r.status_code == 429:
                wait = _retry_after(r, 1.0)
                receipt.notes.append(f"not done: rate limited; waiting {wait:g}s")
                self.sleep(wait)
                continue
            if r.status_code >= 500:
                receipt.notes.append(f"unknown: HTTP {r.status_code}")
                if look_up is not None and (found := look_up()) is not None:
                    receipt.outcome = "done"
                    return found
                self.sleep(0.5 * 2 ** attempt)
                continue
            if r.status_code >= 400:
                receipt.outcome = "failed"
                receipt.notes.append(_message(r))
                return r.json()
            if r.headers.get("Idempotent-Replayed") == "true":
                receipt.notes.append("the API replayed the first answer: it had worked")
            receipt.outcome = "done"
            return r.json()
        receipt.outcome = "unknown"
        return None

    # -- refunds ----------------------------------------------------------------------------------

    def _refund(self, args: dict) -> str:
        charge_id, amount = str(args.get("charge_id", "")), _int(args.get("amount"))
        if amount <= 0:
            return "Error: amount must be a positive number of cents."
        charge_text = self._read(lambda: self.backend.get_charge(charge_id))
        if charge_text.startswith("Error"):
            return charge_text
        charge = json.loads(charge_text)
        if charge.get("customer") != self.ticket.customer["id"]:
            return "Refused: that charge belongs to another customer."

        args_hash = _hash({"tool": "refund_charge", "charge": charge_id, "amount": amount})
        for r in self.receipts:
            if r.args_hash == args_hash and r.outcome == "done":
                return (f"Already done: refund {r.provider_id} of {_usd(r.amount)} on {charge_id} "
                        f"succeeded earlier. Nothing was refunded again.")

        approval = self.approvals.get(args_hash)
        if approval is None:
            card = self._card(charge, amount, args.get("reason"))
            ok, answer = approver(self.ticket, card, amount=amount, charge_id=charge_id)
            approval_id = self.approval_id_for(charge_id, amount) if self.approval_id_for else f"apr_{uuid.uuid4().hex[:12]}"
            approval = Approval(approval_id, args_hash, card, ok, answer)
            self.approvals[args_hash] = approval
        if not approval.approved:
            return (f"Refund not approved by the operator: {approval.answer} Nothing was refunded. "
                    f"Don't promise a refund to the customer.")

        receipt = Receipt("refund", approval.id, args_hash, "unknown", 0, approval.id, amount=amount)
        self.receipts.append(receipt)
        answer = self._write(lambda: self.backend.refund(
            charge_id, amount, args.get("reason"), idempotency_key=approval.id,
            metadata={"approval_id": approval.id, "ticket": self.ticket.id, **self.refund_metadata},
            audit_approval=approval.id),
            receipt)
        if receipt.outcome == "done":
            receipt.provider_id = answer.get("id")
            return f"Refund {receipt.provider_id} succeeded: {_usd(amount)} on {charge_id}."
        if receipt.outcome == "failed":
            return f"Refund failed, nothing was refunded: {receipt.notes[-1]}"
        return ("The refund's outcome is unknown; an operator will check it. Tell the customer it is "
                "being checked. Don't say it is done.")

    def _card(self, charge: dict, amount: int, reason) -> str:
        t = self.ticket
        return "\n".join([
            f"Refund request, ticket {t.id} ({t.customer['name']}, {t.email})",
            f"  Refund:    {_usd(amount)} to the customer's card",
            f"  Charge:    {charge['id']}, {_usd(charge['amount'])} on {charge['created']}, "
            f"\"{charge['description']}\"",
            f"  Already refunded on this charge: {_usd(charge['amount_refunded'])}",
            f"  After this refund: {_usd(charge['amount_refunded'] + amount)} of {_usd(charge['amount'])} refunded",
            f"  Reason given by the agent (not checked): {reason}",
        ])

    # -- replies ----------------------------------------------------------------------------------

    def _reply(self, args: dict) -> str:
        text = str(args.get("message", ""))
        for r in self.receipts:
            if r.kind == "reply" and r.outcome == "done":
                return "Already replied to the customer on this ticket. Not sent again: one reply per ticket."
        refunded = sum(r.amount for r in self.receipts if r.kind == "refund" and r.outcome == "done")
        found = claims.problems(text, refunded)
        if found:
            self.blocked_replies += 1
            if self.blocked_replies > 3:
                return "Not sent. Stop here: the operator will write this reply."
            return f"Not sent: {found[0]}. Rewrite the reply so it only states what the records show."

        key = f"{self.ticket.id}:reply"
        receipt = Receipt("reply", key, _hash({"tool": "reply", "ticket": self.ticket.id}), "unknown", 0)
        self.receipts.append(receipt)

        def look_up() -> dict | None:
            listing = self._read(self.backend.replies)
            if listing.startswith("Error"):
                return None
            for message in json.loads(listing)["data"]:
                if message.get("metadata", {}).get("idempotency_key") == key:
                    return message
            return None

        answer = self._write(lambda: self.backend.reply(text, metadata={"idempotency_key": key}), receipt, look_up)
        if receipt.outcome == "done":
            receipt.provider_id = answer.get("id")
            return f"Reply sent ({receipt.provider_id})."
        if receipt.outcome == "failed":
            return f"Reply failed: {receipt.notes[-1]}"
        return "The reply's outcome is unknown; an operator will check it. Don't send it again."


def _int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _hash(obj: dict) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()[:16]


def _retry_after(r: httpx.Response, default: float) -> float:
    try:
        return float(r.headers.get("Retry-After", default))
    except ValueError:
        return default


def _message(r: httpx.Response) -> str:
    try:
        error = r.json().get("error", {})
        return f"{error.get('code', r.status_code)}: {error.get('message', r.text)}"
    except ValueError:
        return f"HTTP {r.status_code}: {r.text[:200]}"
