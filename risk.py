"""Transparent, rule-based counterparty red-flag scoring.

The LLM writes the narrative, but the score itself is deterministic and auditable:
every flag has a visible weight, and the band thresholds are fixed. This mirrors how
real risk-based-approach (RBA) scoring models are built: rules first, judgment on top.

Weights are illustrative, loosely inspired by FATF risk-factor guidance. They are not
calibrated on data and must not be used for real compliance decisions.
"""
from __future__ import annotations

RED_FLAGS: dict[str, int] = {
    "Incorporated in a FATF grey/black-list jurisdiction": 3,
    "Opaque or undisclosed beneficial ownership": 3,
    "Shell-company indicators": 3,
    "Politically exposed person (PEP) involved": 2,
    "Recent adverse media (fraud, bribery, sanctions)": 2,
    "Regulatory fines or enforcement actions": 2,
    "Sector subject to sanctions (energy, defence, dual-use)": 2,
    "Cash-intensive business model": 1,
    "Reliance on third parties / agents": 1,
    "Recent incorporation or frequent name changes": 1,
}

MAX_SCORE = sum(RED_FLAGS.values())
BANDS = [(0, "Low"), (4, "Medium"), (7, "High")]  # score >= threshold -> band


def score_flags(selected: list[str]) -> dict:
    """Return score, band and per-flag contributions for the selected flags."""
    unknown = [f for f in selected if f not in RED_FLAGS]
    if unknown:
        raise ValueError(f"Unknown flag(s): {unknown}")
    contributions = {f: RED_FLAGS[f] for f in selected}
    score = sum(contributions.values())
    band = next(label for threshold, label in reversed(BANDS) if score >= threshold)
    return {"score": score, "max_score": MAX_SCORE, "band": band, "contributions": contributions}
