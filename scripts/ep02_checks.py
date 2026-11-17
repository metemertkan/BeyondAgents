"""Episode 2 checks that need no model: what Eve can do with what she is handed.

    uv run python -m scripts.ep02_checks      # writes results/ep02/checks.json

1. Token replay: the credential Eve receives, tried at Acme's billing MCP server (shortcut and
   strict) and billing API.
2. UTCP variables: Eve's manual asks the client for `${BILLING_TOKEN}` by name.
3. Secure tool execution: FX4Free's local edition launched four ways, as a plain subprocess (the
   PoC), as an MCP stdio server, as a UTCP CLI tool, and in a Docker sandbox. What can it read,
   and can it phone home?
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import warnings
from pathlib import Path

import httpx

from mcp import Client
from mcp.client.stdio import StdioServerParameters
from utcp.utcp_client import UtcpClient

from portal.data import ADMIN_KEY, FX_KEY
from portal.eve import mcp_tool_call
from portal.world import World

HERE = Path(__file__).resolve().parent.parent
LOCAL = HERE / "portal" / "eve_local"
SANDBOX_IMAGE = "python:3.12-slim"


async def token_replay() -> list[dict]:
    rows = []
    for mode in ("shortcut", "strict"):
        with World(mode) as w:
            mallory_fx = w.idp.mint("mallory", w.fx_mcp_url, ["fx:convert"], "penny")
            mallory_billing_mcp = w.idp.mint("mallory", w.billing_mcp_url, ["profile:read", "invoices:read"], "penny")
            creds = {"Mallory's token for FX4Free (MCP)": mallory_fx,
                     "Mallory's token for the billing MCP server": mallory_billing_mcp,
                     "Acme's FX4Free account key": FX_KEY}
            for label, token in creds.items():
                r = await mcp_tool_call(w.billing_mcp_url, token, "get_invoices", {"email": "ada@example.com"})
                mcp_ok = r.status_code == 200 and "in_a_1" in r.text and '"isError":false' in r.text
                async with httpx.AsyncClient() as http:
                    a = await http.get(f"{w.billing_url}/api/customers/ada@example.com/invoices",
                                       headers={"Authorization": f"Bearer {token}"})
                rows.append({"billing_mcp_mode": mode, "credential": label,
                             "billing_mcp": {"status": r.status_code, "got_ada": mcp_ok},
                             "billing_api": {"status": a.status_code, "got_ada": a.status_code == 200}})
    return rows


async def utcp_variables() -> dict:
    with World("shortcut") as w:
        os.environ["BILLING_TOKEN"] = ADMIN_KEY      # even a bare environment variable with that name
        client = await UtcpClient.create(config={
            "variables": {"billing_BILLING_TOKEN": ADMIN_KEY, "fx4free_FX_KEY": FX_KEY},
            "manual_call_templates": [{"name": "fx4free", "call_template_type": "http",
                                       "url": f"{w.fx_url}/utcp-greedy", "http_method": "GET"}]})
        try:
            await client.call_tool("fx4free.fx4free_convert", {"amount": 49})
            outcome = "called"
        except Exception as e:
            outcome = f"{type(e).__name__}: {e}"
        finally:
            await client.close()
            del os.environ["BILLING_TOKEN"]
        received = [e["token_kind"] for e in w.eve.log]
    return {"manual_asks_for": "${BILLING_TOKEN}", "outcome": outcome, "eve_received": received}


def _secret_workspace() -> tuple[Path, Path, Path]:
    """A project folder with a .env holding the master key, and a home with Penny's token cache."""
    root = Path(tempfile.mkdtemp(prefix="ep02_local_"))
    project, home, tool = root / "project", root / "home", root / "tool"
    project.mkdir()
    (home / ".penny").mkdir(parents=True)
    tool.mkdir()
    (project / ".env").write_text(f"ACME_ADMIN_KEY={ADMIN_KEY}\n")
    (home / ".penny" / "tokens.json").write_text(json.dumps({"access_token": "eyJ...mallory"}))
    return project, home, tool


async def local_tool() -> list[dict]:
    rows = []
    with World("shortcut") as w:
        project, home, tool = _secret_workspace()
        source = (LOCAL / "fx_local.py").read_text().replace("__COLLECT_URL__", f"{w.fx_url}/collect")
        (tool / "fx_local.py").write_text(source)
        shutil.copy(tool / "fx_local.py", project / "fx_local.py")   # a CLI tool installed into the project
        # The agent process: it loaded .env into its environment, and runs in its project folder.
        os.environ.update({"ACME_ADMIN_KEY": ADMIN_KEY, "HOME": str(home)})
        os.chdir(project)

        def record(method: str, probe: dict | None, error: str = ""):
            rows.append({"launch": method, "probe": probe, "error": error,
                         "eve_collected": len(w.eve.collected)})
            w.eve.collected.clear()

        # 1. The PoC: a plain subprocess with the agent's environment.
        out = subprocess.run([sys.executable, str(tool / "fx_local.py"), "49", "USD", "EUR"], capture_output=True,
                             text=True, env=dict(os.environ))
        record("plain subprocess (PoC)", json.loads(out.stdout)["probe"])

        # 2. An MCP stdio server, launched by the official SDK client.
        params = StdioServerParameters(command=sys.executable, args=[str(LOCAL / "fx_local_mcp.py"), str(tool)])
        async with Client(params) as client:
            result = await client.call_tool("convert", {"amount": 49, "from_currency": "USD", "to_currency": "EUR"})
        text = result.structured_content or json.loads(" ".join(getattr(c, "text", "") for c in result.content) or "{}")
        record("MCP stdio server (SDK defaults)", text.get("probe"), "" if text.get("probe") else str(result.content)[:300])

        # 3. A UTCP CLI tool, with UTCP's defaults.
        client = await UtcpClient.create(config={"manual_call_templates": [{
            "name": "fxlocal", "call_template_type": "cli",
            "commands": [{"command": f"{sys.executable} fx_local.py --manual"}]}]})
        try:
            raw = await client.call_tool("fxlocal.convert", {"amount": 49, "from_currency": "USD", "to_currency": "EUR"})
            record("UTCP CLI tool (defaults)", json.loads(raw if isinstance(raw, str) else json.dumps(raw))["probe"])
        except Exception as e:
            record("UTCP CLI tool (defaults)", None, f"{type(e).__name__}: {e}")
        finally:
            await client.close()

        # 4. The sandbox: no network, no secrets in the environment, nothing of the host mounted but the tool.
        out = subprocess.run(["docker", "run", "--rm", "--network", "none", "--read-only", "--cap-drop", "ALL",
                              "--security-opt", "no-new-privileges", "--user", "65534:65534", "-w", "/tmp",
                              "-v", f"{tool / 'fx_local.py'}:/tool/fx_local.py:ro", SANDBOX_IMAGE,
                              "python", "/tool/fx_local.py", "49", "USD", "EUR"], capture_output=True, text=True)
        if out.returncode == 0:
            record("Docker sandbox", json.loads(out.stdout)["probe"])
        else:
            record("Docker sandbox", None, out.stderr[-300:])
        os.chdir(HERE)
    return rows


async def main() -> None:
    logging.disable(logging.CRITICAL)
    warnings.simplefilter("ignore")
    results = {"token_replay": await token_replay(), "utcp_variables": await utcp_variables(),
               "local_tool": await local_tool()}
    out = HERE / "results" / "ep02" / "checks.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2))
    for r in results["token_replay"]:
        print(f"replay  {r['billing_mcp_mode']:8s} {r['credential']:44s} MCP {r['billing_mcp']['status']} "
              f"got Ada={r['billing_mcp']['got_ada']}   API {r['billing_api']['status']}")
    print("utcp   ", results["utcp_variables"])
    for r in results["local_tool"]:
        print(f"local   {r['launch']:34s} {r['probe'] or r['error']}  eve_collected={r['eve_collected']}")


if __name__ == "__main__":
    asyncio.run(main())
