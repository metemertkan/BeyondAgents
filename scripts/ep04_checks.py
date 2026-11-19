"""Episode 4 checks, no model.

    uv run python -m scripts.ep04_checks      # writes results/ep04/checks.json

1. What each library does after a hard crash: a three-step job whose process dies (os._exit, like
   kill -9) right after step 2's work, then restarts. Which steps run again? DBOS, and LangGraph in
   each durability mode. Repeated 10 times each, because LangGraph's default writes checkpoints in
   the background, so the outcome depends on timing.
2. The month-end job for every design and crash plan with a rule instead of a model, so the only
   thing that varies is the design (stored as results/ep04/runs_rule.jsonl by scripts.ep04_run).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent

DBOS_JOB = '''
import os, sys
from dbos import DBOS, SetWorkflowID
STATE = sys.argv[1]
DBOS(config={"name": "crashcheck", "system_database_url": f"sqlite:///{STATE}/dbos.sqlite"})
def effect(name):
    open(f"{STATE}/effects.log", "a").write(name + "\\n")
@DBOS.step()
def step(i):
    effect(f"step{i}")
    if i == 2 and not os.path.exists(f"{STATE}/crashed"):
        open(f"{STATE}/crashed", "w").close(); os._exit(137)
    return i
@DBOS.workflow()
def job():
    return [step(i) for i in (1, 2, 3)]
DBOS.launch()
with SetWorkflowID("job-1"):
    DBOS.start_workflow(job).get_result()
'''

LANGGRAPH_JOB = '''
import os, sys, sqlite3
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver
STATE, MODE = sys.argv[1], sys.argv[2]
def effect(name):
    open(f"{STATE}/effects.log", "a").write(name + "\\n")
class S(TypedDict):
    done: list
def make(i):
    def node(s):
        effect(f"step{i}")
        if i == 2 and not os.path.exists(f"{STATE}/crashed"):
            open(f"{STATE}/crashed", "w").close(); os._exit(137)
        return {"done": s["done"] + [i]}
    return node
g = StateGraph(S)
for i in (1, 2, 3):
    g.add_node(f"n{i}", make(i))
g.add_edge(START, "n1"); g.add_edge("n1", "n2"); g.add_edge("n2", "n3"); g.add_edge("n3", END)
app = g.compile(checkpointer=SqliteSaver(sqlite3.connect(f"{STATE}/lg.sqlite", check_same_thread=False)))
cfg = {"configurable": {"thread_id": "job-1"}}
kw = {} if MODE == "default" else {"durability": MODE}
snap = app.get_state(cfg)
if not snap.values:
    app.invoke({"done": []}, cfg, **kw)
elif len(snap.values.get("done", [])) < 3:
    app.invoke(None, cfg, **kw)
'''


def crash_and_restart(script: str, *args: str) -> list[str]:
    state = tempfile.mkdtemp(prefix="ep04_check_")
    path = os.path.join(state, "job.py")
    open(path, "w").write(script)
    for _ in range(2):
        subprocess.run([sys.executable, path, state, *args], capture_output=True, timeout=300)
    return open(os.path.join(state, "effects.log")).read().split()


def main() -> None:
    rows = []
    cases = [("DBOS", DBOS_JOB, ())] + [(f"LangGraph, durability={m}", LANGGRAPH_JOB, (m,))
                                         for m in ("default", "async", "sync", "exit")]
    for name, script, args in cases:
        runs = Counter(" ".join(crash_and_restart(script, *args)) for _ in range(10))
        rows.append({"library": name, "outcomes": dict(runs)})
        print(f"{name:32s} {dict(runs)}")
    out = HERE / "results" / "ep04" / "checks.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"crash_semantics": rows}, indent=2))


if __name__ == "__main__":
    main()
