"""Episode 1 batch: Penny with each executor, on each ticket, under each condition.

    uv run python -m scripts.ep01_run --models qwen3:8b --repeats 1        # a quick look
    uv run python -m scripts.ep01_run                                      # the full batch

Every run gets a fresh world (the stand-in APIs) and its own executor. Results are appended to
a JSONL file; runs already in it are skipped, so an interrupted batch resumes where it stopped.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from penny import agent
from penny.audit import audit
from penny.executors import DemoExecutor, ProductionExecutor
from penny.faults import CONDITIONS, FaultyTransport
from penny.tickets import TICKETS
from penny.tools import Backend
from penny.world import Server, World

EXECUTORS = {"demo": DemoExecutor, "production": ProductionExecutor}
THINK = {"qwen3:8b": False, "gpt-oss:20b": "medium"}


def one_run(model: str, ticket_key: str, condition: str, executor_name: str, seed: int) -> dict:
    ticket = TICKETS[ticket_key]
    world = World()
    world.load(ticket.customer, [dict(c) for c in ticket.charges])
    with Server(world) as server:
        backend = Backend(server.url, FaultyTransport(condition), ticket)
        executor = EXECUTORS[executor_name](backend, ticket)
        try:
            result = agent.run(ticket, executor, model, seed, THINK.get(model, False))
        finally:
            backend.close()
        snapshot = world.snapshot()
    row = {"model": model, "ticket": ticket_key, "condition": condition, "executor": executor_name,
           "seed": seed, "seconds": result["seconds"], "server_errors": result["server_errors"],
           "operator_questions": executor.questions, **audit(ticket, snapshot),
           "transcript": result["transcript"]}
    if isinstance(executor, ProductionExecutor):
        row["records"] = executor.records()
    return row


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="qwen3:8b,gpt-oss:20b")
    ap.add_argument("--tickets", default=",".join(TICKETS))
    ap.add_argument("--conditions", default=",".join(CONDITIONS))
    ap.add_argument("--executors", default="demo,production")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--out", default="results/ep01/runs.jsonl")
    a = ap.parse_args()

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if out.exists():
        for line in out.read_text().splitlines():
            r = json.loads(line)
            done.add((r["model"], r["ticket"], r["condition"], r["executor"], r["seed"]))

    jobs = [(m, t, c, e, s)
            for m in a.models.split(",")
            for s in range(1, a.repeats + 1)
            for t in a.tickets.split(",")
            for c in a.conditions.split(",")
            for e in a.executors.split(",")]
    todo = [j for j in jobs if j not in done]
    print(f"{len(jobs)} runs, {len(jobs) - len(todo)} already done", flush=True)
    for i, (m, t, c, e, s) in enumerate(todo, 1):
        row = one_run(m, t, c, e, s)
        with out.open("a") as f:
            f.write(json.dumps(row) + "\n")
        print(f"[{i}/{len(todo)}] {m:12s} {t:8s} {c:14s} {e:10s} seed={s} {row['seconds']:6.1f}s "
              f"refunded={row['refunded_cents']}/{row['right_refund_cents']} "
              f"unapproved={row['unapproved_refunds']} replies={row['reply_count']} "
              f"problems={len(row['reply_problems'])} right={row['handled_right']}", flush=True)


if __name__ == "__main__":
    main()
