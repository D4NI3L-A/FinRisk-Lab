"""Demo mode: simulated AI answers for when no API key is configured.

The hosted demo runs without keys, so visitors can't spend anyone's credit. Instead of
an error, each AI task gets a transparent rule-based answer in the same JSON format the
real model returns. Every answer is labelled as a demo in the app.
"""
from __future__ import annotations

import json
import re

POSITIVE = ["beat", "beats", "raises", "raised", "record", "growth", "surge", "jumps", "completes", "partners",
            "opens", "launch", "upgrade", "strong", "wins", "profit", "creating", "expands", "higher"]
NEGATIVE = ["delay", "fine", "fined", "falls", "fell", "cut", "cuts", "reduction", "review", "probe", "charged",
            "plunge", "investigat", "denies", "loss", "lawsuit", "sanction", "bribe", "fraud", "launder", "weak",
            "downgrade", "layoff", "recall", "warning", "slump", "outflows", "falsif"]
CATEGORIES = [
    ("money_laundering", ["launder", "anti-money", "aml"]),
    ("sanctions", ["sanction", "dual-use", "embargo"]),
    ("bribery_corruption", ["bribe", "corrupt", "kickback"]),
    ("fraud", ["fraud", "falsif", "embezzl", "ponzi", "misled"]),
    ("tax_evasion", ["tax evasion", "tax fraud", "offshore account"]),
    ("terrorist_financing", ["terror"]),
    ("regulatory_enforcement", ["fined", "fine ", "regulator", "enforcement", "penalty", "charged", "probe"]),
]


def _numbered_lines(prompt: str) -> list[str]:
    """The workflows send items as '0. text' lines; return the texts in order."""
    return [m.group(1) for m in re.finditer(r"^\d+\.\s+(.*)$", prompt, flags=re.M)]


def _has(text: str, words: list[str]) -> list[str]:
    t = text.lower()
    return [w for w in words if w in t]


def sentiment(prompt: str, allow_mixed: bool) -> dict:
    results = []
    for i, line in enumerate(_numbered_lines(prompt)):
        pos, neg = _has(line, POSITIVE), _has(line, NEGATIVE)
        if pos and neg and allow_mixed:
            label, why = "Mixed", f"both good ({pos[0]}) and bad ({neg[0]}) news"
        elif neg and len(neg) >= len(pos):
            label, why = "Negative", f"keyword: {neg[0]}"
        elif pos:
            label, why = "Positive", f"keyword: {pos[0]}"
        else:
            label, why = "Neutral", "no strong signal words"
        results.append({"index": i, "sentiment": label, "confidence": 0.6 if label != "Neutral" else 0.5,
                        "reasoning": f"Demo rule: {why}"})
    return {"results": results}


def adverse_media(prompt: str) -> dict:
    results = []
    for i, line in enumerate(_numbered_lines(prompt)):
        t = line.lower()
        category = next((c for c, words in CATEGORIES if any(w in t for w in words)), "none")
        flag = category != "none"
        allegation = any(w in t for w in ("alleged", "denies", "investigat", "probe", "reports"))
        results.append({
            "index": i, "flag": flag, "category": category,
            "confidence": ("medium" if allegation else "high") if flag else "low",
            "reasoning": (f"Demo rule: mentions {category.replace('_', ' ')}" + (" (allegation)" if allegation else ""))
            if flag else "Demo rule: ordinary business news",
        })
    return {"results": results}


def _find(pattern: str, text: str) -> str:
    m = re.search(pattern, text, flags=re.I)
    return m.group(1).strip() if m else "Not stated"


def earnings(prompt: str) -> dict:
    t = prompt
    sentences = re.split(r"(?<=[.!?])\s+", t)
    highlights = [s.strip() for s in sentences if _has(s, POSITIVE)][:4]
    risks = [s.strip() for s in sentences if _has(s, NEGATIVE + ["uncertain", "softness", "monitor"])][:4]
    pos, neg = sum(bool(_has(s, POSITIVE)) for s in sentences), sum(bool(_has(s, NEGATIVE)) for s in sentences)
    return {
        "company": _find(r"welcome to ([A-Z][\w&.\- ]+?)(?:'s|’s)", t),
        "quarter": _find(r"((?:first|second|third|fourth)[- ]quarter(?: \d{4})?|(?:fiscal )?Q[1-4](?: \d{4})?)", t),
        "revenue": _find(r"revenue (?:was|of|reached)\s*([€$£]?\s?[\d.,]+\s?(?:billion|million|bn|m)?)", t),
        "eps": _find(r"(?:earnings per share|EPS)[^.\d€$£]*?([€$£]?\d+\.\d+)", t),
        "guidance": _find(r"((?:raising|expect|guidance)[^.]*\.)", t),
        "highlights": highlights or ["Not stated"],
        "risks": risks or ["Not stated"],
        "outlook": "Demo summary built from keyword rules. Add an API key for a real analyst-style summary.",
        "tone": "Positive" if pos > neg * 1.5 else "Negative" if neg > pos * 1.5 else "Mixed",
    }


def red_flags(prompt: str) -> dict:
    try:
        payload = json.loads(prompt.split("\n", 2)[-1])
    except (json.JSONDecodeError, IndexError):
        payload = {}
    flags = payload.get("selected_flags", [])
    band = (payload.get("rule_based_score") or {}).get("band", "Low")
    drivers = flags[:4] or ["No red flags selected"]
    narrative = (
        f"This counterparty shows {len(flags)} of the listed risk factors, giving a {band.lower()} rule-based "
        "rating. " + (f"The main concerns are {', '.join(f.lower() for f in flags[:2])}. " if flags else "")
        + "This is a demo narrative written by rules; add an API key for a model-written assessment."
    )
    steps = {"High": ["Escalate to compliance", "Verify beneficial ownership with registry documents",
                      "Screen owners and directors against sanctions and PEP lists"],
             "Medium": ["Request ownership and source-of-funds documents", "Repeat adverse-media screening"],
             "Low": ["Standard due diligence", "Re-screen at the next periodic review"]}[band if band in ("High", "Medium") else "Low"]
    return {"risk_rating": band, "narrative": narrative, "key_drivers": drivers,
            "recommended_next_steps": steps, "divergence_note": ""}


def respond(prompt: str, system: str, json_mode: bool) -> str:
    """Pick the right simulated answer from the system message."""
    if not json_mode:
        return "OK (demo mode, no API key)"
    if "news classifier" in system:
        return json.dumps(sentiment(prompt, allow_mixed="Mixed" in system))
    if "adverse-media" in system or "screening news" in system:
        return json.dumps(adverse_media(prompt))
    if "earnings call" in system:
        return json.dumps(earnings(prompt))
    if "counterparty risk" in system:
        return json.dumps(red_flags(prompt))
    return json.dumps({"results": []})
