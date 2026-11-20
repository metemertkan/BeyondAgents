"""Episode 5: the LLM judge reads the first five runs of every ticket, for every version.

    uv run --group evals python -m scripts.ep05_judge

DeepEval's G-Eval with gpt-oss:20b on the local Ollama (see gate/judge.py). Results are appended
to results/ep05/judged.jsonl; runs already judged are skipped.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from gate.judge import JUDGE, judge, metric
from gate.versions import VERSIONS

JUDGED_SEEDS = 5


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default="results/ep05/runs.jsonl")
    ap.add_argument("--out", default="results/ep05/judged.jsonl")
    ap.add_argument("--versions", default=",".join(VERSIONS))
    a = ap.parse_args()
    out = Path(a.out)
    done = {(r["version"], r["ticket"], r["seed"]) for r in map(json.loads, out.read_text().splitlines())} \
        if out.exists() else set()
    wanted = a.versions.split(",")
    rows = [json.loads(line) for line in Path(a.runs).read_text().splitlines()]
    todo = [r for r in rows if r["version"] in wanted and r["seed"] in VERSIONS[r["version"]].seeds[:JUDGED_SEEDS]
            and (r["version"], r["ticket"], r["seed"]) not in done]
    # Seed by seed across versions, like the runs.
    todo.sort(key=lambda r: (VERSIONS[r["version"]].seeds.index(r["seed"]), r["version"], r["ticket"]))
    print(f"{len(todo)} runs to judge with {JUDGE}", flush=True)
    m = metric()
    for i, r in enumerate(todo, 1):
        started = time.time()
        result = judge(r, m)
        row = {"version": r["version"], "ticket": r["ticket"], "seed": r["seed"], "judge": JUDGE,
               "score": result["score"], "reason": result["reason"], "seconds": round(time.time() - started, 1),
               "outcome": r["outcome"]}
        with out.open("a") as f:
            f.write(json.dumps(row) + "\n")
        print(f"[{i}/{len(todo)}] {r['version']:13s} {r['ticket']:8s} seed={r['seed']:<3d} {row['seconds']:6.1f}s "
              f"score={row['score']:.2f} ({r['outcome']}) {row['reason'][:120]!r}", flush=True)


if __name__ == "__main__":
    main()
