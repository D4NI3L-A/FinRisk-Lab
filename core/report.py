"""Case report export: turn an investigation into a Markdown document."""
from __future__ import annotations

import datetime as dt

from core.scoring import LABELS

ACTIONS = {
    "Low": "Standard due diligence. Re-check at the next periodic review.",
    "Medium": "Enhanced due diligence: verify beneficial ownership and source of funds before proceeding.",
    "High": "Escalate to compliance. Do not proceed until a reviewer has checked every flag against primary sources.",
    "Not scored": "Complete at least one scored step to get a recommendation.",
}


def _pct(x):
    return "n/a" if x is None else f"{x:+.1%}"


def build_markdown(case: dict, result: dict) -> str:
    p = case.get("profile", {})
    m = case.get("market_metrics") or {}
    score_txt = "n/a" if result["score"] is None else f"{result['score']:.0f}%"
    lines = [
        f"# Case report: {p.get('name') or case['ticker']} ({case['ticker']})",
        f"Generated {dt.datetime.now():%d %b %Y %H:%M} with FinRisk Lab. Educational prototype; "
        "not financial advice and not a compliance decision.",
        "",
        "## Verdict",
        f"- Risk score: **{score_txt}** ({result['band']})",
        f"- Evidence completed: {result['completeness']:.0%} of the scoring weight",
        f"- Recommended action: {ACTIONS[result['band']]}",
        "",
        "## Score breakdown",
    ]
    for k, label in LABELS.items():
        sub = case.get("scores", {}).get(k)
        contrib = result["contributions"].get(k)
        lines.append(f"- {label}: " + ("not completed" if sub is None else f"{sub:.0f}/100, adds {contrib:.1f} points"))
    lines += ["", "## Company",
              f"- Sector: {p.get('sector') or 'n/a'} · Industry: {p.get('industry') or 'n/a'} · "
              f"Country: {p.get('country') or 'n/a'}"]
    if m:
        lines += ["", "## Market risk (1 year)",
                  f"- Return {_pct(m.get('period'))}, volatility {m.get('vol', 0):.1%}, "
                  f"max drawdown {_pct(m.get('max_dd'))}, beta {m['beta']:.2f}" if m.get("beta") is not None
                  else f"- Return {_pct(m.get('period'))}, volatility {m.get('vol', 0):.1%}, "
                       f"max drawdown {_pct(m.get('max_dd'))}"]
    if case.get("news_rows"):
        lines += ["", "## News sentiment"]
        lines += [f"- [{r['sentiment']}] {r['headline']}" for r in case["news_rows"]]
    if case.get("media_rows"):
        flagged = [r for r in case["media_rows"] if r.get("flag")]
        lines += ["", f"## Adverse media ({len(flagged)} of {len(case['media_rows'])} flagged)"]
        lines += [f"- {r['category']} ({r['confidence']}): {r['snippet']} — {r['reasoning']}" for r in flagged] or ["- None flagged"]
    if case.get("flags") is not None:
        lines += ["", "## Red flags selected"]
        lines += [f"- {f}" for f in case["flags"]] or ["- None"]
        if case.get("narrative"):
            lines += ["", "### AI narrative", case["narrative"]]
    lines += ["", "## Sources checked"]
    lines += [f"- [{k}]({v})" for k, v in case.get("links", {}).items()]
    return "\n".join(lines) + "\n"
