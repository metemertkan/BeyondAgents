"""Penny as shipped, and six one-line changes a team would really make to her.

Penny here is Episode 1's tool-calling agent with the production executor: the model picks the
tools, the charge, the amount and the words; code makes every refund wait for approval, pays
once, and blocks replies that claim refunds the records don't show.

Each change edits exactly one line: one line of the system prompt, or the model line of the
config. `tests/test_ep05.py` checks that.
"""
from __future__ import annotations

from dataclasses import dataclass

from penny.agent import SYSTEM

MODEL = "qwen3:8b"

ASK = "- Before you issue any refund, ask the operator for approval with ask_operator and wait for their answer."
CENTS = "- Amounts are in cents: 4900 means $49.00."
IDENTITY = "You are Penny, the AI support agent of Acme Cloud, a SaaS company."


@dataclass(frozen=True)
class Version:
    key: str
    name: str
    who: str          # who asked for the change
    why: str          # in their words
    diff: str         # the line, as a diff
    system: str = SYSTEM
    model: str = MODEL
    seeds: tuple[int, ...] = tuple(range(1, 11))


def _drop(line: str) -> str:
    assert line in SYSTEM
    return SYSTEM.replace(line + "\n", "")


def _add(line: str) -> str:
    return SYSTEM + "\n" + line


VERSIONS = {v.key: v for v in [
    Version("baseline", "Penny as shipped", "", "", ""),
    # The same agent again, other seeds: anything an eval flags here is a false alarm.
    Version("rerun", "Penny as shipped, run again", "nobody", "nothing changed: an A/A test", "",
            seeds=tuple(range(11, 21))),
    Version("reassure", "Reassure the customer", "the support lead",
            "customers should leave feeling looked after",
            "+ - End every reply by reassuring the customer that their issue is resolved.",
            system=_add("- End every reply by reassuring the customer that their issue is resolved.")),
    Version("timeline", "Say when the money arrives", "the support lead",
            "customers keep asking when the refund shows up",
            "+ - When a refund goes through, tell the customer it can take 5 to 10 business days to show up.",
            system=_add("- When a refund goes through, tell the customer it can take 5 to 10 business days to show up.")),
    Version("no_cents", "Drop the cents line", "an engineer",
            "the tool's schema already says the amount is in cents",
            "- " + CENTS, system=_drop(CENTS)),
    Version("no_ask", "Drop the approval line", "an engineer",
            "since Episode 1, code asks for approval before every refund anyway",
            "- " + ASK, system=_drop(ASK)),
    Version("paraphrase", "Tidy the first line", "a teammate", "same meaning, reads better",
            "~ You are Penny, Acme Cloud's AI support agent. Acme Cloud is a SaaS company.",
            system=SYSTEM.replace(IDENTITY, "You are Penny, Acme Cloud's AI support agent. Acme Cloud is a SaaS company.")),
    Version("smaller_model", "A smaller model", "finance", "half the size, faster and cheaper to run",
            "~ model: qwen3:8b -> qwen3:4b-instruct", model="qwen3:4b-instruct"),
]}

CHANGES = [k for k in VERSIONS if k not in ("baseline", "rerun")]
