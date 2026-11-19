"""Penny's month-end job, four ways. One worker process; it may die at any planned moment.

    python -m month_end.worker --design poc --services http://127.0.0.1:PORT --state DIR

poc            a loop with a progress file: a customer counts as done when the whole customer is done
checkpoint     a LangGraph graph with a SQLite checkpointer, defaults (durability "async")
durable        a DBOS workflow: every step's result is recorded; a step that was running when the
               process died runs again
durable_keys   what I'd build: the DBOS workflow, plus a key for every step that touches the world
               (the approval request, the refund, the reply), so running a step again is harmless

For every customer: decide the refund (the model), ask a person to approve it, refund, reply.
Environment: CRASH_PLAN (JSON list of [customer, point]), ATTEMPT, MODEL, SEED, DECIDER (llm|rule).
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.request

import httpx

from month_end.data import BY_ID, CUSTOMERS, right_refund

OLLAMA = "http://localhost:11434/api/chat"
JOB = "november-overcharge"
THINK = {"qwen3:8b": False, "gpt-oss:20b": "medium"}


class Job:
    def __init__(self, services: str, state: str):
        self.http = httpx.Client(base_url=services, timeout=60)
        self.state = state
        self.attempt = int(os.environ.get("ATTEMPT", "1"))
        self.plan = {tuple(p) for p in json.loads(os.environ.get("CRASH_PLAN", "[]"))}
        self.fired_path = os.path.join(state, "fired.json")

    # -- dying on purpose ------------------------------------------------------------------------

    def maybe_crash(self, customer: str, point: str) -> None:
        fired = json.load(open(self.fired_path)) if os.path.exists(self.fired_path) else []
        if (customer, point) in self.plan and [customer, point] not in fired:
            fired.append([customer, point])
            json.dump(fired, open(self.fired_path, "w"))
            os._exit(137)   # like kill -9: nothing gets cleaned up, nothing gets flushed

    # -- the model decides ----------------------------------------------------------------------

    def decide(self, customer: str) -> float:
        c = BY_ID[customer]
        if os.environ.get("DECIDER", "llm") == "rule":
            amount = right_refund(customer)
        else:
            model = os.environ.get("MODEL", "qwen3:8b")
            body = {"model": model, "stream": False, "think": THINK.get(model, False),
                    "format": {"type": "object", "properties": {"refund_usd": {"type": "number"}},
                               "required": ["refund_usd"]},
                    "options": {"seed": int(os.environ.get("SEED", "1")) * 100 + self.attempt, "num_predict": 2048},
                    "messages": [{"role": "system", "content":
                                  "You are Penny, Acme Cloud's billing assistant. Decide the November refund for one "
                                  "customer. Acme's rule: if a customer was charged more than their plan price, refund "
                                  "the difference; otherwise refund nothing. Answer with JSON: {\"refund_usd\": number}."},
                                 {"role": "user", "content": f"{c['name']} is on the {c['plan']} plan "
                                  f"(${c['plan_usd']:.2f} a month). Their November charge was ${c['charged_usd']:.2f}."}]}
            req = urllib.request.Request(OLLAMA, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=1800) as r:
                content = json.loads(r.read())["message"].get("content", "{}")
            try:
                amount = round(float(json.loads(content).get("refund_usd", 0)), 2)
            except (ValueError, TypeError, AttributeError):
                amount = 0.0
        with open(os.path.join(self.state, "decisions.jsonl"), "a") as f:
            f.write(json.dumps({"customer": customer, "attempt": self.attempt, "refund_usd": amount}) + "\n")
        return amount

    # -- the world ------------------------------------------------------------------------------

    def request_approval(self, customer: str, amount: float, key: str | None = None) -> str:
        return self.http.post("/approvals", json={"customer": customer, "amount_usd": amount,
                                                  **({"client_key": key} if key else {})}).json()["id"]

    def wait_approval(self, aid: str) -> str:
        while True:
            status = self.http.get(f"/approvals/{aid}").json()["status"]
            if status != "pending":
                return status
            time.sleep(0.25)

    def refund(self, customer: str, amount: float, key: str | None = None) -> dict:
        r = self.http.post("/refunds", json={"customer": customer, "amount_usd": amount},
                           headers={"Idempotency-Key": key} if key else {})
        return {"status": r.status_code, **r.json()}

    def reply(self, customer: str, text: str, key: str | None = None) -> None:
        if key and any(m["metadata"].get("key") == key
                       for m in self.http.get("/replies", params={"customer": customer}).json()["data"]):
            return   # already sent before the crash
        self.http.post("/replies", json={"customer": customer, "text": text, "metadata": {"key": key} if key else {}})


def reply_text(customer: str, outcome: str, amount: float) -> str:
    c = BY_ID[customer]
    if outcome == "refunded":
        return f"Hi {c['name']}, we refunded ${amount:.2f} for November's overcharge."
    if outcome == "no_refund":
        return f"Hi {c['name']}, your November charge of ${c['charged_usd']:.2f} is right for your plan."
    return f"Hi {c['name']}, we're looking into November's invoice; a colleague will follow up."


# -- 1. the PoC ---------------------------------------------------------------------------------

def run_poc(job: Job) -> None:
    path = os.path.join(job.state, "progress.json")
    done = json.load(open(path)) if os.path.exists(path) else []
    for c in CUSTOMERS:
        cid = c["id"]
        if cid in done:
            continue
        amount = job.decide(cid)
        job.maybe_crash(cid, "after_decide")
        outcome = "no_refund"
        if amount > 0:
            aid = job.request_approval(cid, amount)
            job.maybe_crash(cid, "after_approval_request")
            if job.wait_approval(aid) == "approved":
                r = job.refund(cid, amount)
                job.maybe_crash(cid, "after_refund")
                outcome = "refunded" if r["status"] == 200 else "failed"
            else:
                outcome = "failed"
        job.reply(cid, reply_text(cid, outcome, amount))
        job.maybe_crash(cid, "after_reply")
        done.append(cid)
        json.dump(done, open(path, "w"))


# -- 2. checkpoints (LangGraph) -----------------------------------------------------------------

def run_checkpoint(job: Job) -> None:
    import sqlite3
    from typing import TypedDict

    from langgraph.checkpoint.sqlite import SqliteSaver
    from langgraph.graph import END, START, StateGraph

    class S(TypedDict, total=False):
        i: int
        amount: float
        aid: str
        status: str
        outcome: str

    def cid(s):
        return CUSTOMERS[s["i"]]["id"]

    def decide(s):
        amount = job.decide(cid(s))
        job.maybe_crash(cid(s), "after_decide")
        return {"amount": amount, "aid": "", "status": "", "outcome": "no_refund"}

    def request(s):
        if s["amount"] <= 0:
            return {}
        aid = job.request_approval(cid(s), s["amount"])
        job.maybe_crash(cid(s), "after_approval_request")
        return {"aid": aid}

    def wait(s):
        return {"status": job.wait_approval(s["aid"])} if s.get("aid") else {}

    def refund(s):
        if s.get("status") == "approved":
            r = job.refund(cid(s), s["amount"])
            job.maybe_crash(cid(s), "after_refund")
            return {"outcome": "refunded" if r["status"] == 200 else "failed"}
        return {"outcome": "failed"} if s.get("status") == "rejected" else {}

    def reply(s):
        job.reply(cid(s), reply_text(cid(s), s["outcome"], s["amount"]))
        job.maybe_crash(cid(s), "after_reply")
        return {}

    def advance(s):
        return {"i": s["i"] + 1}

    g = StateGraph(S)
    for name, fn in (("decide", decide), ("request", request), ("wait", wait), ("refund", refund),
                     ("reply", reply), ("advance", advance)):
        g.add_node(name, fn)
    g.add_edge(START, "decide")
    for a, b in (("decide", "request"), ("request", "wait"), ("wait", "refund"), ("refund", "reply"), ("reply", "advance")):
        g.add_edge(a, b)
    g.add_conditional_edges("advance", lambda s: "decide" if s["i"] < len(CUSTOMERS) else END)
    saver = SqliteSaver(sqlite3.connect(os.path.join(job.state, "langgraph.sqlite"), check_same_thread=False))
    app = g.compile(checkpointer=saver)
    cfg = {"configurable": {"thread_id": JOB}, "recursion_limit": 500}
    snapshot = app.get_state(cfg)
    if not snapshot.values:
        app.invoke({"i": 0}, cfg)           # first run
    elif snapshot.values.get("i", 0) < len(CUSTOMERS):
        # Resume from the last checkpoint. Not `if snapshot.next`: after a crash before the first
        # step's checkpoint, get_state reports next=() with the start still pending.
        app.invoke(None, cfg)


# -- 3 and 4. a durable workflow (DBOS) ---------------------------------------------------------

def run_durable(job: Job, keys: bool) -> None:
    from dbos import DBOS, SetWorkflowID

    DBOS(config={"name": "month-end-keys" if keys else "month-end",
                 "system_database_url": f"sqlite:///{os.path.join(job.state, 'dbos.sqlite')}"})
    k = (lambda cid, step: f"{JOB}:{cid}:{step}") if keys else (lambda cid, step: None)

    @DBOS.step()
    def decide_step(cid: str) -> float:
        amount = job.decide(cid)
        job.maybe_crash(cid, "after_decide")
        return amount

    @DBOS.step()
    def request_step(cid: str, amount: float) -> str:
        aid = job.request_approval(cid, amount, k(cid, "approval"))
        job.maybe_crash(cid, "after_approval_request")
        return aid

    @DBOS.step()
    def wait_step(aid: str) -> str:
        return job.wait_approval(aid)

    @DBOS.step()
    def refund_step(cid: str, amount: float) -> int:
        r = job.refund(cid, amount, k(cid, "refund"))
        job.maybe_crash(cid, "after_refund")
        return r["status"]

    @DBOS.step()
    def reply_step(cid: str, text: str) -> None:
        job.reply(cid, text, k(cid, "reply"))
        job.maybe_crash(cid, "after_reply")

    @DBOS.workflow()
    def month_end() -> None:
        for c in CUSTOMERS:
            cid = c["id"]
            amount = decide_step(cid)
            outcome = "no_refund"
            if amount > 0:
                status = wait_step(request_step(cid, amount))
                outcome = ("refunded" if refund_step(cid, amount) == 200 else "failed") if status == "approved" else "failed"
            reply_step(cid, reply_text(cid, outcome, amount))

    DBOS.launch()                           # picks up the workflow the last process left behind
    with SetWorkflowID(JOB):
        DBOS.start_workflow(month_end).get_result()
    DBOS.destroy()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--design", required=True, choices=["poc", "checkpoint", "durable", "durable_keys"])
    ap.add_argument("--services", required=True)
    ap.add_argument("--state", required=True)
    a = ap.parse_args()
    job = Job(a.services, a.state)
    if a.design == "poc":
        run_poc(job)
    elif a.design == "checkpoint":
        run_checkpoint(job)
    else:
        run_durable(job, keys=a.design == "durable_keys")


if __name__ == "__main__":
    main()
