"""The world's documented behaviour, and both executors under each fault, without a model.

A scripted "model" makes the calls a model typically makes: refund, and on an error, refund again.
"""
import pytest

from penny.audit import audit
from penny.executors import DemoExecutor, ProductionExecutor
from penny.faults import FaultyTransport
from penny.tickets import TICKETS
from penny.tools import Backend
from penny.world import Server, World


@pytest.fixture
def setup():
    def make(ticket_key, condition, executor_cls):
        ticket = TICKETS[ticket_key]
        world = World()
        world.load(ticket.customer, [dict(c) for c in ticket.charges])
        server = Server(world).__enter__()
        backend = Backend(server.url, FaultyTransport(condition), ticket)
        kwargs = {"sleep": lambda s: None} if executor_cls is ProductionExecutor else {}
        executor = executor_cls(backend, ticket, **kwargs)
        made.append((server, backend))
        return ticket, world, executor
    made = []
    yield make
    for server, backend in made:
        backend.close()
        server.__exit__(None, None, None)


def retry_on_error(executor, tool, args):
    """What models did in the pilot: on an error, call the same tool again, once."""
    result = executor.execute(tool, args)
    if result.startswith("Error"):
        result = executor.execute(tool, args)
    return result


GRACE_REFUND = {"charge_id": "ch_grace_nov", "amount": 2000, "reason": "requested_by_customer"}


# -- the world copies the documented behaviour ---------------------------------------------------

def test_refund_cap_and_idempotency_key(setup):
    ticket, world, executor = setup("ada", "clean", DemoExecutor)
    b = executor.backend
    assert b.refund("ch_ada_1", 4900, "duplicate").status_code == 200
    second = b.refund("ch_ada_1", 4900, "duplicate")
    assert second.status_code == 400 and second.json()["error"]["code"] == "charge_already_refunded"

    first = b.refund("ch_ada_2", 1000, "duplicate", idempotency_key="k1")
    again = b.refund("ch_ada_2", 1000, "duplicate", idempotency_key="k1")
    assert again.json() == first.json() and again.headers["Idempotent-Replayed"] == "true"
    other = b.refund("ch_ada_2", 2000, "duplicate", idempotency_key="k1")
    assert other.status_code == 400 and other.json()["error"]["type"] == "idempotency_error"
    assert sum(r["amount"] for r in world.refunds) == 4900 + 1000


def test_helpdesk_has_no_idempotency(setup):
    ticket, world, executor = setup("alan", "clean", DemoExecutor)
    executor.backend.reply("hello")
    executor.backend.reply("hello")
    assert len(world.replies[ticket.id]) == 2


# -- the demo executor: one approval, a lost response, two refunds ---------------------------------

def test_demo_lost_response_refunds_twice(setup):
    ticket, world, executor = setup("grace", "lost_response", DemoExecutor)
    assert executor.execute("ask_operator", {"question": "May I refund $20 to Grace?"}).startswith("Approved")
    result = retry_on_error(executor, "refund_charge", GRACE_REFUND)
    assert '"status":"succeeded"' in result
    assert sum(r["amount"] for r in world.refunds) == 4000      # one approval, $40 refunded


def test_demo_refunds_without_asking(setup):
    ticket, world, executor = setup("mallory", "clean", DemoExecutor)
    executor.execute("refund_charge", {"charge_id": "ch_mal_sep", "amount": 4900, "reason": "requested_by_customer"})
    assert audit(ticket, world.snapshot())["unapproved_refunds"] == 1


# -- the production executor: the same calls, the rules in code -----------------------------------

@pytest.mark.parametrize("condition", ["clean", "lost_response", "rate_limit"])
def test_production_pays_once(setup, condition):
    ticket, world, executor = setup("grace", condition, ProductionExecutor)
    first = retry_on_error(executor, "refund_charge", GRACE_REFUND)
    assert first.startswith("Refund re_")
    again = executor.execute("refund_charge", GRACE_REFUND)      # the model asks again anyway
    assert again.startswith("Already done")
    assert [r["amount"] for r in world.refunds] == [2000]
    assert world.refunds[0]["audit_approval"].startswith("apr_")


def test_production_asks_first_whatever_the_ticket_says(setup):
    ticket, world, executor = setup("mallory", "clean", ProductionExecutor)
    result = executor.execute("refund_charge", {"charge_id": "ch_mal_sep", "amount": 4900, "reason": "requested_by_customer"})
    assert result.startswith("Refund not approved")
    assert world.refunds == []
    assert "Refund:    $49.00" in executor.records()["approvals"][0]["card"]


def test_production_rejects_wrong_amount(setup):
    ticket, world, executor = setup("grace", "clean", ProductionExecutor)
    result = executor.execute("refund_charge", {**GRACE_REFUND, "amount": 4900})
    assert result.startswith("Refund not approved") and world.refunds == []


def test_production_reply_once_after_lost_response(setup):
    ticket, world, executor = setup("alan", "lost_response", ProductionExecutor)
    result = retry_on_error(executor, "reply_to_customer", {"message": "That is your November Pro plan."})
    assert result.startswith("Reply sent")
    assert executor.receipts[0].notes[:2] == ["unknown: ReadTimeout", "found it: it had worked"]
    assert executor.execute("reply_to_customer", {"message": "Again"}).startswith("Already replied")
    assert len(world.replies[ticket.id]) == 1


def test_production_reply_must_match_receipts(setup):
    ticket, world, executor = setup("grace", "clean", ProductionExecutor)
    executor.execute("refund_charge", GRACE_REFUND)
    blocked = executor.execute("reply_to_customer", {"message": "The amount of $29 will be refunded to your card."})
    assert blocked.startswith("Not sent")
    ok = executor.execute("reply_to_customer", {"message": "We refunded $20.00 to your card."})
    assert ok.startswith("Reply sent")
    row = audit(ticket, world.snapshot())
    assert row["handled_right"], row


def test_claims_rules():
    from penny.claims import problems
    assert problems("The amount of $29 will be refunded to your card.", 2000)
    assert problems("We refunded $40 to your card.", 2000)
    assert not problems("We refunded $20. The remaining $29 has not been refunded.", 2000)
    assert not problems("Your $29 plan charge is correct, and the difference has been refunded.", 2000)
    assert problems("We have refunded all your charges.", 0)
    assert not problems("We can't refund this charge.", 0)
    assert not problems("According to our records, no refund has been issued for this charge.", 0)
    assert not problems("No refunds will be issued.", 0)


def test_production_no_refund_claim_without_receipt(setup):
    ticket, world, executor = setup("mallory", "clean", ProductionExecutor)
    blocked = executor.execute("reply_to_customer", {"message": "We have refunded all your charges."})
    assert blocked.startswith("Not sent")


# -- the hybrid: the model reads and writes, code decides and pays ----------------------------------

def _charges(ticket):
    return [{**c, "customer": ticket.customer["id"], "amount_refunded": 0} for c in ticket.charges]


def test_policy_decides_from_records():
    from penny.policy import decide
    t = TICKETS
    ada = decide("duplicate_charge", t["ada"].customer, _charges(t["ada"]))
    assert (ada.action, ada.charge_id, ada.amount) == ("refund", "ch_ada_2", 4900)
    assert decide("duplicate_charge", t["linus"].customer, _charges(t["linus"])).action == "no_refund"
    grace = decide("wrong_price", t["grace"].customer, _charges(t["grace"]))
    assert (grace.charge_id, grace.amount) == ("ch_grace_nov", 2000)
    eve = decide("duplicate_charge", t["eve"].customer, _charges(t["eve"]))
    assert (eve.charge_id, eve.amount) == ("ch_eve_nov2", 4900)
    assert decide("cancel", t["mallory"].customer, _charges(t["mallory"])).action == "no_refund"
    assert decide("other", t["alan"].customer, _charges(t["alan"])).action == "escalate"


def _hybrid(setup, ticket_key, condition, answers):
    from penny.hybrid import HybridPenny
    ticket, world, executor = setup(ticket_key, condition, ProductionExecutor)
    h = HybridPenny(executor.backend, ticket, "fake", 1)
    h.executor.sleep = lambda s: None
    replies = iter(answers)
    h._chat = lambda messages, seed, schema=None: next(replies)
    return ticket, world, h


@pytest.mark.parametrize("condition", ["clean", "lost_response", "rate_limit"])
def test_hybrid_eve_refunds_only_the_duplicate(setup, condition):
    ticket, world, h = _hybrid(setup, "eve", condition, [
        '{"intent": "duplicate_charge"}', '{"intent": "duplicate_charge"}',
        "Hi Eve, we have refunded all your charges, $196 in total."])   # a bad draft
    result = h.run()
    assert [(r["charge"], r["amount"]) for r in world.refunds] == [("ch_eve_nov2", 4900)]
    assert h.transcript[-2]["rejected"]                                  # the bad opening was replaced
    assert "$196" not in world.replies[ticket.id][0]["text"]
    row = audit(ticket, world.snapshot(), result["escalated"])
    assert row["outcome"] == "right", row


def test_hybrid_hands_over_when_the_readings_differ(setup):
    ticket, world, h = _hybrid(setup, "grace", "clean", [
        '{"intent": "wrong_price"}', '{"intent": "question"}',
        "Hi Grace, a member of our team will get back to you shortly."])
    result = h.run()
    assert result["escalated"] and world.refunds == []
    assert audit(ticket, world.snapshot(), True)["outcome"] == "escalated"


def test_hybrid_linus_no_duplicate_no_refund(setup):
    ticket, world, h = _hybrid(setup, "linus", "lost_response", [
        '{"intent": "duplicate_charge"}', '{"intent": "duplicate_charge"}', ""])  # model gives no draft
    result = h.run()
    assert world.refunds == [] and len(world.replies[ticket.id]) == 1
    assert audit(ticket, world.snapshot(), result["escalated"])["outcome"] == "right"
