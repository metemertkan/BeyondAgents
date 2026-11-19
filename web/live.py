"""Live runs: one at a time (they run local models on the CPU), in a background thread."""
from __future__ import annotations

import logging
import queue
import threading
import time
import traceback
import uuid
import warnings

from web.episodes import BY_N

_jobs: dict[str, dict] = {}
_queue: "queue.Queue[str]" = queue.Queue()
_lock = threading.Lock()


def submit(n: int, params: dict) -> dict:
    job = {"id": uuid.uuid4().hex[:12], "episode": n, "params": params, "status": "queued",
           "created": time.time(), "started": None, "finished": None, "row": None, "error": None}
    with _lock:
        _jobs[job["id"]] = job
        # keep the last 50
        for old in sorted(_jobs.values(), key=lambda j: j["created"])[:-50]:
            _jobs.pop(old["id"], None)
    _queue.put(job["id"])
    return status(job["id"])


def status(job_id: str) -> dict | None:
    with _lock:
        job = _jobs.get(job_id)
        if job is None:
            return None
        ahead = sum(1 for j in _jobs.values() if j["status"] == "queued" and j["created"] < job["created"])
        running = any(j["status"] == "running" for j in _jobs.values())
        return {**job, "ahead": ahead + (1 if job["status"] == "queued" and running else 0),
                "elapsed": round((job["finished"] or time.time()) - (job["started"] or time.time()), 1)}


def _worker() -> None:
    logging.disable(logging.WARNING)
    warnings.simplefilter("ignore")
    while True:
        job_id = _queue.get()
        with _lock:
            job = _jobs.get(job_id)
            if job is None:
                continue
            job["status"], job["started"] = "running", time.time()
        try:
            row = BY_N[job["episode"]].run_live(job["params"])
            with _lock:
                job["row"], job["status"] = row, "done"
        except Exception as e:  # shown to the person who started the run
            with _lock:
                job["error"], job["status"] = f"{type(e).__name__}: {e}\n{traceback.format_exc()[-1500:]}", "error"
        finally:
            with _lock:
                job["finished"] = time.time()


threading.Thread(target=_worker, daemon=True, name="live-runs").start()
