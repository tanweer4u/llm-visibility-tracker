"""
brand_detector.py
=================
Detects brand mentions, positions, and ACKO sentiment in AI-generated text.
"""

import re
from config import (
    TRACKED_BRANDS,
    BRAND_SEARCH_PATTERNS,
    KNOWN_UNLISTED_BRANDS,
    POSITIVE_KEYWORDS,
    NEGATIVE_KEYWORDS,
)


def find_brand_mentions(text: str) -> list[str]:
    """
    Return tracked brands found in *text*, sorted by position of first match.
    Deduplication: a brand is counted once even if mentioned multiple times.
    """
    if not text:
        return []

    positions: list[tuple[str, int]] = []
    for brand, pattern in BRAND_SEARCH_PATTERNS.items():
        match = pattern.search(text)
        if match:
            positions.append((brand, match.start()))

    positions.sort(key=lambda x: x[1])
    return [brand for brand, _ in positions]


def get_acko_position(text: str) -> str:
    """
    Return ACKO's ordinal rank (1st, 2nd, …) among all brand first-mentions,
    or 'Not mentioned'.
    """
    brands = find_brand_mentions(text)
    if "ACKO" not in brands:
        return "Not mentioned"
    rank = brands.index("ACKO") + 1
    suffixes = {1: "st", 2: "nd", 3: "rd"}
    suffix = suffixes.get(rank if rank <= 3 else 0, "th")
    return f"{rank}{suffix} mention"


def get_acko_sentiment(text: str) -> str:
    """
    Return Positive / Neutral / Negative based on keyword proximity around
    each ACKO mention (±150 characters).  Returns 'Not mentioned' if absent.
    """
    pattern = BRAND_SEARCH_PATTERNS["ACKO"]
    matches = list(pattern.finditer(text))
    if not matches:
        return "Not mentioned"

    scores: list[int] = []
    for m in matches:
        start = max(0, m.start() - 150)
        end = min(len(text), m.end() + 150)
        ctx = text[start:end].lower()

        pos = sum(1 for kw in POSITIVE_KEYWORDS if kw in ctx)
        neg = sum(1 for kw in NEGATIVE_KEYWORDS if kw in ctx)

        if pos > neg:
            scores.append(1)
        elif neg > pos:
            scores.append(-1)
        else:
            scores.append(0)

    avg = sum(scores) / len(scores)
    if avg > 0:
        return "Positive"
    if avg < 0:
        return "Negative"
    return "Neutral"


def find_unlisted_brands(text: str) -> list[str]:
    """Return known insurance brands that appear in text but are NOT in TRACKED_BRANDS."""
    if not text:
        return []
    text_lower = text.lower()
    return [b for b in KNOWN_UNLISTED_BRANDS if b.lower() in text_lower]


def analyze_response(text: str) -> dict:
    """
    Full analysis of a single AI response.

    Returns
    -------
    dict with keys:
        acko_mentioned   : "Yes" | "No"
        acko_position    : e.g. "1st mention" | "Not mentioned"
        acko_sentiment   : "Positive" | "Neutral" | "Negative" | "Not mentioned"
        brands_mentioned : list[str]  — tracked brands, in order of appearance
        brand_count      : int
        unlisted_brands  : list[str]
    """
    brands = find_brand_mentions(text)
    acko_found = "ACKO" in brands

    return {
        "acko_mentioned":  "Yes" if acko_found else "No",
        "acko_position":   get_acko_position(text) if acko_found else "Not mentioned",
        "acko_sentiment":  get_acko_sentiment(text),
        "brands_mentioned": brands,
        "brand_count":     len(brands),
        "unlisted_brands": find_unlisted_brands(text),
    }
