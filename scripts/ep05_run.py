"""Episode 5 batch: every version of Penny on every ticket, ten times each.

    uv run python -m scripts.ep05_run --versions baseline --seeds 1      # a quick look
    uv run python -m scripts.ep05_run                                    # the full pool

One run is Episode 1's: a fresh world (the stand-in payments and helpdesk APIs), the production
executor, a clean day, and the audit from the APIs' own records. Results are appended to a JSONL
file; runs already in it are skipped, so an interrupted batch resumes where it stopped.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from gate.versions import VERSIONS
from penny import agent
from penny.audit import audit
from penny.executors import ProductionExecutor
from penny.faults import FaultyTransport
from penny.tickets import TICKETS
from penny.tools import Backend
from penny.world import Server, World

THINK = {"qwen3:8b": False, "qwen3:4b-instruct": False}


def one_run(version_key: str, ticket_key: str, seed: int) -> dict:
    version, ticket = VERSIONS[version_key], TICKETS[ticket_key]
    world = World()
    world.load(ticket.customer, [dict(c) for c in ticket.charges])
    with Server(world) as server:
        backend = Backend(server.url, FaultyTransport("clean"), ticket)
        try:
            executor = ProductionExecutor(backend, ticket)
            result = agent.run(ticket, executor, version.model, seed, THINK.get(version.model, False),
                               system=version.system)
        finally:
            backend.close()
        snapshot = world.snapshot()
    approvals = executor.records()["approvals"]
    return {"version": version_key, "model": version.model, "ticket": ticket_key, "seed": seed,
            "seconds": result["seconds"], "model_calls": result["model_calls"], "tokens": result["tokens"],
            "server_errors": result["server_errors"], "operator_questions": executor.questions,
            "approvals_asked": len(approvals), "approvals_refused": sum(not a["approved"] for a in approvals),
            "blocked_replies": executor.blocked_replies,
            "tools": [e["name"] for e in result["transcript"] if e["type"] == "tool"],
            **audit(ticket, snapshot), "transcript": result["transcript"], "records": executor.records()}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--versions", default=",".join(VERSIONS))
    ap.add_argument("--tickets", default=",".join(TICKETS))
    ap.add_argument("--seeds", default="", help="comma-separated; default: each version's own seeds")
    ap.add_argument("--out", default="results/ep05/runs.jsonl")
    a = ap.parse_args()
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if out.exists():
        for line in out.read_text().splitlines():
            r = json.loads(line)
            done.add((r["version"], r["ticket"], r["seed"]))
    # Seed by seed across all versions, so a stopped batch still compares like with like.
    plan = []
    for v in a.versions.split(","):
        seeds = [int(s) for s in a.seeds.split(",")] if a.seeds else list(VERSIONS[v].seeds)
        for i, s in enumerate(seeds):
            for t in a.tickets.split(","):
                plan.append((i, v, t, s))
    todo = [(v, t, s) for _, v, t, s in sorted(plan) if (v, t, s) not in done]
    print(f"{len(plan)} runs, {len(plan) - len(todo)} already done", flush=True)
    for i, (v, t, s) in enumerate(todo, 1):
        row = one_run(v, t, s)
        with out.open("a") as f:
            f.write(json.dumps(row) + "\n")
        print(f"[{i}/{len(todo)}] {v:13s} {t:8s} seed={s:<3d} {row['seconds']:6.1f}s calls={row['model_calls']:2d} "
              f"{row['outcome']:9s} refunded={row['refunded_cents']}/{row['right_refund_cents']} "
              f"replies={row['reply_count']} blocked={row['blocked_replies']} refused={row['approvals_refused']} "
              f"problems={row['reply_problems'][:1]}", flush=True)


if __name__ == "__main__":
    main()
