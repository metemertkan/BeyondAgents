"""Episode 2 tables from results/ep02/runs.jsonl -> results/ep02/summary.md and summary.json.

    uv run python -m scripts.ep02_summary
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ARCHS = ("master_key", "mcp_shortcut", "mcp_strict", "utcp_agent_key", "utcp_user_token", "broker")
NAMES = {"master_key": "One master key (PoC)", "mcp_shortcut": "MCP + OAuth, common shortcut",
         "mcp_strict": "MCP + OAuth, strict", "utcp_agent_key": "UTCP, agent's key",
         "utcp_user_token": "UTCP, user's token", "broker": "Key broker (what I'd build)"}
SCENARIOS = ("colleague", "refund", "euros", "own", "staff_refund")


def stats(rows: list[dict]) -> dict:
    by = lambda s: [r for r in rows if r["scenario"] == s]
    return {
        "runs": len(rows),
        "mistakes": sum(r["mistake"] for r in rows),
        "other_customer_data": sum(r["other_customer_data"] for r in rows),
        "unauthorized_refund": sum(r["unauthorized_refund"] for r in rows),
        "private_to_eve": sum(bool(r["private_to_eve"]) for r in rows),
        "eve_replay_got_data": sum(r["eve_replay_got_data"] for r in rows),
        "legit_done": sum(r["task_done"] for r in rows if r["scenario"] in ("euros", "own", "staff_refund")),
        "legit_runs": sum(1 for r in rows if r["scenario"] in ("euros", "own", "staff_refund")),
        **{f"{s}_mistakes": sum(r["mistake"] for r in by(s)) for s in SCENARIOS},
        **{f"{s}_runs": len(by(s)) for s in SCENARIOS},
        "seconds": round(sum(r["seconds"] for r in rows) / max(len(rows), 1)),
    }


def table(groups: dict[str, dict], title: str) -> list[str]:
    lines = [f"### {title}", "",
             "| | Runs | Mistakes | Ada's data to Mallory | Refund to Mallory | Private data to Eve | "
             "Eve's replay worked | Legit tasks done | s/run |",
             "| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for name, s in groups.items():
        lines.append(f"| {name} | {s['runs']} | {s['mistakes']} | {s['other_customer_data']} | "
                     f"{s['unauthorized_refund']} | {s['private_to_eve']} | {s['eve_replay_got_data']} | "
                     f"{s['legit_done']} / {s['legit_runs']} | {s['seconds']} |")
    return lines + [""]


def scenario_table(groups: dict[str, dict], title: str) -> list[str]:
    lines = [f"### {title}: mistakes by scenario", "",
             "| | " + " | ".join(SCENARIOS) + " |", "| :--- |" + " ---: |" * len(SCENARIOS)]
    for name, s in groups.items():
        lines.append(f"| {name} | " + " | ".join(f"{s[f'{x}_mistakes']} / {s[f'{x}_runs']}" for x in SCENARIOS) + " |")
    return lines + [""]


def main() -> None:
    path = Path("results/ep02/runs.jsonl")
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    by = defaultdict(list)
    for r in rows:
        by[("all", r["arch"])].append(r)
        by[(r["model"], r["arch"])].append(r)
    summary = {" / ".join(k): stats(v) for k, v in by.items()}
    models = sorted({r["model"] for r in rows})
    md = ["# Episode 2 results", "",
          f"{len(rows)} runs. Counted in the systems' own records: the billing API's refunds, what FX4Free "
          "received, and what came back to Penny from her tools. Same models, prompt and people; only the tool "
          "access differs.", ""]
    for scope in ("all", *models):
        groups = {NAMES[a]: summary[f"{scope} / {a}"] for a in ARCHS if f"{scope} / {a}" in summary}
        title = "All runs" if scope == "all" else scope
        md += table(groups, title) + scenario_table(groups, title)
    checks = Path("results/ep02/checks.json")
    if checks.exists():
        c = json.loads(checks.read_text())
        md += ["### Checks without a model (`scripts/ep02_checks.py`)", "",
               "| Billing MCP server | Credential Eve holds | Billing MCP server | Billing API |",
               "| :--- | :--- | :--- | :--- |"]
        for r in c["token_replay"]:
            md.append(f"| {r['billing_mcp_mode']} | {r['credential']} | {r['billing_mcp']['status']}"
                      f"{', Ada’s invoices' if r['billing_mcp']['got_ada'] else ''} | {r['billing_api']['status']} |")
        u = c["utcp_variables"]
        md += ["", f"UTCP: Eve's manual asks for `{u['manual_asks_for']}`. Outcome: {u['outcome']} "
               f"Eve received: {u['eve_received'] or 'nothing'}.", "",
               "| Local FX4Free launched as | Env key | `.env` file | Token cache | Phoned home |",
               "| :--- | :---: | :---: | :---: | :---: |"]
        for r in c["local_tool"]:
            p = r["probe"] or {}
            mark = lambda k: "yes" if p.get(k) else "no"
            md.append(f"| {r['launch']} | {mark('env:ACME_ADMIN_KEY')} | {mark('file:.env')} | "
                      f"{mark('file:~/.penny/tokens.json')} | {mark('phoned_home')} |")
        md.append("")
    Path("results/ep02/summary.md").write_text("\n".join(md))
    Path("results/ep02/summary.json").write_text(json.dumps(summary, indent=2))
    print("\n".join(md))


if __name__ == "__main__":
    main()
