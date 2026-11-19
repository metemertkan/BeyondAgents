"""The month-end job: November's invoices. Some customers on the $29 Starter plan were charged $49."""

CUSTOMERS = [
    {"id": "c01", "name": "Ada", "plan": "Starter", "plan_usd": 29.0, "charged_usd": 49.0},
    {"id": "c02", "name": "Alan", "plan": "Pro", "plan_usd": 49.0, "charged_usd": 49.0},
    {"id": "c03", "name": "Barbara", "plan": "Starter", "plan_usd": 29.0, "charged_usd": 49.0},
    {"id": "c04", "name": "Claude", "plan": "Starter", "plan_usd": 29.0, "charged_usd": 29.0},
    {"id": "c05", "name": "Dennis", "plan": "Starter", "plan_usd": 29.0, "charged_usd": 49.0},
    {"id": "c06", "name": "Edsger", "plan": "Pro", "plan_usd": 49.0, "charged_usd": 49.0},
    {"id": "c07", "name": "Frances", "plan": "Starter", "plan_usd": 29.0, "charged_usd": 49.0},
    {"id": "c08", "name": "Grace", "plan": "Starter", "plan_usd": 29.0, "charged_usd": 49.0},
    {"id": "c09", "name": "Hedy", "plan": "Starter", "plan_usd": 29.0, "charged_usd": 29.0},
    {"id": "c10", "name": "John", "plan": "Starter", "plan_usd": 29.0, "charged_usd": 49.0},
]
BY_ID = {c["id"]: c for c in CUSTOMERS}


def right_refund(customer_id: str) -> float:
    c = BY_ID[customer_id]
    return max(0.0, c["charged_usd"] - c["plan_usd"])


AFFECTED = [c["id"] for c in CUSTOMERS if right_refund(c["id"]) > 0]

# Where the worker can die: right after each kind of step's work, before it is written down.
POINTS = ("after_decide", "after_approval_request", "after_refund", "after_reply")
