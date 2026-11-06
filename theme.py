"""Visual system for FinRisk Lab: colour tokens, CSS and small HTML helpers.

Fonts, base colours and radius live in .streamlit/config.toml. This file adds what
Streamlit's theme options can't express.
"""
from __future__ import annotations

import html

import streamlit as st

COLORS = {
    "ink": "#0E1B33",
    "muted": "#5E6B82",
    "line": "#E3E8F0",
    "canvas": "#F5F7FB",
    "surface": "#FFFFFF",
    "primary": "#2A5BD7",
    "primary_soft": "#E8EEFC",
    "clear": "#0F9D6B",
    "flag": "#D98E04",
    "risk": "#E04848",
    "flag_tint": "#FFF6E5",
}

SENTIMENT_COLORS = {
    "Positive": COLORS["clear"],
    "Negative": COLORS["risk"],
    "Neutral": "#8B95A8",
    "Mixed": COLORS["flag"],
    "Unclassified": "#C9D1DE",
}
BAND_COLORS = {"Low": COLORS["clear"], "Medium": COLORS["flag"], "High": COLORS["risk"], "Not scored": "#8B95A8"}
BAND_KIND = {"Low": "clear", "Medium": "flag", "High": "risk"}

_CSS = """
<style>
[data-testid="stMainBlockContainer"] { max-width: 1240px; padding-top: 1.5rem; padding-bottom: 4rem; }
[data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] li { line-height: 1.6; }
[data-testid="stMetricValue"] { font-variant-numeric: tabular-nums; font-weight: 800; letter-spacing: -0.02em; }
[data-testid="stMetricLabel"] p { color: #5E6B82; font-weight: 600; }

/* Page header */
.ph { margin: 0.5rem 0 1.5rem; }
.ph h1 { font-size: clamp(1.8rem, 3.2vw, 2.4rem); font-weight: 800; letter-spacing: -0.03em;
  margin: 0; padding: 0; color: #0E1B33; }
.ph p { color: #5E6B82; font-size: 1.05rem; margin: 0.35rem 0 0; max-width: 68ch; }

/* Home hero */
.hero { padding: 2.2rem 0 1.4rem; }
.hero h1 { font-size: clamp(2.3rem, 5vw, 3.6rem); line-height: 1.02; letter-spacing: -0.035em;
  font-weight: 800; margin: 0 0 1rem; padding: 0; color: #0E1B33; max-width: 16ch; }
.hero p { font-size: 1.15rem; color: #46536B; max-width: 56ch; margin: 0; line-height: 1.55; }
.hero .tag { display: inline-block; font-weight: 700; font-size: 0.85rem; color: #2A5BD7;
  background: #E8EEFC; padding: 0.3rem 0.75rem; border-radius: 999px; margin-bottom: 1.1rem; }

/* Chips */
.chip { display: inline-flex; align-items: center; gap: 0.35rem; padding: 0.22rem 0.7rem; border-radius: 999px;
  font-size: 0.84rem; font-weight: 700; white-space: nowrap; }
.chip.clear { color: #0B7A53; background: #E3F5EE; }
.chip.flag { color: #8F5D00; background: #FFF1D6; }
.chip.risk { color: #B42323; background: #FDE8E8; }
.chip.muted { color: #5E6B82; background: #EDF1F8; }
.chip.primary { color: #2A5BD7; background: #E8EEFC; }
.chips { display: flex; flex-wrap: wrap; gap: 0.45rem; margin: 0.25rem 0 0.75rem; }

/* Step tracker for the investigation */
.steps { display: grid; grid-template-columns: repeat(6, 1fr); gap: 0.4rem; margin: 0.25rem 0 0.5rem; }
.step { height: 6px; border-radius: 999px; background: #E3E8F0; }
.step.done { background: #0F9D6B; }
.step.now { background: #2A5BD7; }

/* Small labelled numbers inside panels */
.kv { display: grid; grid-template-columns: auto 1fr; gap: 0.35rem 1rem; font-size: 0.95rem; }
.kv span:nth-child(odd) { color: #5E6B82; }
.kv span:nth-child(even) { font-weight: 600; }

/* Contribution bars on the verdict */
.bar { margin: 0.55rem 0; }
.bar .top { display: flex; justify-content: space-between; font-size: 0.92rem; font-weight: 600; }
.bar .top span:last-child { font-variant-numeric: tabular-nums; color: #5E6B82; }
.bar .track { height: 8px; background: #EDF1F8; border-radius: 999px; margin-top: 0.3rem; overflow: hidden; }
.bar .fill { height: 100%; border-radius: 999px; }

.verdicts { display: flex; flex-wrap: wrap; align-items: center; gap: 0.6rem; margin: 0.4rem 0 1rem; }
.verdict-note { color: #5E6B82; font-size: 0.92rem; }
.report-head { display: flex; flex-wrap: wrap; align-items: baseline; gap: 0.75rem; margin-top: 1.5rem; }
.report-head h3 { margin: 0; padding: 0; font-weight: 800; }
.report-head .quarter { color: #5E6B82; font-weight: 600; }
blockquote.guidance { border-left: 3px solid #2A5BD7; margin: 1rem 0 1.25rem; padding: 0.4rem 0 0.4rem 1rem; max-width: 72ch; }
.news-meta { color: #5E6B82; font-size: 0.82rem; }
.fineprint { font-size: 0.78rem; color: #5E6B82; line-height: 1.45; }
.empty { color: #5E6B82; border: 1.5px dashed #CBD3E1; border-radius: 0.75rem; padding: 1.1rem 1.25rem; }
</style>
"""


def inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def chip(text: str, kind: str = "muted") -> str:
    return f'<span class="chip {kind}">{html.escape(text)}</span>'


def page_header(title: str, subtitle: str) -> None:
    st.markdown(f'<div class="ph"><h1>{html.escape(title)}</h1><p>{html.escape(subtitle)}</p></div>',
                unsafe_allow_html=True)


def steps_bar(total: int, done: set[int], current: int) -> None:
    cells = "".join(
        f'<div class="step {"done" if i in done else "now" if i == current else ""}"></div>' for i in range(total)
    )
    st.markdown(f'<div class="steps" style="grid-template-columns:repeat({total},1fr)">{cells}</div>',
                unsafe_allow_html=True)


def contribution_bar(label: str, value: float, max_value: float, color: str, note: str = "") -> str:
    width = 0 if not max_value else max(2, min(100, 100 * value / max_value))
    return (f'<div class="bar"><div class="top"><span>{html.escape(label)}</span><span>{html.escape(note)}</span></div>'
            f'<div class="track"><div class="fill" style="width:{width:.1f}%;background:{color}"></div></div></div>')


def gauge(score: float | None, band: str, height: int = 230):
    """Plotly ring gauge for a 0-100 risk score."""
    import plotly.graph_objects as go

    value = 0 if score is None else score
    color = BAND_COLORS.get(band, COLORS["primary"])
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=value,
        number=dict(suffix="%", font=dict(size=44, color=COLORS["ink"])),
        gauge=dict(
            axis=dict(range=[0, 100], tickvals=[0, 35, 60, 100], tickfont=dict(size=11, color=COLORS["muted"])),
            bar=dict(color=color, thickness=0.32),
            bgcolor="#EDF1F8", borderwidth=0,
            steps=[dict(range=[0, 35], color="#EAF6F1"), dict(range=[35, 60], color="#FFF5E1"),
                   dict(range=[60, 100], color="#FDECEC")],
        ),
    ))
    fig.update_layout(height=height, margin=dict(l=20, r=20, t=10, b=0), paper_bgcolor="rgba(0,0,0,0)")
    return fig


def style_fig(fig, height: int = 380):
    """House style for Plotly charts."""
    fig.update_layout(
        height=height, margin=dict(l=8, r=8, t=30, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=COLORS["ink"]), hovermode="x unified",
        legend=dict(orientation="h", y=1.08, x=0, title=None),
        xaxis=dict(showgrid=False, linecolor=COLORS["line"]),
        yaxis=dict(gridcolor="#EDF1F8", zeroline=False),
    )
    return fig
