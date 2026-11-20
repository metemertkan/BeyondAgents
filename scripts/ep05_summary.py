"""Episode 5 tables -> results/ep05/summary.md and summary.json.

    uv run python -m scripts.ep05_summary

1. What each change did, from the full pool (every ticket, ten runs) read from the APIs' records.
2. How likely each eval was to flag each change, over every sample it could have drawn from the
   pool: the spot check (3 runs), golden replies (6), the LLM judge (6), the receipts gate (30).

Reply similarities (bge-m3 on the local Ollama) are cached in results/ep05/similarity.jsonl.
"""
from __future__ import annotations

import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from gate import evals
from gate.golden import GOLDEN, embed, cosine, reply_of
from gate.versions import CHANGES, VERSIONS
from penny.tickets import TICKETS

OUT = Path("results/ep05")
K = 5                 # runs per ticket in one pass of the receipts gate
GOLDEN_MARGIN = 0.02
JUDGE_MARGIN = 0.05
DEFAULT_THRESHOLD = 0.5


def load(name: str) -> list[dict]:
    path = OUT / name
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def similarities(rows: list[dict]) -> dict[tuple, float]:
    path = OUT / "similarity.jsonl"
    cache = {(r["version"], r["ticket"], r["seed"]): r["similarity"] for r in load("similarity.jsonl")}
    todo = [r for r in rows if (r["version"], r["ticket"], r["seed"]) not in cache]
    if todo:
        gold = dict(zip(GOLDEN, embed(list(GOLDEN.values()))))
        with path.open("a") as f:
            for i in range(0, len(todo), 16):
                batch = todo[i:i + 16]
                for r, vec in zip(batch, embed([reply_of(r) for r in batch])):
                    key = (r["version"], r["ticket"], r["seed"])
                    cache[key] = round(cosine(vec, gold[r["ticket"]]), 4)
                    f.write(json.dumps({"version": key[0], "ticket": key[1], "seed": key[2],
                                        "similarity": cache[key]}) + "\n")
    return cache


def what_happened(runs: list[dict], baseline: list[dict]) -> dict:
    """Per ticket: failures by kind, compared with the shipped version's own runs."""
    out = {}
    for t in TICKETS:
        mine = [r for r in runs if r["ticket"] == t]
        base = [r for r in baseline if r["ticket"] == t]
        kinds = Counter(k for r in mine for k in evals.failures(r))
        base_kinds = Counter(k for r in base for k in evals.failures(r))
        out[t] = {"runs": len(mine), "right": sum(not evals.failures(r) for r in mine), "failures": dict(kinds),
                  "baseline_failures": dict(base_kinds),
                  "p_worse": {k: round(evals.fisher_greater(n, len(mine), base_kinds.get(k, 0), len(base)), 4)
                              for k, n in kinds.items()}}
    return out


def verdict(happened: dict, runs: list[dict], baseline: list[dict]) -> str:
    """Did the change hurt customers? Needs the effect to repeat: a new kind of failure on a ticket at
    least twice in ten runs, or a failure significantly more frequent (p < 0.05) on a ticket or overall."""
    for t, h in happened.items():
        for kind, n in h["failures"].items():
            if kind not in h["baseline_failures"] and n >= 2:
                return "broke"
            if h["p_worse"][kind] < 0.05:
                return "broke"
    bad = sum(bool(evals.failures(r)) for r in runs)
    base_bad = sum(bool(evals.failures(r)) for r in baseline)
    if evals.fisher_greater(bad, len(runs), base_bad, len(baseline)) < 0.05:
        return "broke"
    if any(kind not in h["baseline_failures"] for h in happened.values() for kind in h["failures"]):
        return "unclear"
    return "no harm found"


def main() -> None:
    rows = load("runs.jsonl")
    judged = {(r["version"], r["ticket"], r["seed"]): r for r in load("judged.jsonl")}
    sims = similarities(rows)
    by = defaultdict(list)
    for r in rows:
        by[r["version"]].append(r)
    baseline = by["baseline"]
    base_by_ticket = {t: [r for r in baseline if r["ticket"] == t] for t in TICKETS}

    # Calibrate on the shipped version: it passes its own golden and judge checks.
    golden_floor = evals.floors({t: [sims[(r["version"], t, r["seed"])] for r in base_by_ticket[t]]
                                 for t in TICKETS}, GOLDEN_MARGIN)
    base_judged = {t: [judged[k]["score"] for k in judged if k[0] == "baseline" and k[1] == t] for t in TICKETS}
    judge_floor = evals.floors(base_judged, JUDGE_MARGIN) if all(base_judged.values()) else {}

    summary = {"golden_floor": golden_floor, "judge_floor": judge_floor, "versions": {}}
    for key, version in VERSIONS.items():
        runs = by.get(key, [])
        if not runs:
            continue
        per_ticket = {t: [r for r in runs if r["ticket"] == t] for t in TICKETS}
        happened = what_happened(runs, baseline)
        s = {"name": version.name, "who": version.who, "why": version.why, "diff": version.diff,
             "runs": len(runs), "right": sum(not evals.failures(r) for r in runs),
             "model_calls": round(statistics.mean(r["model_calls"] for r in runs), 2),
             "tokens": round(statistics.mean(r["tokens"]["prompt"] + r["tokens"]["output"] for r in runs)),
             "seconds_median": round(statistics.median(r["seconds"] for r in runs), 1),
             "approvals_refused": sum(r["approvals_refused"] for r in runs),
             "blocked_replies": sum(r["blocked_replies"] for r in runs),
             "happened": happened}
        if key != "baseline":
            s["verdict"] = verdict(happened, runs, baseline)
            spot = [sum(evals.spot_ok(r) for r in per_ticket[t]) / len(per_ticket[t]) for t in evals.DEMO_TICKETS]
            gold = [sum(sims[(key, t, r["seed"])] >= golden_floor[t] for r in per_ticket[t]) / len(per_ticket[t])
                    for t in TICKETS]
            s["flag"] = {"spot_check": evals.flag_probability(spot), "golden": evals.flag_probability(gold)}
            mine_judged = {t: [judged[(key, t, r["seed"])]["score"] for r in per_ticket[t]
                               if (key, t, r["seed"]) in judged] for t in TICKETS}
            if judge_floor and all(mine_judged.values()):
                s["flag"]["judge"] = evals.flag_probability(
                    [sum(x >= judge_floor[t] for x in v) / len(v) for t, v in mine_judged.items()])
                # DeepEval's default: a test case passes at a score of 0.5 or more.
                s["flag"]["judge_default"] = evals.flag_probability(
                    [sum(x >= DEFAULT_THRESHOLD for x in v) / len(v) for t, v in mine_judged.items()])
                s["judge_scores"] = {t: v for t, v in mine_judged.items()}
            if all(len(per_ticket[t]) >= K for t in TICKETS):
                s["flag"]["receipts"] = evals.flag_probability(
                    [evals.pass_rate_over_samples(per_ticket[t], base_by_ticket[t], K) for t in TICKETS])
            s["golden_low"] = {t: min(sims[(key, t, r["seed"])] for r in per_ticket[t]) for t in TICKETS}
        summary["versions"][key] = s

    # The judge against the records, run by run.
    agree = Counter()
    by_ticket = defaultdict(Counter)
    for k, j in judged.items():
        r = next((x for x in by[k[0]] if x["ticket"] == k[1] and x["seed"] == k[2]), None)
        if r is None:
            continue
        cell = ("right" if not evals.failures(r) else "mistake", "pass" if j["score"] >= DEFAULT_THRESHOLD else "fail")
        agree[cell] += 1
        by_ticket[k[1]][cell] += 1
    summary["judge_vs_records"] = {" / ".join(c): n for c, n in agree.items()}
    summary["judge_vs_records_by_ticket"] = {t: {" / ".join(c): n for c, n in v.items()} for t, v in by_ticket.items()}
    run_s = statistics.median(r["seconds"] for r in baseline)
    judge_s = statistics.median(j["seconds"] for j in judged.values()) if judged else 0
    summary["cost_per_pass"] = {
        "spot_check": {"agent_runs": 3, "judge_calls": 0, "minutes": round(3 * run_s / 60, 1)},
        "golden": {"agent_runs": 6, "judge_calls": 0, "minutes": round(6 * run_s / 60, 1)},
        "judge": {"agent_runs": 6, "judge_calls": 6, "minutes": round((6 * run_s + 6 * judge_s) / 60, 1)},
        "receipts": {"agent_runs": 6 * K, "judge_calls": 0, "minutes": round(6 * K * run_s / 60, 1)},
    }
    hybrid = OUT / "hybrid_reads.json"
    if hybrid.exists():
        summary["hybrid_reads"] = json.loads(hybrid.read_text())

    # Follow-up runs for a weak verdict: the version's runs on that ticket, all of them, against the
    # shipped version's runs on it (baseline and rerun together).
    extra = load("runs_extra.jsonl")
    summary["follow_up"] = {}
    for key in sorted({r["version"] for r in extra}):
        for t in sorted({r["ticket"] for r in extra if r["version"] == key}):
            mine = [r for r in by[key] + extra if r["version"] == key and r["ticket"] == t]
            shipped = [r for r in by["baseline"] + by["rerun"] if r["ticket"] == t]
            bad, base_bad = sum(bool(evals.failures(r)) for r in mine), sum(bool(evals.failures(r)) for r in shipped)
            p = evals.fisher_greater(bad, len(mine), base_bad, len(shipped))
            summary["follow_up"][f"{key} / {t}"] = {"failed": bad, "runs": len(mine), "shipped_failed": base_bad,
                                                   "shipped_runs": len(shipped), "p": round(p, 3)}
            if p >= 0.05 and summary["versions"][key]["verdict"] == "broke":
                summary["versions"][key]["verdict"] = "unclear"

    order = ["rerun"] + CHANGES
    md = ["# Episode 5 results", "",
          f"{len(rows)} runs of Penny (Episode 1's tool-calling agent, production executor, clean day). "
          "Each version ran every ticket ten times. Failures are read from the payments and helpdesk records.", "",
          "## What each change did", "",
          "| Version | Change | Right (of runs) | Failures by ticket | Model calls / run | Tokens / run | Verdict |",
          "| :--- | :--- | ---: | :--- | ---: | ---: | :--- |"]
    for key in ["baseline"] + order:
        s = summary["versions"].get(key)
        if not s:
            continue
        fails = "; ".join(f"{t}: " + ", ".join(f"{k} {n}" for k, n in h["failures"].items())
                          for t, h in s["happened"].items() if h["failures"]) or "none"
        md.append(f"| {s['name']} | {s['diff'] or '—'} | {s['right']}/{s['runs']} | {fails} | {s['model_calls']} | "
                  f"{s['tokens']} | {s.get('verdict', 'the reference')} |")
    md += ["", "## How likely each eval was to flag the version", "",
           "Over every sample the eval could have drawn from the pool. The rerun changed nothing: any flag "
           "there is a false alarm.", "",
           "| Version | Verdict | Spot check (3 runs) | Golden replies (6) | LLM judge (6) | LLM judge, threshold 0.5 | Receipts gate (30) |",
           "| :--- | :--- | ---: | ---: | ---: | ---: | ---: |"]
    pct = lambda x: "–" if x is None else f"{100 * x:.0f}%"
    for key in order:
        s = summary["versions"].get(key)
        if not s:
            continue
        f = s["flag"]
        md.append(f"| {s['name']} | {s['verdict']} | {pct(f.get('spot_check'))} | {pct(f.get('golden'))} | "
                  f"{pct(f.get('judge'))} | {pct(f.get('judge_default'))} | {pct(f.get('receipts'))} |")
    for name, f in summary["follow_up"].items():
        md += ["", f"Follow-up, {name}: {f['failed']}/{f['runs']} runs failed, against {f['shipped_failed']}/"
               f"{f['shipped_runs']} for the shipped version (one-sided Fisher p = {f['p']}). Verdict: "
               f"{summary['versions'][name.split(' / ')[0]]['verdict']}."]
    md += ["", f"Golden floors (lowest similarity of the shipped version, minus {GOLDEN_MARGIN}): " +
           ", ".join(f"{t} {v:.3f}" for t, v in golden_floor.items())]
    if judge_floor:
        md.append(f"Judge floors (lowest G-Eval score of the shipped version, minus {JUDGE_MARGIN}): " +
                  ", ".join(f"{t} {v:.2f}" for t, v in judge_floor.items()))
    if agree:
        md += ["", "## The judge against the records (score 0.5 or more = pass)", "",
               "| Ticket | Right, judge passed | Right, judge failed | Mistake, judge passed | Mistake, judge failed |",
               "| :--- | ---: | ---: | ---: | ---: |"]
        for t, c in list(by_ticket.items()) + [("all", agree)]:
            md.append(f"| {t} | {c[('right', 'pass')]} | {c[('right', 'fail')]} | {c[('mistake', 'pass')]} | "
                      f"{c[('mistake', 'fail')]} |")
    md += ["", "## Cost of one pass (this CPU, one run at a time)", "",
           "| Eval | Agent runs | Judge calls | Minutes |", "| :--- | ---: | ---: | ---: |"]
    for name, c in summary["cost_per_pass"].items():
        md.append(f"| {name} | {c['agent_runs']} | {c['judge_calls']} | {c['minutes']} |")
    if "hybrid_reads" in summary:
        md += ["", "## Side note: the hybrid's reading step (Episode 1, Act 3)", "",
               "| Variant | Model | Every ticket read right, 5 seeds? |", "| :--- | :--- | :--- |"]
        for name, h in summary["hybrid_reads"].items():
            ok = all(o == {"right": 5} for o in h["outcomes"].values())
            md.append(f"| {name} | {h['model']} | {'yes' if ok else h['outcomes']} |")
    (OUT / "summary.md").write_text("\n".join(md) + "\n")
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2))
    print("\n".join(md))


if __name__ == "__main__":
    main()
