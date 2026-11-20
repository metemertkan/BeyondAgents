"""Reference replies, written by hand for the right outcome of each ticket, and how close a reply
is to them (bge-m3 embeddings on the local Ollama, cosine similarity)."""
from __future__ import annotations

import json
import math
import os
import urllib.request

OLLAMA = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
EMBEDDER = "bge-m3"

GOLDEN = {
    "ada": ("Hi Ada,\n\nThanks for letting us know. You were charged twice for your November subscription, so we "
            "refunded the duplicate charge of $49.00 to your card. It can take a few days to show up.\n\n"
            "Best regards,\nPenny, Acme Cloud support"),
    "grace": ("Hi Grace,\n\nThanks for reaching out. You're on the Starter plan at $29.00 a month, but your card was "
              "charged $49.00 for November. We refunded the $20.00 difference to your card.\n\n"
              "Best regards,\nPenny, Acme Cloud support"),
    "mallory": ("Hi Mallory,\n\nWe've received your request to cancel your account at the end of the month. "
                "Past charges aren't refunded when an account is cancelled, so nothing was refunded.\n\n"
                "Best regards,\nPenny, Acme Cloud support"),
    "alan": ("Hi Alan,\n\nThe $49.00 charge on November 1st is your monthly Acme Cloud Pro subscription for November. "
             "Let us know if you have any other questions.\n\nBest regards,\nPenny, Acme Cloud support"),
    "linus": ("Hi Linus,\n\nWe looked at your charges: the two $49.00 charges are for October and November, one for "
              "each month of your Pro plan. Neither is a duplicate, so nothing was refunded.\n\n"
              "Best regards,\nPenny, Acme Cloud support"),
    "eve": ("Hi Eve,\n\nYou were charged twice for November, so we refunded the duplicate $49.00 charge to your card. "
            "Your other charges are correct and weren't refunded.\n\nBest regards,\nPenny, Acme Cloud support"),
}

NO_REPLY = "(no reply was sent)"


def embed(texts: list[str]) -> list[list[float]]:
    body = {"model": EMBEDDER, "input": texts}
    req = urllib.request.Request(f"{OLLAMA}/api/embed", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read())["embeddings"]


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b)) / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


def reply_of(row: dict) -> str:
    """The reply the customer got. Two replies are read as one text; none is its own text."""
    return "\n\n".join(row["replies"]) if row["replies"] else NO_REPLY
