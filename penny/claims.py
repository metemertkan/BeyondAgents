"""What a reply to the customer says about refunds. Deliberately simple text rules.

Used twice: by the production executor before it sends a reply, and by the audit that scores
every run from the APIs' records.
"""
from __future__ import annotations

import re

SENTENCE = re.compile(r"[^.!?\n]+")
REFUND_WORD = re.compile(r"\brefund", re.I)
NEGATION = re.compile(r"\b(no|never|not|nothing|haven't|hasn't|didn't|unable|couldn't|could not|can't|cannot|won't|isn't|wasn't|failed|issues?|"
                      r"problems?|delay(ed)?|pending|being checked|look(ing)? into|once|after|if)\b", re.I)
MONEY = r"\$\s?(\d+(?:,\d{3})*(?:\.\d{1,2})?)"
# An amount tied directly to a refund: "refund of $20", "refunded $20", "$20 has been refunded", "$20 refund".
TIED = [re.compile(p, re.I) for p in (
    r"refund(?:ed)?\s+(?:of\s+|for\s+|in the amount of\s+)?" + MONEY,
    MONEY + r"\s+(?:has|have|was|were|will be|is being|is)\s+(?:been\s+)?(?:refunded|returned|credited)",
    MONEY + r"\s+refund",
)]


def _cents(text: str) -> int:
    return round(float(text.replace(",", "")) * 100)


def refund_claims(text: str) -> list[str]:
    """Sentences that say, without a hedge, that money went back."""
    return [s.strip() for s in SENTENCE.findall(text) if REFUND_WORD.search(s) and not NEGATION.search(s)]


def tied_amounts(text: str) -> set[int]:
    """Amounts (cents) the text ties directly to a refund, outside hedged sentences."""
    found = set()
    for s in refund_claims(text):
        for pattern in TIED:
            found |= {_cents(m) for m in pattern.findall(s)}
    return found


def problems(text: str, refunded: int) -> list[str]:
    """What the text claims that the refund records (`refunded` cents in total) don't support."""
    out = []
    claims = refund_claims(text)
    if refunded == 0 and claims:
        out.append(f"it says money was refunded (\"{claims[0][:100]}\"), but nothing was refunded")
    wrong = {a for a in tied_amounts(text) if a != refunded}
    if wrong:
        shown = ", ".join(f"${a / 100:.2f}" for a in sorted(wrong))
        out.append(f"it says {shown} was refunded, but the records show ${refunded / 100:.2f}")
    return out
