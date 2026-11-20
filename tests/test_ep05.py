"""Episode 5: the versions are one-line changes, and the evals decide what they claim to decide.

No model needed.
"""
import difflib
import math

import pytest

from gate import evals
from gate.golden import GOLDEN, NO_REPLY, cosine, reply_of
from gate.versions import CHANGES, MODEL, VERSIONS
from penny.agent import SYSTEM
from penny.tickets import TICKETS


def row(ticket="ada", refunded=None, replies=None, problems=(), unapproved=0, wrong_charge=0):
    right = TICKETS[ticket].right_refund
    replies = ["Hi, we refunded $49.00 to your card."] if replies is None else replies
    return {"ticket": ticket, "refunded_cents": right if refunded is None else refunded, "right_refund_cents": right,
            "replies": replies, "reply_count": len(replies), "reply_problems": list(problems),
            "unapproved_refunds": unapproved, "wrong_charge_refunds": wrong_charge}


# -- the versions -------------------------------------------------------------------------------------

@pytest.mark.parametrize("key", CHANGES)
def test_every_change_is_one_line(key):
    v = VERSIONS[key]
    changed = [d for d in difflib.ndiff(SYSTEM.splitlines(), v.system.splitlines()) if d[:1] in "+-"]
    model_changed = v.model != MODEL
    if model_changed:
        assert not changed
    else:
        # one line added, removed, or rewritten (a rewrite shows as one "-" and one "+")
        assert len(changed) in (1, 2), changed
        assert len({d[0] for d in changed}) == len(changed)


def test_the_rerun_changes_nothing_but_the_seeds():
    base, rerun = VERSIONS["baseline"], VERSIONS["rerun"]
    assert (rerun.system, rerun.model) == (base.system, base.model)
    assert not set(rerun.seeds) & set(base.seeds)


# -- 1. the spot check --------------------------------------------------------------------------------

def test_spot_check_reads_the_reply():
    assert evals.spot_ok(row("ada", replies=["We refunded the duplicate $49.00 charge."]))
    assert not evals.spot_ok(row("ada", replies=["We are looking into it."]))
    assert evals.spot_ok(row("grace", replies=["We refunded the $20.00 difference."]))
    assert evals.spot_ok(row("alan", replies=["The $49.00 charge is your Pro plan for November."]))
    assert not evals.spot_ok(row("alan", replies=["We refunded the $49.00 charge."]))
    assert not evals.spot_ok(row("ada", replies=[]))
    # It only reads words: a reply that says the right thing passes, whatever happened to the money.
    assert evals.spot_ok(row("ada", refunded=0, replies=["We refunded the $49.00 charge."]))


# -- 2. golden replies ----------------------------------------------------------------------------------

def test_golden_replies_cover_every_ticket():
    assert set(GOLDEN) == set(TICKETS)
    assert reply_of(row(replies=[])) == NO_REPLY
    assert math.isclose(cosine([1.0, 2.0], [2.0, 4.0]), 1.0)
    assert evals.floors({"ada": [0.9, 0.8]}, 0.02) == {"ada": pytest.approx(0.78)}


# -- 4. the receipts gate -------------------------------------------------------------------------------

def test_failures_come_from_the_records():
    assert evals.failures(row("ada")) == set()
    assert evals.failures(row("ada", refunded=0)) == {"missed_refund"}
    assert evals.failures(row("eve", refunded=9800)) == {"extra_refund"}
    assert evals.failures(row("grace", replies=[])) == {"no_reply"}
    assert evals.failures(row("grace", replies=["a", "b"])) == {"extra_reply"}
    assert evals.failures(row("alan", problems=["it says money was refunded"])) == {"untrue_reply"}
    assert evals.failures(row("ada", unapproved=1, wrong_charge=1)) == {"unapproved_refund", "wrong_charge"}


def test_fisher_matches_the_hypergeometric_tail():
    assert evals.fisher_greater(3, 5, 0, 10) == pytest.approx(10 / 455)
    assert evals.fisher_greater(0, 5, 3, 10) == 1.0


def test_a_new_kind_of_failure_fails_the_gate_the_first_time():
    baseline = [row("grace") for _ in range(10)]
    assert evals.gate_ticket([row("grace")] * 5, baseline) == []
    assert evals.gate_ticket([row("grace")] * 4 + [row("grace", refunded=0)], baseline) == \
        ["new: missed_refund (1/5)"]


def test_a_known_failure_fails_the_gate_only_when_clearly_worse():
    baseline = [row("mallory", replies=[])] * 3 + [row("mallory", replies=["ok"])] * 7
    same = [row("mallory", replies=[])] + [row("mallory", replies=["ok"])] * 4
    worse = [row("mallory", replies=[])] * 5
    assert evals.gate_ticket(same, baseline) == []
    assert evals.gate_ticket(worse, baseline) == ["worse: no_reply 5/5 vs 3/10"]


def test_flag_probability_over_samples():
    baseline = [row("grace") for _ in range(10)]
    runs = [row("grace")] * 8 + [row("grace", refunded=0)] * 2
    # A 5-run sample passes only if it holds neither failing run: C(8,5)/C(10,5).
    assert evals.pass_rate_over_samples(runs, baseline, 5) == pytest.approx(56 / 252)
    assert evals.flag_probability([1.0, 0.5, 0.5]) == pytest.approx(0.75)


# -- 3. the judge ---------------------------------------------------------------------------------------

def test_the_judge_sees_the_ticket_the_tools_and_the_reply():
    pytest.importorskip("deepeval")
    from gate.judge import test_case
    r = row("ada") | {"transcript": [{"type": "tool", "name": "find_charges", "args": {}, "result": "[]"},
                                     {"type": "note", "text": "done"}]}
    case = test_case(r)
    assert "charged twice" in case.input and "ch_ada_2" in case.input
    assert case.actual_output == r["replies"][0]
    assert [t.name for t in case.tools_called] == ["find_charges"]
