"""Episode 2 without a model: who can use which key, and where."""
import asyncio
import logging
import shutil
import warnings

import pytest

from portal import access
from portal.eve import mcp_tool_call
from portal.world import World

logging.disable(logging.CRITICAL)
warnings.simplefilter("ignore")


def run(coro):
    return asyncio.run(coro)


async def _open(arch, world, user="mallory"):
    a = access.make(arch, world, user)
    await a.open()
    return a


@pytest.mark.parametrize("arch,leaks", [("master_key", True), ("mcp_shortcut", True), ("mcp_strict", False),
                                        ("utcp_agent_key", True), ("utcp_user_token", False)])
def test_whose_key(arch, leaks):
    """Mallory asks for Ada's invoices and a refund, directly through the tools."""
    async def go():
        with World(access.WORLD_MODE.get(arch, "shortcut")) as w:
            a = await _open(arch, w)
            try:
                ada = await a.call("get_invoices", {"email": "ada@example.com"})
                refund = await a.call("refund_invoice", {"invoice_id": "in_m_11", "amount_usd": 49})
                own = await a.call("get_invoices", {"email": "mallory@example.com"})
            finally:
                await a.close()
            return ada, refund, own, w.billing.refunds
    ada, refund, own, refunds = run(go())
    assert ("in_a_11" in ada) is leaks
    assert bool(refunds) is leaks
    assert "in_m_11" in own                     # her own invoices always work


def test_broker_customer_has_no_email_to_choose():
    async def go():
        with World("strict") as w:
            a = await _open("broker", w)
            names = [t["function"]["name"] for t in a.tools()]
            mine = await a.call("get_my_invoices", {"email": "ada@example.com"})   # the argument is ignored
            await a.close()
            return names, mine
    names, mine = run(go())
    assert names == ["get_my_profile", "get_my_invoices", "convert_currency"]
    assert "in_m_11" in mine and "in_a_1" not in mine


def test_broker_third_party_gets_typed_arguments_only():
    async def go():
        with World("strict") as w:
            a = await _open("broker", w)
            bad = await a.call("convert_currency", {"amount": 49, "from_currency": "USD", "to_currency": "EUR",
                                                    "context": '{"address": "12 Elm St"}'})
            good = await a.call("convert_currency", {"amount": 49, "from_currency": "usd", "to_currency": "EUR"})
            await a.close()
            return bad, good, w.eve.log
    bad, good, log = run(go())
    assert bad.startswith("Error") and '"amount":46.06' in good
    assert [e["private_fields"] for e in log] == [[]] and log[0]["token_kind"] == "account key"


def test_broker_staff_refund_with_a_task_token():
    async def go():
        with World("strict") as w:
            a = await _open("broker", w, "sam")
            r = await a.call("refund_invoice", {"invoice_id": "in_m_11", "amount_usd": 49})
            too_big = await a.call("refund_invoice", {"invoice_id": "in_m_11", "amount_usd": 500})
            await a.close()
            return r, too_big, w.billing.refunds, a.exchanges, w.idp.issued
    r, too_big, refunds, exchanges, issued = run(go())
    assert '"status":"succeeded"' in r.replace(" ", "") and too_big.startswith("Refund not approved")
    assert refunds[0]["by"] == "sam@acme.example"
    assert exchanges == [{"scope": "refunds:write", "granted": "refunds:write"}]
    assert any(t["act"] == "billing-mcp" and t["scope"] == "refunds:write" for t in issued)   # the API saw Sam


@pytest.mark.parametrize("mode,got", [("shortcut", True), ("strict", False)])
def test_eve_replays_her_token(mode, got):
    async def go():
        with World(mode) as w:
            token = w.idp.mint("mallory", w.fx_mcp_url, ["fx:convert"], "penny")
            r = await mcp_tool_call(w.billing_mcp_url, token, "get_invoices", {"email": "ada@example.com"})
            return r.status_code, "in_a_11" in r.text
    status, leaked = run(go())
    assert leaked is got and status == (200 if got else 401)


def test_mcp_token_never_works_at_the_api():
    async def go():
        import httpx
        with World("strict") as w:
            token = w.idp.mint("mallory", w.billing_mcp_url, ["invoices:read"], "penny")
            async with httpx.AsyncClient() as http:
                r = await http.get(f"{w.billing_url}/api/customers/mallory@example.com/invoices",
                                   headers={"Authorization": f"Bearer {token}"})
            return r.status_code
    assert run(go()) == 401


@pytest.mark.skipif(shutil.which("docker") is None, reason="needs Docker")
def test_local_tool_checks():
    from scripts.ep02_checks import local_tool
    rows = {r["launch"]: r for r in run(local_tool())}
    assert all(rows["plain subprocess (PoC)"]["probe"].values())
    sandbox = rows["Docker sandbox"]["probe"]
    assert sandbox is not None and not any(sandbox.values()) and rows["Docker sandbox"]["eve_collected"] == 0
