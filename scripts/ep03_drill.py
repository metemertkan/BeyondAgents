"""Episode 3 deletion drill, no model: does "delete Ada" make Penny forget Ada?

    uv run python -m scripts.ep03_drill      # writes results/ep03/drill.json

For each memory design, Ada's new address is stored the way that design stores things. Acme then
processes Ada's deletion request (the design's own delete), and every store is searched for it.

- notebook: two notes, as the pilot's models wrote them: one with Ada's name, one without
- Mem0: Ada's message stored for her (`infer=False`, so no model is involved), then `delete_all(user_id=...)`
- owned: a profile change request and a preference, both for Ada
"""
from __future__ import annotations

import json
import logging
import os
import warnings
from pathlib import Path

os.environ.setdefault("MEM0_TELEMETRY", "False")

from recall.data import ADA_NEW, CUSTOMERS   # noqa: E402
from recall.scenarios import NEW_ADDRESS     # noqa: E402
from recall.world import World               # noqa: E402

HERE = Path(__file__).resolve().parent.parent


def plant(world: World) -> None:
    d = world.design
    if d.name == "notebook":
        d.notes += ["Ada moved to 9 Hill St, Bristol on December 1st. New phone: +44 7700 900333.",
                    "I'm moving to 9 Hill St, Bristol on December 1st, and my new phone number is +44 7700 900333."]
    elif d.name.startswith("mem0"):
        ids = {"user_id": CUSTOMERS["ada"]["email"], **({"agent_id": "penny"} if d.shared else {})}
        d.memory.add([{"role": "user", "content": NEW_ADDRESS}], infer=False, **ids)
    elif d.name == "owned":
        world.call("ada", "request_profile_change", {"field": "address", "value": "9 Hill St, Bristol"})
        world.call("ada", "remember_preference", {"preference": "Send post to 9 Hill St from December 1st"})


def where(dumps: dict) -> list[str]:
    return sorted(store for store, text in dumps.items() if any(m in text for m in ADA_NEW))


def main() -> None:
    logging.disable(logging.CRITICAL)
    warnings.simplefilter("ignore")
    rows = []
    for design in ("notebook", "mem0_user", "mem0_shared", "owned"):
        world = World(design)
        try:
            plant(world)
            dump = lambda: {**world.design.dump(), "crm pending changes": json.dumps(world.crm.pending)}
            before = where(dump())
            world.forget("ada")
            after = dump()
            rows.append({"design": design, "stored_in_before": before, "still_in_after_delete": where(after),
                         "after": {k: v for k, v in after.items() if any(m in v for m in ADA_NEW)}})
        finally:
            world.close()
    out = HERE / "results" / "ep03" / "drill.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, indent=2))
    for r in rows:
        print(f"{r['design']:12s} before: {r['stored_in_before']}   after delete: {r['still_in_after_delete'] or 'nothing'}")
        for store, text in r["after"].items():
            print(f"{'':14s}{store}: {text[:150]!r}")


if __name__ == "__main__":
    main()
