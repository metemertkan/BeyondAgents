"""Episode 3 tables from results/ep03/runs.jsonl (+ drill.json) -> results/ep03/summary.md and summary.json.

    uv run python -m scripts.ep03_summary
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

DESIGNS = ("notebook", "mem0_user", "mem0_shared", "owned")
NAMES = {"notebook": "Learning notebook (PoC)", "mem0_user": "Mem0, per customer", "mem0_shared": "Mem0, shared",
         "owned": "Memory with an owner (what I'd build)"}


def frac(rows, key) -> str:
    return f"{sum(bool(r[key]) for r in rows)} / {len(rows)}" if rows else "–"


def stats(rows: list[dict]) -> dict:
    by = lambda s: [r for r in rows if r["scenario"] == s]
    harm = [r for r in rows if r["mistake"] is not None]
    return {
        "harm_runs": len(harm), "mistakes": sum(bool(r["mistake"]) for r in harm),
        "poison_shown": frac(by("poison"), "poison_shown"), "told_fake_policy": frac(by("poison"), "told_fake_policy"),
        "refunded_poison": frac(by("poison"), "refunded"), "refunded_control": frac(by("control"), "refunded"),
        "leak": frac(by("leak"), "leaked"), "whose": frac(by("whose"), "leaked"),
        "forget_leak": frac(by("forget"), "leaked"), "forget_traces": frac(by("forget"), "traces_after_forget"),
        "helped": frac(by("helpful"), "used_preference"),
        "seconds": round(sum(r["seconds"] for r in rows) / max(len(rows), 1)),
        "memory_seconds": round(sum(r["memory_seconds"] for r in rows) / max(len(rows), 1)),
    }


def table(groups: dict[str, dict], title: str) -> list[str]:
    lines = [f"### {title}", "",
             "| | Mistakes | Fake policy in Ada's memory | Ada told the fake policy | Ada refunded (poison) | "
             "Ada refunded (no poison) | Ada's address to Mallory | …as Mallory's own | …after deleting Ada | "
             "Ada's address left after deleting | Grace's preference used | s/run |",
             "| :--- |" + " ---: |" * 11]
    for name, s in groups.items():
        lines.append(f"| {name} | {s['mistakes']} / {s['harm_runs']} | {s['poison_shown']} | {s['told_fake_policy']} | "
                     f"{s['refunded_poison']} | {s['refunded_control']} | {s['leak']} | {s['whose']} | "
                     f"{s['forget_leak']} | {s['forget_traces']} | {s['helped']} | {s['seconds']} |")
    return lines + [""]


def main() -> None:
    rows = [json.loads(line) for line in Path("results/ep03/runs.jsonl").read_text().splitlines()]
    by = defaultdict(list)
    for r in rows:
        by[("all", r["design"])].append(r)
        by[(r["model"], r["design"])].append(r)
    summary = {" / ".join(k): stats(v) for k, v in by.items()}
    md = ["# Episode 3 results", "",
          f"{len(rows)} runs. Every run starts with an empty memory. Mistakes are harm the memory caused, in the "
          "poison, leak, whose and forget scenarios; the control runs (Ada asks with an empty memory) are the "
          "baseline for refunds, and the helpful runs measure whether memory still helps.", ""]
    for scope in ("all", *sorted({r["model"] for r in rows})):
        groups = {NAMES[d]: summary[f"{scope} / {d}"] for d in DESIGNS if f"{scope} / {d}" in summary}
        md += table(groups, "All runs" if scope == "all" else scope)
    drill = Path("results/ep03/drill.json")
    if drill.exists():
        md += ["### Deletion drill, no model (`scripts/ep03_drill.py`)", "",
               "| Memory design | Ada's new address stored in | Still there after deleting Ada |", "| :--- | :--- | :--- |"]
        for d in json.loads(drill.read_text()):
            md.append(f"| {NAMES[d['design']]} | {', '.join(d['stored_in_before'])} | "
                      f"{', '.join(d['still_in_after_delete']) or 'nowhere'} |")
        md.append("")
    Path("results/ep03/summary.md").write_text("\n".join(md))
    Path("results/ep03/summary.json").write_text(json.dumps(summary, indent=2))
    print("\n".join(md))


if __name__ == "__main__":
    main()
