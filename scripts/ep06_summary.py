"""Episode 6 tables -> results/ep06/summary.md and summary.json.

    uv run python -m scripts.ep06_summary

The reference is one agent: Episode 5's "Penny as shipped" (baseline and rerun, clean day).
"""
from __future__ import annotations

import json
import statistics
from collections import Counter
from pathlib import Path

from gate.evals import failures
from handoff.designs import DESIGNS

OUT = Path("results/ep06")


def stats(rows: list[dict], two_agents: bool = True) -> dict:
    kinds = Counter(k for r in rows for k in (r["failures"] if "failures" in r else failures(r)))
    calls = [r["front_model_calls"] + r["billing_model_calls"] if two_agents else r["model_calls"] for r in rows]
    tokens = [(r["front_tokens"]["prompt"] + r["front_tokens"]["output"] + r["billing_tokens"]["prompt"] +
               r["billing_tokens"]["output"]) if two_agents else r["tokens"]["prompt"] + r["tokens"]["output"]
              for r in rows]
    refunds_with_order = sum(bool(m.get("work_order")) for r in rows for m in r.get("refund_metadata", []))
    refunds = sum(len(r.get("refund_metadata", r.get("refunds", []))) for r in rows)
    out = {"runs": len(rows), "right": sum(not (r["failures"] if "failures" in r else failures(r)) for r in rows),
           "failures": dict(kinds), "extra_refund_usd": sum(r["extra_cents"] for r in rows) / 100,
           "model_calls": round(statistics.mean(calls), 2), "tokens": round(statistics.mean(tokens)),
           "seconds_median": round(statistics.median(r["seconds"] for r in rows), 1)}
    if two_agents:
        out |= {"handoffs_sent": sum(r["handoffs_sent"] for r in rows),
                "work_done_twice": sum(r["billing_work"] > 1 for r in rows),
                "replayed": sum(r["billing_replayed"] for r in rows),
                "relayed_approval": sum(r["relayed_approval"] for r in rows if r["ticket"] in ("mallory", "eve")),
                "relay_tickets": sum(r["ticket"] in ("mallory", "eve") for r in rows),
                "approvals_asked": sum(r["approvals_asked"] for r in rows),
                "approvals_refused": sum(r["approvals_refused"] for r in rows),
                "refunds": refunds, "refunds_traceable": refunds_with_order}
    return out


def main() -> None:
    rows = [json.loads(line) for line in (OUT / "runs.jsonl").read_text().splitlines() if line.strip()]
    ep5 = [json.loads(line) for line in Path("results/ep05/runs.jsonl").read_text().splitlines()]
    one = [r for r in ep5 if r["version"] in ("baseline", "rerun")]
    summary = {"one_agent": stats(one, two_agents=False), "designs": {}}
    for key, design in DESIGNS.items():
        for condition in design.conditions:
            mine = [r for r in rows if r["design"] == key and r["condition"] == condition]
            if mine:
                summary["designs"][f"{key} / {condition}"] = {"name": design.name, "act": design.act,
                                                               **stats(mine)}
    md = ["# Episode 6 results", "",
          f"{len(rows)} runs of Penny as two agents (front desk + billing agent over A2A, qwen3:8b), and the "
          f"one-agent reference: Episode 5's {len(one)} clean runs of Penny as shipped. Failures are read from "
          "the payments and helpdesk records.", ""]
    for condition, title in (("clean", "A clean day"), ("lost_handoff", "One answer lost between the agents")):
        md += [f"## {title}", "",
               "| Design | Right | Failures | Extra refunded | Work done twice | Model calls / run | Tokens / run | s (median) |",
               "| :--- | ---: | :--- | ---: | ---: | ---: | ---: | ---: |"]
        if condition == "clean":
            s = summary["one_agent"]
            md.append(f"| One agent (Episode 5) | {s['right']}/{s['runs']} | "
                      f"{', '.join(f'{k} {n}' for k, n in s['failures'].items()) or 'none'} | ${s['extra_refund_usd']:.0f} | "
                      f"— | {s['model_calls']} | {s['tokens']} | {s['seconds_median']} |")
        for key, s in summary["designs"].items():
            if not key.endswith(condition):
                continue
            md.append(f"| {s['name']} | {s['right']}/{s['runs']} | "
                      f"{', '.join(f'{k} {n}' for k, n in s['failures'].items()) or 'none'} | ${s['extra_refund_usd']:.0f} | "
                      f"{s['work_done_twice']} | {s['model_calls']} | {s['tokens']} | {s['seconds_median']} |")
        md.append("")
    tickets = ["ada", "grace", "mallory", "alan", "linus", "eve"]
    right = lambda rs: f"{sum(not (r['failures'] if 'failures' in r else failures(r)) for r in rs)}/{len(rs)}"
    md += ["## Right, ticket by ticket", "", "| Design / day | " + " | ".join(tickets) + " |",
           "| :--- |" + " ---: |" * len(tickets),
           "| One agent (Episode 5) / clean | " + " | ".join(right([r for r in one if r["ticket"] == t]) for t in tickets) + " |"]
    for key, design in DESIGNS.items():
        for condition in design.conditions:
            mine = [r for r in rows if r["design"] == key and r["condition"] == condition]
            if mine:
                md.append(f"| {design.name} / {condition} | " +
                          " | ".join(right([r for r in mine if r["ticket"] == t]) for t in tickets) + " |")
    md.append("")
    md += ["## The hand-off", "",
           "| Design / day | Messages sent | Replayed | Fake approval retold as fact (Mallory, Eve) | Approvals asked / refused | Refunds traceable to a work order |",
           "| :--- | ---: | ---: | ---: | ---: | ---: |"]
    for key, s in summary["designs"].items():
        md.append(f"| {s['name']} / {key.split(' / ')[1]} | {s['handoffs_sent']} | {s['replayed']} | "
                  f"{s['relayed_approval']}/{s['relay_tickets']} | {s['approvals_asked']} / {s['approvals_refused']} | "
                  f"{s['refunds_traceable']}/{s['refunds']} |")
    (OUT / "summary.md").write_text("\n".join(md) + "\n")
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2))
    print("\n".join(md))


if __name__ == "__main__":
    main()
