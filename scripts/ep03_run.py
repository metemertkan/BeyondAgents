"""Episode 3 batch: Penny with each memory design, in each scenario, with each model.

    uv run python -m scripts.ep03_run --models qwen3:8b --repeats 1   # a quick look
    uv run python -m scripts.ep03_run                                 # the full batch

Every run starts with an empty memory. Mem0 extracts memories with qwen3:8b in every run (a memory
layer usually runs on a small model); Penny's own model is the one under test.
Results are appended to a JSONL file; runs already in it are skipped.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import warnings
from pathlib import Path

os.environ.setdefault("MEM0_TELEMETRY", "False")

from recall.agent import conversation   # noqa: E402
from recall.designs import DESIGNS      # noqa: E402
from recall.scenarios import FORGET, SCENARIOS, score   # noqa: E402
from recall.world import World          # noqa: E402

THINK = {"qwen3:8b": False, "gpt-oss:20b": "medium"}


def one_run(model: str, design: str, scenario: str, seed: int) -> dict:
    world = World(design)
    conversations, dumps_after_forget = [], None
    try:
        steps = SCENARIOS[scenario]
        for i, (who, step) in enumerate(steps):
            if who == FORGET:
                world.forget(step)
                dumps_after_forget = {**world.design.dump(),
                                      "crm pending changes": json.dumps(world.crm.pending)}
                continue
            conversations.append(conversation(world, who, step, model, seed, THINK.get(model, False),
                                              save=i < len(steps) - 1))
        result = score(scenario, conversations, world, dumps_after_forget)
        final_dump = world.design.dump()
    finally:
        world.close()
    return {"model": model, "design": design, "scenario": scenario, "seed": seed, **result,
            "seconds": round(sum(c["seconds"] + c["memory_seconds"] for c in conversations), 1),
            "memory_seconds": round(sum(c["memory_seconds"] for c in conversations), 1),
            "conversations": conversations, "refunds": world.refunds, "store_after": final_dump,
            "store_after_forget": dumps_after_forget, "crm_pending": world.crm.pending,
            "mem0_adds": getattr(world.design, "adds", None)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="qwen3:8b,gpt-oss:20b")
    ap.add_argument("--designs", default=",".join(DESIGNS))
    ap.add_argument("--scenarios", default=",".join(SCENARIOS))
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--out", default="results/ep03/runs.jsonl")
    a = ap.parse_args()
    logging.disable(logging.CRITICAL)
    warnings.simplefilter("ignore")

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if out.exists():
        for line in out.read_text().splitlines():
            r = json.loads(line)
            done.add((r["model"], r["design"], r["scenario"], r["seed"]))
    jobs = [(m, d, sc, s) for m in a.models.split(",") for s in range(1, a.repeats + 1)
            for sc in a.scenarios.split(",") for d in a.designs.split(",")]
    todo = [j for j in jobs if j not in done]
    print(f"{len(jobs)} runs, {len(jobs) - len(todo)} already done", flush=True)
    for i, (m, d, sc, s) in enumerate(todo, 1):
        row = one_run(m, d, sc, s)
        with out.open("a") as f:
            f.write(json.dumps(row) + "\n")
        print(f"[{i}/{len(todo)}] {m:12s} {d:12s} {sc:8s} seed={s} {row['seconds']:6.1f}s "
              f"(memory {row['memory_seconds']:5.1f}s) shown_poison={row['poison_shown']} "
              f"told={row['told_fake_policy']} refunded={row['refunded']} leaked={row['leaked']} "
              f"traces={row['traces_after_forget']} helped={row['used_preference']} mistake={row['mistake']}",
              flush=True)


if __name__ == "__main__":
    main()
