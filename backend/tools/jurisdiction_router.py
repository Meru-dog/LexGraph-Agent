"""jurisdiction_router — detect jurisdiction from text."""

from typing import Literal

JP_MARKERS = [
    "会社法", "民法", "金商法", "金融商品取引法", "株式会社", "日本",
    "kaisha", "kabushiki", "fiea", "tokyo", "osaka", "japan",
    "companies act", "civil code article",
]
US_MARKERS = [
    "delaware", "sec", "securities exchange act", "ucc", "us gaap",
    "federal", "state of", "new york", "california", "united states",
    "contract act", "cfius", "hart-scott",
]


def jurisdiction_router(text: str) -> Literal["JP", "US"]:
    """Detect jurisdiction from input text.

    Strategy: explicit JP/US tag detection → langdetect → keyword scoring.
    Phase 3: add LLM-based classification for ambiguous queries.
    """
    lower = text.lower()

    # Explicit tags
    if "jp" in lower or "japan" in lower:
        return "JP"
    if "us" in lower or "united states" in lower or "american" in lower:
        return "US"

    jp_score = sum(1 for m in JP_MARKERS if m in lower)
    us_score = sum(1 for m in US_MARKERS if m in lower)

    # Japanese character detection
    if any("\u3040" <= c <= "\u9FFF" for c in text):
        jp_score += 3

    return "JP" if jp_score >= us_score else "US"
