"""Composite case score for the investigation flow.

Each completed step contributes a 0-100 sub-score. Steps the analyst skipped
are left out and the remaining weights are rescaled, so a partial case still
gets an honest score, and the app shows how much of the case is complete.
Weights are illustrative, not calibrated.
"""
from __future__ import annotations

WEIGHTS = {"market": 0.15, "news": 0.20, "media": 0.30, "flags": 0.35}
LABELS = {"market": "Market risk", "news": "News sentiment", "media": "Adverse media", "flags": "Red flags"}
BANDS = [(0, "Low"), (35, "Medium"), (60, "High")]  # score >= threshold -> band

_CONF = {"low": 0.4, "medium": 0.7, "high": 1.0}


def market_score(vol: float, max_dd: float) -> float:
    """Annualised volatility of 60%+ or a 50%+ drawdown counts as maximum market risk."""
    v = min(max(vol, 0) / 0.60, 1)
    d = min(abs(min(max_dd, 0)) / 0.50, 1)
    return round(100 * (0.6 * v + 0.4 * d), 1)


def news_score(labels: list[str]) -> float:
    """Share of classified headlines that are negative (Mixed counts half)."""
    known = [s for s in labels if s in {"Positive", "Negative", "Neutral", "Mixed"}]
    if not known:
        return 0.0
    neg = sum(1.0 if s == "Negative" else 0.5 if s == "Mixed" else 0.0 for s in known)
    return round(100 * neg / len(known), 1)


def media_score(rows: list[dict]) -> float:
    """Confidence-weighted share of snippets flagged for financial crime, scaled up.

    Two confident flags out of ten headlines is already a serious signal, so the
    share is multiplied by 3 and capped at 100.
    """
    if not rows:
        return 0.0
    w = sum(_CONF.get(str(r.get("confidence", "")).lower(), 0.7) for r in rows if r.get("flag"))
    return round(min(100.0, 300 * w / len(rows)), 1)


def flags_score(score: int, max_score: int) -> float:
    return round(100 * score / max_score, 1) if max_score else 0.0


def band(score: float) -> str:
    return next(label for threshold, label in reversed(BANDS) if score >= threshold)


def composite(parts: dict[str, float | None]) -> dict:
    """Combine available sub-scores. Returns score, band, completeness and each part's contribution."""
    done = {k: v for k, v in parts.items() if k in WEIGHTS and v is not None}
    completeness = sum(WEIGHTS[k] for k in done)
    if not done:
        return {"score": None, "band": "Not scored", "completeness": 0.0, "contributions": {}}
    total_w = sum(WEIGHTS[k] for k in done)
    contributions = {k: round(v * WEIGHTS[k] / total_w, 1) for k, v in done.items()}
    score = round(sum(contributions.values()), 1)
    return {"score": score, "band": band(score), "completeness": round(completeness, 2),
            "contributions": contributions}
