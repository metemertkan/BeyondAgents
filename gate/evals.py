"""Four ways to decide whether a new version of Penny may ship. Each one reads finished runs.

1. spot_check     the PoC way: my three demo tickets, one run each, and does the reply say the
                  right thing (the right amount, a refund or not)
2. golden         reference replies: every ticket once, and is the reply close enough to the
                  approved answer (embedding similarity, bge-m3)
3. judge          an LLM judge: every ticket once, scored by DeepEval's G-Eval with a bigger local
                  model, given the ticket, the policy, the agent's tool calls and its reply
4. receipts_gate  what I'd build: every ticket five times, checked against what happened in the
                  payments and helpdesk records, compared with the shipped version's own record

Thresholds for 2 and 3 are calibrated on the shipped version, so it passes its own eval.
"""
from __future__ import annotations

import math
from itertools import combinations

from penny import claims
from penny.tickets import dollar_amounts

DEMO_TICKETS = ("ada", "grace", "alan")


# -- 1. the spot check ------------------------------------------------------------------------------

def spot_ok(row: dict) -> bool:
    """What I'd look for when reading the reply to one of my demo tickets."""
    if row["reply_count"] != 1:
        return False
    text = row["replies"][0]
    said = dollar_amounts(text)
    refund_word = "refund" in text.lower()
    if row["ticket"] == "ada":
        return 4900 in said and refund_word
    if row["ticket"] == "grace":
        return 2000 in said and refund_word
    if row["ticket"] == "alan":
        return 4900 in said and not claims.refund_claims(text)
    raise ValueError(f"not a demo ticket: {row['ticket']}")


# -- 2 and 3. per-ticket floors ---------------------------------------------------------------------

def floors(scores: dict[str, list[float]], margin: float) -> dict[str, float]:
    """The lowest score the shipped version got on each ticket, minus a margin."""
    return {t: min(v) - margin for t, v in scores.items()}


# -- 4. the receipts gate ---------------------------------------------------------------------------

FAILURES = ("missed_refund", "extra_refund", "wrong_charge", "unapproved_refund", "no_reply", "extra_reply",
            "untrue_reply")


def failures(row: dict) -> set[str]:
    """What went wrong for the customer in one run, read from the APIs' own records (Episode 1's audit)."""
    out = set()
    if row["refunded_cents"] < row["right_refund_cents"]:
        out.add("missed_refund")
    if row["refunded_cents"] > row["right_refund_cents"]:
        out.add("extra_refund")
    if row["wrong_charge_refunds"]:
        out.add("wrong_charge")
    if row["unapproved_refunds"]:
        out.add("unapproved_refund")
    if row["reply_count"] == 0:
        out.add("no_reply")
    if row["reply_count"] > 1:
        out.add("extra_reply")
    if row["reply_problems"]:
        out.add("untrue_reply")
    return out


def fisher_greater(a: int, n: int, b: int, m: int) -> float:
    """One-sided Fisher exact test: P(the new version shows >= a failures in n runs), if it fails no
    more often than the baseline's b failures in m runs."""
    total, k = n + m, a + b
    denominator = math.comb(total, k)
    return sum(math.comb(n, x) * math.comb(m, k - x) for x in range(a, min(n, k) + 1)) / denominator


def gate_ticket(runs: list[dict], baseline: list[dict], alpha: float = 0.05) -> list[str]:
    """Why one ticket's runs fail the gate (empty: it passes).

    - A failure the shipped version never showed on this ticket fails the gate the first time.
    - A failure it already showed sometimes fails the gate only if it got clearly more frequent.
    """
    seen = [failures(r) for r in baseline]
    known = set().union(*seen) if seen else set()
    reasons = []
    for kind in FAILURES:
        count = sum(kind in failures(r) for r in runs)
        if not count:
            continue
        if kind not in known:
            reasons.append(f"new: {kind} ({count}/{len(runs)})")
            continue
        base = sum(kind in s for s in seen)
        if fisher_greater(count, len(runs), base, len(baseline)) < alpha:
            reasons.append(f"worse: {kind} {count}/{len(runs)} vs {base}/{len(baseline)}")
    return reasons


def pass_rate_over_samples(runs: list[dict], baseline: list[dict], k: int) -> float:
    """The share of all k-run samples of `runs` that pass the gate for one ticket."""
    samples = list(combinations(runs, k))
    return sum(not gate_ticket(list(s), baseline) for s in samples) / len(samples)


def flag_probability(pass_rates: list[float]) -> float:
    """An eval flags a version if any ticket fails; tickets are independent runs."""
    return 1 - math.prod(pass_rates)
