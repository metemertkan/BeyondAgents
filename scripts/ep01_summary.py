"""Episode 1 tables from results/ep01/runs.jsonl -> results/ep01/summary.md and summary.json.

    uv run python -m scripts.ep01_summary
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def usd(cents: int) -> str:
    return f"${cents / 100:,.2f}"


def stats(rows: list[dict]) -> dict:
    n = len(rows)
    return {
        "runs": n,
        "handled_right": sum(r["handled_right"] for r in rows),
        "unapproved_refunds": sum(r["unapproved_refunds"] for r in rows),
        "unapproved_cents": sum(r["unapproved_cents"] for r in rows),
        "runs_extra_money": sum(r["extra_cents"] > 0 for r in rows),
        "extra_cents": sum(r["extra_cents"] for r in rows),
        "runs_missing_money": sum(r["missing_cents"] > 0 for r in rows),
        "runs_duplicate_replies": sum(r["reply_count"] > 1 for r in rows),
        "runs_no_reply": sum(r["reply_count"] == 0 for r in rows),
        "runs_untrue_reply": sum(bool(r["reply_problems"]) for r in rows),
        "operator_questions": sum(r["operator_questions"] for r in rows),
        "seconds": round(sum(r["seconds"] for r in rows) / max(n, 1)),
    }


def table(groups: dict, title: str) -> list[str]:
    lines = [f"### {title}", "",
             "| | Runs | Handled right | Refunds without approval | Money refunded beyond need | "
             "Duplicate replies | Untrue replies | No reply | Operator questions | s/run |",
             "| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for key, s in groups.items():
        lines.append(
            f"| {key} | {s['runs']} | {s['handled_right']} | {s['unapproved_refunds']} ({usd(s['unapproved_cents'])}) | "
            f"{s['runs_extra_money']} runs, {usd(s['extra_cents'])} | {s['runs_duplicate_replies']} | "
            f"{s['runs_untrue_reply']} | {s['runs_no_reply']} | {s['operator_questions']} | {s['seconds']} |")
    return lines + [""]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default="results/ep01/runs.jsonl")
    a = ap.parse_args()
    rows = [json.loads(line) for line in Path(a.runs).read_text().splitlines()]
    out_dir = Path(a.runs).parent

    by = defaultdict(list)
    for r in rows:
        by[(r["model"], r["executor"])].append(r)
        by[("all models", r["executor"])].append(r)
        by[(r["model"], r["executor"], r["ticket"])].append(r)
        by[(r["model"], r["executor"], r["condition"])].append(r)
    summary = {" / ".join(k): stats(v) for k, v in by.items()}

    models = sorted({r["model"] for r in rows})
    md = ["# Episode 1 results", "",
          f"{len(rows)} runs. Counted in the stand-in APIs' records, not in Penny's logs. "
          "Same models, prompt and tools; only the executor differs.", ""]
    md += table({f"{e}": summary[f"all models / {e}"] for e in ("demo", "production")
                 if f"all models / {e}" in summary}, "All runs")
    for m in models:
        md += table({e: summary[f"{m} / {e}"] for e in ("demo", "production") if f"{m} / {e}" in summary},
                    f"{m}")
        for dim, values in (("ticket", ("ada", "grace", "mallory", "alan")),
                            ("condition", ("clean", "lost_response", "rate_limit"))):
            groups = {f"{e}, {v}": summary[f"{m} / {e} / {v}"]
                      for v in values for e in ("demo", "production") if f"{m} / {e} / {v}" in summary}
            md += table(groups, f"{m} by {dim}")
    (out_dir / "summary.md").write_text("\n".join(md))
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    print("\n".join(md))


if __name__ == "__main__":
    main()
