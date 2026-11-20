"""The BeyondAgents site.

    uv run python -m web          # http://localhost:8092
"""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from web import live
from web.episodes import BY_N, EPISODES, Episode, rows

STATIC = Path(__file__).resolve().parent / "static"
OLLAMA = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")

app = FastAPI(title="BeyondAgents")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


def _episode(n: int) -> Episode:
    ep = BY_N.get(n)
    if ep is None:
        raise HTTPException(404, "no such episode")
    return ep


def _designs(ep: Episode) -> list[dict]:
    if not ep.ready:
        return ep.designs
    all_rows = rows(ep)
    out = []
    for d in ep.designs:
        mine = [r for r in all_rows if r.get(ep.design_key) == d["key"]]
        out.append({**d, **(ep.scoreboard(mine) if mine else {"headline": "–", "cells": []})})
    return out


def _summary(ep: Episode) -> dict:
    return {"n": ep.n, "question": ep.question, "answer": ep.answer, "sentence": ep.sentence, "ready": ep.ready,
            "runs": len(rows(ep)) if ep.ready else 0}


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/models")
def models():
    """Which local models a live run can use."""
    try:
        with urllib.request.urlopen(f"{OLLAMA}/api/tags", timeout=3) as r:
            names = [m["name"] for m in json.loads(r.read())["models"]]
        return {"ollama": True, "models": names}
    except Exception:
        return {"ollama": False, "models": []}


@app.get("/api/episodes")
def episodes():
    return [{**_summary(ep), "designs": _designs(ep), "act_names": ep.act_names} for ep in EPISODES]


@app.get("/api/episodes/{n}")
def episode(n: int):
    ep = _episode(n)
    return {**_summary(ep), "designs": _designs(ep), "columns": ep.columns, "axes": ep.axes, "live": ep.live,
            "design_key": ep.design_key, "act_names": ep.act_names, "headline_label": ep.headline_label,
            "extra": ep.extra() if ep.extra and ep.ready else None}


@app.get("/api/episodes/{n}/runs")
def runs(n: int, request: Request):
    ep = _episode(n)
    if not ep.ready:
        return []
    filters = {k: v for k, v in request.query_params.items() if v != ""}
    out = []
    for i, r in enumerate(rows(ep)):
        if all(str(r.get(k)) == v for k, v in filters.items()):
            out.append({"i": i, **{a["key"]: r.get(a["key"]) for a in ep.axes}, "seconds": r.get("seconds"),
                        **ep.verdict(r)})
    return out


@app.get("/api/episodes/{n}/runs/{i}")
def run(n: int, i: int):
    ep = _episode(n)
    all_rows = rows(ep) if ep.ready else []
    if not 0 <= i < len(all_rows):
        raise HTTPException(404, "no such run")
    r = all_rows[i]
    return {"row": r, "verdict": ep.verdict(r), "context": ep.context(r) if ep.context else {}}


@app.post("/api/episodes/{n}/live")
async def start_live(n: int, request: Request):
    ep = _episode(n)
    if ep.run_live is None:
        raise HTTPException(400, "this episode has no live runs yet")
    try:
        params = await request.json()
    except ValueError:
        raise HTTPException(400, "send the parameters as JSON")
    allowed = {p["key"]: [str(v) for v in p["values"]] for p in ep.live}
    if not isinstance(params, dict) or set(params) != set(allowed) or any(str(params[k]) not in allowed[k] for k in allowed):
        raise HTTPException(400, f"parameters must be one of {allowed}")
    return live.submit(n, params)


@app.get("/api/live/{job_id}")
def live_status(job_id: str):
    job = live.status(job_id)
    if job is None:
        raise HTTPException(404, "no such live run")
    ep = BY_N[job["episode"]]
    if job["row"] is not None:
        job = {**job, "verdict": ep.verdict(job["row"]), "context": ep.context(job["row"]) if ep.context else {}}
    return job
