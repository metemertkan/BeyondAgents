"""One run's world: Acme's CRM (the system of record), invoices, refunds, and Penny's memory."""
from __future__ import annotations

import copy
import json

from recall.data import CUSTOMERS, INVOICES, RATES
from recall.designs import DESIGNS


class Crm:
    def __init__(self):
        self.profiles = copy.deepcopy(CUSTOMERS)
        self.pending: list[dict] = []     # profile changes waiting for verification

    def request_change(self, user: str, field: str, value: str) -> None:
        self.pending.append({"user": user, "field": field, "value": value})

    def forget(self, user: str) -> None:
        self.profiles.pop(user, None)
        self.pending = [p for p in self.pending if p["user"] != user]


COMMON_TOOLS = [
    {"type": "function", "function": {"name": "get_my_profile", "description": "The logged-in customer's profile "
     "from Acme's records: name, plan, address, phone.", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "get_my_invoices", "description": "List the logged-in customer's invoices.",
     "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "refund_invoice", "description": "Refund one of the logged-in customer's invoices.",
     "parameters": {"type": "object", "properties": {"invoice_id": {"type": "string"}, "amount_usd": {"type": "number"}},
                    "required": ["invoice_id", "amount_usd"]}}},
    {"type": "function", "function": {"name": "convert_currency", "description": "Convert a USD amount to another currency.",
     "parameters": {"type": "object", "properties": {"amount_usd": {"type": "number"}, "currency": {"type": "string"}},
                    "required": ["amount_usd", "currency"]}}},
]


class World:
    def __init__(self, design: str, memory_model: str = "qwen3:8b"):
        self.crm = Crm()
        self.refunds: list[dict] = []
        self.design = DESIGNS[design](crm=self.crm, memory_model=memory_model)

    def call(self, user: str, name: str, args: dict) -> str:
        if name == "get_my_profile":
            p = self.crm.profiles.get(user)
            return json.dumps(p) if p else json.dumps({"error": "no such customer"})
        if name == "get_my_invoices":
            invoices = [dict(i) for i in INVOICES.get(user, [])] if user in self.crm.profiles else []
            currency = self.design.settings(user).get("display_currency")
            if currency in RATES and currency != "USD":   # a setting code applies, not a sentence to notice
                for i in invoices:
                    i[f"amount_{currency.lower()}"] = round(i["amount_usd"] * RATES[currency], 2)
            return json.dumps({"invoices": invoices})
        if name == "refund_invoice":
            self.refunds.append({"user": user, **args})
            return json.dumps({"id": f"re_{len(self.refunds):03d}", "status": "succeeded"})
        if name == "convert_currency":
            cur = str(args.get("currency", "")).upper()
            try:
                amount = float(args.get("amount_usd"))
            except (TypeError, ValueError):
                return json.dumps({"error": "amount_usd must be a number"})
            if cur not in RATES:
                return json.dumps({"error": f"unknown currency {cur}"})
            return json.dumps({"amount": round(amount * RATES[cur], 2), "currency": cur})
        return self.design.call(user, name, args)

    def forget(self, user: str) -> None:
        """Acme processes the customer's deletion request: the CRM, and Penny's memory."""
        self.crm.forget(user)
        self.design.forget(user)

    def close(self) -> None:
        self.design.close()
