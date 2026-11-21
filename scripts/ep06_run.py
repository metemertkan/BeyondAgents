"""Episode 6 batch: Penny as two agents, every design, on every ticket, on a clean and a bad day.

    uv run python -m scripts.ep06_run --designs chat --tickets grace --seeds 1     # a quick look
    uv run python -m scripts.ep06_run                                              # the full batch

One run: a fresh world (the stand-in payments and helpdesk APIs), the billing agent behind its own
A2A endpoint, the front desk talking to the customer, and the audit from the APIs' own records.
"lost_handoff": the first hand-off reaches the billing agent and gets done, and its answer never
comes back. Results are appended to a JSONL file; runs already in it are skipped.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from gate.evals import failures
from handoff import loop
from handoff.billing import A2AServer, BillingAgent, llm_brain
from handoff.designs import DESIGNS, MODEL
from handoff.frontdesk import NUDGE, FrontDesk
from penny.audit import audit
from penny.faults import FaultyTransport
from penny.tickets import TICKETS
from penny.tools import Backend
from penny.world import Server, World


def one_run(design_key: str, ticket_key: str, condition: str, seed: int, brain=llm_brain) -> dict:
    design, ticket = DESIGNS[design_key], TICKETS[ticket_key]
    world = World()
    world.load(ticket.customer, [dict(c) for c in ticket.charges])
    started = time.time()
    with Server(world) as api:
        billing = BillingAgent(design, ticket, api.url, seed, brain)
        with A2AServer(billing) as a2a:
            backend = Backend(api.url, FaultyTransport("clean"), ticket)
            try:
                desk = FrontDesk(design, ticket, backend, a2a.card, condition)
                front = loop.run(MODEL, desk.system, desk.first_message(), desk.tools, desk.execute, seed,
                                 nudge=NUDGE, finished=lambda: desk.replied)
            finally:
                backend.close()
        snapshot = world.snapshot()
    worked = [j for j in billing.jobs if not j["replayed"]]
    row = {"design": design_key, "ticket": ticket_key, "condition": condition, "seed": seed, "model": MODEL,
           "seconds": round(time.time() - started, 1),
           "front_model_calls": front["model_calls"], "front_tokens": front["tokens"],
           "billing_model_calls": sum(j["model_calls"] for j in worked),
           "billing_tokens": {"prompt": sum(j["tokens"]["prompt"] for j in worked),
                              "output": sum(j["tokens"]["output"] for j in worked)},
           "handoffs_sent": len(desk.handoffs), "billing_tasks": len(billing.jobs), "billing_work": len(worked),
           "billing_replayed": len(billing.jobs) - len(worked),
           "relayed_approval": any(h["relays_approval"] for h in desk.handoffs),
           "approvals_asked": sum(len(j["approvals"]) for j in worked),
           "approvals_refused": sum(not a["approved"] for j in worked for a in j["approvals"]),
           "blocked_replies": desk.blocked, "server_errors": front["server_errors"] +
           [e for j in worked for e in j["server_errors"]],
           **audit(ticket, snapshot)}
    row["failures"] = sorted(failures(row))
    row["refund_metadata"] = [r.get("metadata", {}) for r in snapshot["refunds"]]
    row["transcript"] = front["transcript"]
    row["handoffs"] = desk.handoffs
    row["billing_jobs"] = [{k: v for k, v in j.items()} for j in billing.jobs]
    return row


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--designs", default=",".join(DESIGNS))
    ap.add_argument("--tickets", default=",".join(TICKETS))
    ap.add_argument("--seeds", default="1,2,3,4,5")
    ap.add_argument("--out", default="results/ep06/runs.jsonl")
    a = ap.parse_args()
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if out.exists():
        for line in out.read_text().splitlines():
            r = json.loads(line)
            done.add((r["design"], r["ticket"], r["condition"], r["seed"]))
    plan = [(int(s), d, c, t) for s in a.seeds.split(",") for d in a.designs.split(",")
            for c in DESIGNS[d].conditions for t in a.tickets.split(",")]
    todo = [(d, t, c, s) for s, d, c, t in plan if (d, t, c, s) not in done]
    print(f"{len(plan)} runs, {len(plan) - len(todo)} already done", flush=True)
    for i, (d, t, c, s) in enumerate(todo, 1):
        row = one_run(d, t, c, s)
        with out.open("a") as f:
            f.write(json.dumps(row) + "\n")
        print(f"[{i}/{len(todo)}] {d:12s} {c:12s} {t:8s} seed={s} {row['seconds']:6.1f}s "
              f"calls={row['front_model_calls']}+{row['billing_model_calls']} sent={row['handoffs_sent']} "
              f"work={row['billing_work']} replayed={row['billing_replayed']} "
              f"refunded={row['refunded_cents']}/{row['right_refund_cents']} replies={row['reply_count']} "
              f"failures={row['failures']} relayed={row['relayed_approval']}", flush=True)


if __name__ == "__main__":
    main()
