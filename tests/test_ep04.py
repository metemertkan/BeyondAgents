"""Episode 4 without a model: the services, the crash hook, and the designs under one crash plan."""
import json

import httpx
import pytest

from month_end.data import AFFECTED, right_refund
from month_end.services import Ledger, create_app
from portal.servers import Served, free_port
from scripts.ep04_run import crash_plan, one_job


@pytest.fixture
def services():
    ledger, port = Ledger(), free_port()
    served = Served(create_app(ledger), port)
    yield ledger, httpx.Client(base_url=f"http://127.0.0.1:{port}")
    served.stop()


def test_partial_refund_twice_is_allowed_but_not_with_a_key(services):
    ledger, http = services
    assert http.post("/refunds", json={"customer": "c01", "amount_usd": 20}).status_code == 200
    assert http.post("/refunds", json={"customer": "c01", "amount_usd": 20}).status_code == 200   # $40 of $49
    assert http.post("/refunds", json={"customer": "c01", "amount_usd": 20}).status_code == 400   # over the charge
    first = http.post("/refunds", json={"customer": "c03", "amount_usd": 20}, headers={"Idempotency-Key": "k"})
    again = http.post("/refunds", json={"customer": "c03", "amount_usd": 20}, headers={"Idempotency-Key": "k"})
    assert again.json() == first.json() and again.headers["Idempotent-Replayed"] == "true"
    assert sum(r["amount_usd"] for r in ledger.refunds if r["customer"] == "c03") == 20


def test_approval_client_key_makes_one_request(services):
    ledger, http = services
    a = http.post("/approvals", json={"customer": "c01", "amount_usd": 20, "client_key": "x"}).json()
    b = http.post("/approvals", json={"customer": "c01", "amount_usd": 20, "client_key": "x"}).json()
    assert a["id"] == b["id"] and len(ledger.approvals) == 1


def test_crash_plans_hit_every_window():
    for seed in range(1, 6):
        plan = crash_plan(seed)
        assert [p for _, p in plan] == ["after_decide", "after_approval_request", "after_refund", "after_reply"]
        assert all(c in AFFECTED for c, p in plan if p in ("after_approval_request", "after_refund"))
    assert crash_plan(0) == []


@pytest.mark.parametrize("design,extra_refunds", [("durable", 1), ("durable_keys", 0)])
def test_durable_workflow_with_and_without_keys(design, extra_refunds):
    job = one_job("rule", design, plan_seed=1, decider="rule")
    assert job["finished"] and job["runs_of_worker"] == 5            # four planned crashes, then done
    assert job["extra_refund_customers"] == extra_refunds
    assert job["missing_replies"] == 0 and job["missing_refund_customers"] == 0
    if design == "durable_keys":
        assert job["mistakes"] == 0 and job["extra_approval_requests"] == 0
        assert all(p["refunded"] == right_refund(c) and p["replies"] == 1 for c, p in job["per_customer"].items())


def test_poc_redoes_the_whole_customer():
    job = one_job("rule", "poc", plan_seed=1, decider="rule")
    assert job["extra_refund_customers"] >= 1 and job["extra_approval_requests"] >= 2
