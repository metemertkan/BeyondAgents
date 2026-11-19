"""Episode 4 batch: the month-end job, crashed on schedule, for each design and model.

    uv run python -m scripts.ep04_run --models qwen3:8b --plans 0,1        # a quick look
    uv run python -m scripts.ep04_run                                       # the full batch

A crash plan kills the worker four times, once in each place a step's work is done but not yet
written down: after a decision, after asking for approval, after a refund, after a reply (plan 0
never crashes). The same plans are used for every design and model. A supervisor restarts the
worker until the job finishes, like a deployment or a restarting pod would.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
import tempfile
import time
from collections import Counter, defaultdict
from pathlib import Path

from month_end.data import AFFECTED, CUSTOMERS, right_refund
from month_end.services import Ledger, create_app
from portal.servers import Served, free_port

DESIGNS = ("poc", "checkpoint", "durable", "durable_keys")
HERE = Path(__file__).resolve().parent.parent


def crash_plan(seed: int) -> list[list[str]]:
    """One crash in each place: after a decision, an approval request, a refund and a reply."""
    if seed == 0:
        return []
    rng = random.Random(seed)
    everyone = [c["id"] for c in CUSTOMERS]
    return [[rng.choice(everyone), "after_decide"], [rng.choice(AFFECTED), "after_approval_request"],
            [rng.choice(AFFECTED), "after_refund"], [rng.choice(everyone), "after_reply"]]


def score(ledger_state: dict, decisions: list[dict]) -> dict:
    refunds, replies, approvals = defaultdict(float), Counter(), Counter()
    for r in ledger_state["refunds"]:
        refunds[r["customer"]] += r["amount_usd"]
    for m in ledger_state["replies"]:
        replies[m["customer"]] += 1
    for a in ledger_state["approvals"]:
        approvals[a["customer"]] += 1
    seen = defaultdict(list)
    for d in decisions:
        seen[d["customer"]].append(d["refund_usd"])
    per = {}
    for c in CUSTOMERS:
        cid, right = c["id"], right_refund(c["id"])
        got = round(refunds[cid], 2)
        per[cid] = {"refunded": got, "right": right, "replies": replies[cid], "approvals": approvals[cid],
                    "decisions": seen[cid]}
    extra = {cid: round(p["refunded"] - p["right"], 2) for cid, p in per.items() if p["refunded"] > p["right"] + 0.005}
    return {
        "extra_refund_customers": len(extra), "extra_refund_usd": round(sum(extra.values()), 2),
        "missing_refund_customers": sum(1 for p in per.values() if p["right"] > 0 and p["refunded"] < p["right"] - 0.005),
        "duplicate_replies": sum(1 for p in per.values() if p["replies"] > 1),
        "missing_replies": sum(1 for p in per.values() if p["replies"] == 0),
        "extra_approval_requests": sum(max(0, p["approvals"] - 1) for p in per.values()),
        "changed_mind": sum(1 for p in per.values() if len(set(p["decisions"])) > 1),
        "model_wrong": sum(1 for p in per.values() if p["decisions"] and p["decisions"][0] != p["right"]),
        "decisions_made": len(decisions),
        # A mistake is a customer the crashes hurt: paid too much, or not told exactly once.
        "mistakes": sum(1 for cid, p in per.items() if cid in extra or p["replies"] != 1),
        "per_customer": per,
    }


def one_job(model: str, design: str, plan_seed: int, decider: str = "llm", max_restarts: int = 12) -> dict:
    ledger = Ledger()
    port = free_port()
    served = Served(create_app(ledger), port)
    state = tempfile.mkdtemp(prefix=f"ep04_{design}_")
    plan = crash_plan(plan_seed)
    started, attempts, exits = time.time(), 0, []
    try:
        while attempts < max_restarts:
            attempts += 1
            env = {**os.environ, "CRASH_PLAN": json.dumps(plan), "ATTEMPT": str(attempts), "MODEL": model,
                   "SEED": str(max(plan_seed, 1)), "DECIDER": decider, "DBOS__APPVERSION": "ep04",
                   "PYTHONPATH": str(HERE)}
            p = subprocess.run([sys.executable, "-m", "month_end.worker", "--design", design, "--services",
                                f"http://127.0.0.1:{port}", "--state", state], env=env, cwd=HERE,
                               capture_output=True, text=True, timeout=7200)
            exits.append(p.returncode)
            if p.returncode == 0:
                break
            if p.returncode != 137:   # not one of our planned crashes: keep the evidence
                exits[-1] = f"{p.returncode}: {p.stderr[-400:]}"
        decisions_path = os.path.join(state, "decisions.jsonl")
        decisions = [json.loads(line) for line in open(decisions_path)] if os.path.exists(decisions_path) else []
        result = score(ledger.state(), decisions)
    finally:
        served.stop()
    return {"model": model, "design": design, "plan": plan_seed, "crash_plan": plan, "finished": exits[-1] == 0,
            "runs_of_worker": attempts, "exits": exits, "seconds": round(time.time() - started, 1), **result,
            "ledger": ledger.state()}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="qwen3:8b,gpt-oss:20b")
    ap.add_argument("--designs", default=",".join(DESIGNS))
    ap.add_argument("--plans", default="0,1,2,3,4,5")
    ap.add_argument("--decider", default="llm", choices=["llm", "rule"])
    ap.add_argument("--out", default="results/ep04/runs.jsonl")
    a = ap.parse_args()
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if out.exists():
        for line in out.read_text().splitlines():
            r = json.loads(line)
            done.add((r["model"], r["design"], r["plan"]))
    model_list = a.models.split(",") if a.decider == "llm" else ["rule"]
    jobs = [(m, d, int(p)) for m in model_list for p in a.plans.split(",") for d in a.designs.split(",")]
    todo = [j for j in jobs if j not in done]
    print(f"{len(jobs)} jobs, {len(jobs) - len(todo)} already done", flush=True)
    for i, (m, d, p) in enumerate(todo, 1):
        row = one_job(m, d, p, a.decider)
        with out.open("a") as f:
            f.write(json.dumps(row) + "\n")
        print(f"[{i}/{len(todo)}] {m:12s} {d:13s} plan={p} {row['seconds']:6.1f}s worker runs={row['runs_of_worker']} "
              f"finished={row['finished']} extra_refunds={row['extra_refund_customers']} (${row['extra_refund_usd']}) "
              f"dup_replies={row['duplicate_replies']} missing_replies={row['missing_replies']} "
              f"extra_approvals={row['extra_approval_requests']} changed_mind={row['changed_mind']} "
              f"model_wrong={row['model_wrong']} mistakes={row['mistakes']}", flush=True)


if __name__ == "__main__":
    main()
