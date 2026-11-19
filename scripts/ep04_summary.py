"""Episode 4 tables -> results/ep04/summary.md and summary.json.

    uv run python -m scripts.ep04_summary
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

DESIGNS = ("poc", "checkpoint", "durable", "durable_keys")
NAMES = {"poc": "Loop with a progress file (PoC)", "checkpoint": "Checkpoints (LangGraph, defaults)",
         "durable": "Durable workflow (DBOS)", "durable_keys": "Durable workflow + a key per step (what I'd build)"}


def stats(rows: list[dict]) -> dict:
    s = lambda k: sum(r[k] for r in rows)
    return {"jobs": len(rows), "finished": sum(r["finished"] for r in rows), "mistakes": s("mistakes"),
            "extra_refund_customers": s("extra_refund_customers"), "extra_refund_usd": round(s("extra_refund_usd"), 2),
            "duplicate_replies": s("duplicate_replies"), "missing_replies": s("missing_replies"),
            "wrong_replies": sum(r.get("wrong_replies", 0) for r in rows),
            "extra_approval_requests": s("extra_approval_requests"), "changed_mind": s("changed_mind"),
            "missing_refund_customers": s("missing_refund_customers"), "model_wrong": s("model_wrong"),
            "decisions_made": s("decisions_made"), "seconds": round(s("seconds") / max(len(rows), 1))}


def table(groups: dict[str, dict], title: str) -> list[str]:
    lines = [f"### {title}", "",
             "| | Jobs | Mistakes (customers) | Extra refunds | Repeated replies | Missing replies | Untrue replies | "
             "Approval asked again | Model changed its mind | Model decisions | s/job |",
             "| :--- |" + " ---: |" * 10]
    for name, x in groups.items():
        lines.append(f"| {name} | {x['jobs']} | {x['mistakes']} | {x['extra_refund_customers']} (${x['extra_refund_usd']:.0f}) | "
                     f"{x['duplicate_replies']} | {x['missing_replies']} | {x['wrong_replies']} | {x['extra_approval_requests']} | "
                     f"{x['changed_mind']} | {x['decisions_made']} | {x['seconds']} |")
    return lines + [""]


def main() -> None:
    rows = [json.loads(line) for line in Path("results/ep04/runs.jsonl").read_text().splitlines()]
    by = defaultdict(list)
    for r in rows:
        crashed = "crashes" if r["plan"] else "no crash"
        by[(crashed, "all", r["design"])].append(r)
        by[(crashed, r["model"], r["design"])].append(r)
    summary = {" / ".join(k): stats(v) for k, v in by.items()}
    md = ["# Episode 4 results", "",
          f"{len(rows)} jobs: 10 customers each; crash plans 1–5 kill the worker four times (after a decision, an "
          "approval request, a refund and a reply), plan 0 never. Counted in the services' records.", ""]
    for crashed in ("crashes", "no crash"):
        for scope in ("all", *sorted({r["model"] for r in rows})):
            groups = {NAMES[d]: summary[f"{crashed} / {scope} / {d}"] for d in DESIGNS
                      if f"{crashed} / {scope} / {d}" in summary}
            md += table(groups, f"{'With crashes' if crashed == 'crashes' else 'No crash'}: "
                                f"{'all models' if scope == 'all' else scope}")
    rule = Path("results/ep04/runs_rule.jsonl")
    if rule.exists():
        rr = [json.loads(line) for line in rule.read_text().splitlines()]
        md += table({NAMES[d]: stats([r for r in rr if r["design"] == d and r["plan"]]) for d in DESIGNS},
                    "With crashes, a rule instead of a model")
    checks = Path("results/ep04/checks.json")
    if checks.exists():
        md += ["### After a hard crash, which steps run again? (`scripts/ep04_checks.py`)", "",
               "| Library and setting | Outcomes over 10 crashes |", "| :--- | :--- |"]
        for c in json.loads(checks.read_text())["crash_semantics"]:
            md.append(f"| {c['library']} | " + "; ".join(f"`{k}` × {v}" for k, v in c["outcomes"].items()) + " |")
        md.append("")
    Path("results/ep04/summary.md").write_text("\n".join(md))
    Path("results/ep04/summary.json").write_text(json.dumps(summary, indent=2))
    print("\n".join(md))


if __name__ == "__main__":
    main()
