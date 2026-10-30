"""Visual system for FinRisk Lab: colour tokens, a little CSS, and small HTML helpers.

Fonts and base colours live in .streamlit/config.toml; this file only adds what
Streamlit's theme options can't express.
"""
from __future__ import annotations

import html

import streamlit as st

COLORS = {
    "ink": "#16233A",       # text, sidebar
    "paper": "#F5F6F3",     # page background
    "regulator": "#1F4E79", # primary actions
    "muted": "#5B6676",     # secondary text
    "rule": "#D3D9E0",      # borders and dividers
    "clear": "#2F6B4F",     # low risk / positive
    "flag": "#B7791F",      # needs review / mixed
    "risk": "#A4262C",      # high risk / negative
    "flag_tint": "#FBF3E4",
}

SENTIMENT_COLORS = {
    "Positive": COLORS["clear"],
    "Negative": COLORS["risk"],
    "Neutral": "#8A94A6",
    "Mixed": COLORS["flag"],
    "Unclassified": "#C9CFD7",
}

_CSS = """
<style>
/* Page width and rhythm */
[data-testid="stMainBlockContainer"] { max-width: 1180px; padding-top: 2.2rem; padding-bottom: 4rem; }
[data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] li { line-height: 1.6; }
[data-testid="stMarkdownContainer"] p { max-width: 72ch; }

/* Tabs read as a section index, not pills */
[data-testid="stTabs"] [role="tablist"] { gap: 1.75rem; border-bottom: 1px solid #D3D9E0; }
[data-testid="stTabs"] [role="tab"] { padding: 0.6rem 0; font-weight: 600; }
[data-testid="stTabs"] [role="tab"] p { font-size: 0.98rem; }

/* Metrics: tabular figures, quiet labels */
[data-testid="stMetricValue"] { font-variant-numeric: tabular-nums; font-weight: 700; letter-spacing: -0.01em; }
[data-testid="stMetricLabel"] p { color: #5B6676; font-size: 0.85rem; }
[data-testid="stMetric"] { border-top: 3px solid #16233A; padding-top: 0.6rem; }

/* Sidebar brand */
.brand { display: flex; align-items: center; gap: 0.75rem; margin: 0.25rem 0 1.25rem; }
.brand-mark { display: inline-grid; place-items: center; width: 2.3rem; height: 2.3rem;
  border: 2px solid #E9EDF2; border-radius: 0.375rem; font-weight: 800; letter-spacing: 0.02em; }
.brand-name { font-weight: 800; font-size: 1.15rem; line-height: 1.1; }
.brand-sub { font-size: 0.8rem; opacity: 0.75; line-height: 1.3; }
.keyrow { display: flex; align-items: center; gap: 0.5rem; font-size: 0.82rem; margin: 0.2rem 0; }
.keyrow code { flex: 1; background: transparent; padding: 0; color: inherit; }
.dot { width: 0.55rem; height: 0.55rem; border-radius: 50%; flex: none; }
.dot.ok { background: #4CA37A; } .dot.no { background: #D9A13B; }
.fineprint { font-size: 0.75rem; opacity: 0.7; line-height: 1.45; margin-top: 2rem; }

/* Overview hero */
.hero { padding: 1.5rem 0 2rem; }
.hero h1 { font-size: clamp(2rem, 4.2vw, 3.1rem); line-height: 1.05; letter-spacing: -0.025em;
  font-weight: 800; color: #16233A; margin: 0 0 1rem; padding: 0; }
.hero p { font-size: 1.12rem; color: #3A4658; max-width: 62ch; line-height: 1.6; margin: 0; }

/* Triage pipeline: one strip, four stages */
.pipeline { display: grid; grid-template-columns: repeat(4, 1fr); border: 1px solid #16233A;
  border-radius: 0.375rem; overflow: hidden; margin: 0 0 2.5rem; background: #FFFFFF; }
.stage { padding: 1rem 1.1rem 1.15rem; border-right: 1px solid #D3D9E0; position: relative; }
.stage:last-child { border-right: none; background: #16233A; color: #F5F6F3; }
.stage .n { font-size: 0.8rem; font-weight: 700; color: #1F4E79; font-variant-numeric: tabular-nums; }
.stage:last-child .n { color: #9DB9D6; }
.stage h4 { margin: 0.15rem 0 0.35rem; padding: 0; font-size: 1.05rem; font-weight: 800; color: inherit; }
.stage p { margin: 0; font-size: 0.88rem; line-height: 1.45; opacity: 0.85; }
.stage:not(:last-child)::after { content: ""; position: absolute; right: -6px; top: 50%;
  width: 10px; height: 10px; background: #FFFFFF; border-top: 1px solid #D3D9E0;
  border-right: 1px solid #D3D9E0; transform: translateY(-50%) rotate(45deg); z-index: 1; }
@media (max-width: 760px) {
  .pipeline { grid-template-columns: 1fr 1fr; }
  .stage:nth-child(2) { border-right: none; }
  .stage:nth-child(-n+2) { border-bottom: 1px solid #D3D9E0; }
  .stage::after { display: none; }
}

.rule { border-top: 1px solid #D3D9E0; margin: 2rem 0 1.5rem; }

/* Tool headers */
.intro { margin: 0.75rem 0 1.25rem; }
.intro h2 { font-size: 1.7rem; font-weight: 800; letter-spacing: -0.015em; margin: 0; padding: 0; color: #16233A; }
.intro p { color: #5B6676; margin: 0.3rem 0 0; font-size: 1rem; }
.empty { color: #5B6676; border: 1px dashed #C3CBD5; border-radius: 0.375rem;
  padding: 1.1rem 1.25rem; margin-top: 1.5rem; }

/* Chips and verdicts */
.chip { display: inline-block; padding: 0.2rem 0.6rem; border-radius: 999px; font-size: 0.85rem;
  font-weight: 700; border: 1.5px solid currentColor; white-space: nowrap; }
.chip.clear { color: #2F6B4F; background: #EAF3EE; }
.chip.flag { color: #8A5A12; background: #FBF3E4; }
.chip.risk { color: #A4262C; background: #F8E9EA; }
.chip.muted { color: #5B6676; background: #EEF0F3; }
.verdicts { display: flex; flex-wrap: wrap; align-items: center; gap: 0.6rem; margin: 0.4rem 0 1rem; }
.verdict-note { color: #5B6676; font-size: 0.92rem; }

/* Earnings report header */
.report-head { display: flex; flex-wrap: wrap; align-items: baseline; gap: 0.75rem; margin-top: 1.5rem; }
.report-head h3 { margin: 0; padding: 0; font-weight: 800; }
.report-head .quarter { color: #5B6676; font-weight: 600; }
blockquote.guidance { border-left: 3px solid #1F4E79; margin: 1rem 0 1.25rem; padding: 0.4rem 0 0.4rem 1rem;
  color: #16233A; max-width: 72ch; }

/* Risk band meter */
.meter { margin: 0.25rem 0 1rem; }
.meter .score { font-size: 2.6rem; font-weight: 800; line-height: 1; font-variant-numeric: tabular-nums;
  letter-spacing: -0.02em; }
.meter .score small { font-size: 1rem; font-weight: 600; color: #5B6676; letter-spacing: 0; }
.meter .track { position: relative; display: flex; height: 0.7rem; margin: 0.9rem 0 0.35rem;
  border-radius: 0.2rem; overflow: visible; }
.meter .seg { height: 100%; opacity: 0.28; }
.meter .seg.on { opacity: 1; }
.meter .pin { position: absolute; top: -0.35rem; width: 3px; height: 1.4rem; background: #16233A;
  border-radius: 2px; transform: translateX(-1.5px); transition: left 300ms ease; }
.meter .labels { display: flex; font-size: 0.78rem; color: #5B6676; }
.meter .labels span { text-align: left; white-space: nowrap; }
@media (prefers-reduced-motion: reduce) { .meter .pin { transition: none; } }
</style>
"""


def inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def chip(text: str, kind: str = "muted") -> str:
    return f'<span class="chip {kind}">{html.escape(text)}</span>'


def section_intro(title: str, purpose: str) -> None:
    st.markdown(f'<div class="intro"><h2>{html.escape(title)}</h2><p>{html.escape(purpose)}</p></div>',
                unsafe_allow_html=True)


def pipeline(stages: list[tuple[str, str]]) -> None:
    """The triage sequence on the overview page. Numbered because it is a real order of steps."""
    cells = "".join(
        f'<div class="stage"><span class="n">{i}</span><h4>{html.escape(t)}</h4><p>{html.escape(d)}</p></div>'
        for i, (t, d) in enumerate(stages, start=1)
    )
    st.markdown(f'<div class="pipeline">{cells}</div>', unsafe_allow_html=True)


def band_meter(score: int, max_score: int, bands: list[tuple[int, str]], current: str) -> str:
    """Score readout plus a track split into the Low / Medium / High bands, with a pin at the score."""
    colors = {"Low": COLORS["clear"], "Medium": COLORS["flag"], "High": COLORS["risk"]}
    edges = [t for t, _ in bands] + [max_score + 1]
    segs, labels = [], []
    for (start, name), end in zip(bands, edges[1:]):
        width = (end - start) / (max_score + 1) * 100
        on = " on" if name == current else ""
        segs.append(f'<div class="seg{on}" style="width:{width:.2f}%;background:{colors[name]}"></div>')
        labels.append(f'<span style="width:{width:.2f}%">{name}</span>')
    pin = (score + 0.5) / (max_score + 1) * 100
    return (
        f'<div class="meter"><div class="score">{score}<small> / {max_score} · {current}</small></div>'
        f'<div class="track">{"".join(segs)}<div class="pin" style="left:{pin:.2f}%"></div></div>'
        f'<div class="labels">{"".join(labels)}</div></div>'
    )
