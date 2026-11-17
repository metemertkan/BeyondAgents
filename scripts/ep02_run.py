"""Episode 2 batch: Penny with each kind of tool access, in each scenario, with each model.

    uv run python -m scripts.ep02_run --models qwen3:8b --repeats 1   # a quick look
    uv run python -m scripts.ep02_run                                 # the full batch

Every run gets a fresh world: Acme's IdP, billing API and billing MCP server, and Eve's FX4Free.
Results are appended to a JSONL file; runs already in it are skipped.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import warnings
from pathlib import Path

from portal import access as access_mod
from portal.agent import SCENARIOS, run
from portal.score import score
from portal.world import World

ARCHS = ("master_key", "mcp_shortcut", "mcp_strict", "utcp_agent_key", "utcp_user_token", "broker")
THINK = {"qwen3:8b": False, "gpt-oss:20b": "medium"}


async def one_run(model: str, arch: str, scenario: str, seed: int) -> dict:
    user = SCENARIOS[scenario][0]
    with World(access_mod.WORLD_MODE.get(arch, "shortcut")) as world:
        access = access_mod.make(arch, world, user)
        await access.open()
        try:
            result = await run(scenario, access, model, seed, THINK.get(model, False))
        finally:
            await access.close()
        row = {"model": model, "arch": arch, "scenario": scenario, "user": user, "seed": seed,
               **score(scenario, user, access, world), **result,
               "billing_audit": world.billing.audit, "eve_log": world.eve.log,
               "tokens_issued": world.idp.issued}
        if hasattr(access, "exchanges"):
            row["exchanges"] = access.exchanges
    return row


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="qwen3:8b,gpt-oss:20b")
    ap.add_argument("--archs", default=",".join(ARCHS))
    ap.add_argument("--scenarios", default=",".join(SCENARIOS))
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--out", default="results/ep02/runs.jsonl")
    a = ap.parse_args()
    logging.disable(logging.CRITICAL)
    warnings.simplefilter("ignore")

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if out.exists():
        for line in out.read_text().splitlines():
            r = json.loads(line)
            done.add((r["model"], r["arch"], r["scenario"], r["seed"]))
    jobs = [(m, ar, sc, s) for m in a.models.split(",") for s in range(1, a.repeats + 1)
            for sc in a.scenarios.split(",") for ar in a.archs.split(",")]
    todo = [j for j in jobs if j not in done]
    print(f"{len(jobs)} runs, {len(jobs) - len(todo)} already done", flush=True)
    for i, (m, ar, sc, s) in enumerate(todo, 1):
        row = asyncio.run(one_run(m, ar, sc, s))
        with out.open("a") as f:
            f.write(json.dumps(row) + "\n")
        print(f"[{i}/{len(todo)}] {m:12s} {ar:16s} {sc:13s} seed={s} {row['seconds']:6.1f}s "
              f"other={row['other_customer_data']} refund={row['unauthorized_refund']} "
              f"to_eve={row['private_to_eve']} replay={row['eve_replay_got_data']} done={row['task_done']} "
              f"mistake={row['mistake']}", flush=True)


if __name__ == "__main__":
    main()
