"""The site's API over the recorded results (no live model runs)."""
import time

import pytest
from fastapi.testclient import TestClient

from web.app import app
from web.episodes import EPISODES

client = TestClient(app)
READY = [e.n for e in EPISODES if e.ready]


def test_health_and_index():
    assert client.get("/api/health").json() == {"ok": True}
    assert "BeyondAgents" in client.get("/").text


def test_every_episode_listed_and_the_shipped_design_is_clean():
    eps = client.get("/api/episodes").json()
    assert [e["n"] for e in eps] == [e.n for e in EPISODES]
    for e in eps:
        # Episodes whose designs are the three acts end with what I'd build; Episode 5's designs are versions.
        if e["ready"] and not e["act_names"]:
            last = e["designs"][-1]
            assert last["act"] == 3 and last["headline"].startswith("0 /"), (e["n"], last)


@pytest.mark.parametrize("n", READY)
def test_runs_filter_and_detail(n):
    ep = client.get(f"/api/episodes/{n}").json()
    runs = client.get(f"/api/episodes/{n}/runs").json()
    assert len(runs) == ep["runs"] > 0
    first = ep["designs"][0]["key"]
    only = client.get(f"/api/episodes/{n}/runs", params={ep["design_key"]: first}).json()
    assert only and all(r[ep["design_key"]] == first for r in only)
    detail = client.get(f"/api/episodes/{n}/runs/{runs[0]['i']}").json()
    assert detail["verdict"]["status"] in {"right", "mistake", "neutral"}
    assert client.get(f"/api/episodes/{n}/runs/99999").status_code == 404


def test_live_rejects_bad_parameters():
    assert client.post("/api/episodes/4/live", json={"design": "nope", "plan": 1, "model": "rule (no model)"}).status_code == 400
    assert client.post("/api/episodes/4/live", content=b"{not json").status_code == 400
    assert client.post("/api/episodes/6/live", json={}).status_code == 400


def test_live_run_without_a_model():
    job = client.post("/api/episodes/4/live", json={"design": "durable_keys", "plan": 1, "model": "rule (no model)"}).json()
    for _ in range(120):
        job = client.get(f"/api/live/{job['id']}").json()
        if job["status"] in {"done", "error"}:
            break
        time.sleep(1)
    assert job["status"] == "done", job.get("error")
    assert job["verdict"]["status"] == "right" and job["row"]["runs_of_worker"] > 1
