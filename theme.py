"""Visual system for FinRisk Lab: colour tokens, CSS and small HTML helpers.

Fonts, base colours and radius live in .streamlit/config.toml. This file adds what
Streamlit's theme options can't express.
"""
from __future__ import annotations

import html

import streamlit as st

# Chart and data colours. These mid-tones read well on both the dark and the light theme.
COLORS = {
    "ink": "#E7ECF3",
    "muted": "#8A97AD",
    "line": "rgba(138,151,173,0.35)",
    "grid": "rgba(138,151,173,0.16)",
    "track": "rgba(138,151,173,0.18)",
    "primary": "#E5383B",    # signal red: brand, primary actions, alerts
    "info": "#5B8DEF",       # neutral data series (benchmarks, prices)
    "clear": "#2BB673",
    "flag": "#F0A830",
    "risk": "#FF5A5F",
    "flag_tint": "rgba(240,168,48,0.14)",
}

SENTIMENT_COLORS = {
    "Positive": COLORS["clear"],
    "Negative": COLORS["risk"],
    "Neutral": "#8A97AD",
    "Mixed": COLORS["flag"],
    "Unclassified": "rgba(138,151,173,0.45)",
}
BAND_COLORS = {"Low": COLORS["clear"], "Medium": COLORS["flag"], "High": COLORS["risk"], "Not scored": "#8A97AD"}
BAND_KIND = {"Low": "clear", "Medium": "flag", "High": "risk"}

# Streamlit sets `color-scheme` on the app to light or dark, so CSS light-dark() picks the right
# value for whichever theme the viewer chose in the settings menu, with no rerun needed.
_CSS = """
<style>
:root {
  --fr-ink: light-dark(#0E1B33, #E7ECF3);
  --fr-title: light-dark(#0B1628, #F4F6FA);
  --fr-body: light-dark(#46536B, #B4BFD0);
  --fr-muted: light-dark(#5E6B82, #8A97AD);
  --fr-line: light-dark(#DCE2EC, #26324A);
  --fr-raised: light-dark(#EEF2F8, #1A2540);
  --fr-red: light-dark(#D62F33, #E5383B);
  --fr-red-text: light-dark(#B42326, #FF7A7C);
  --fr-red-soft: light-dark(rgba(214,47,51,0.09), rgba(229,56,59,0.13));
  --fr-red-edge: light-dark(rgba(214,47,51,0.30), rgba(229,56,59,0.35));
  --fr-green-text: light-dark(#0B7A4B, #5FD69C);
  --fr-amber-text: light-dark(#8F5D00, #F6C46A);
  --fr-risk-text: light-dark(#B42326, #FF8A8D);
  --fr-dots: light-dark(rgba(14,27,51,0.10), rgba(138,151,173,0.18));
}

/* A thin signal-red line across the top of every page */
[data-testid="stApp"]::before { content: ""; position: fixed; top: 0; left: 0; right: 0; height: 3px;
  background: var(--fr-red); z-index: 1000001; }
[data-testid="stAppHeader"] { border-bottom: 1px solid var(--fr-line); }
[data-testid="stMainBlockContainer"] { max-width: 1240px; padding-top: 1.75rem; padding-bottom: 4rem; }
[data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] li { line-height: 1.6; }
[data-testid="stMetricValue"] { font-variant-numeric: tabular-nums; font-weight: 800; letter-spacing: -0.02em; }
[data-testid="stMetricLabel"] p { color: var(--fr-muted); font-weight: 600; }

/* Smooth transitions: pages and investigation steps fade in (see page_enter); tabs do the same */
@keyframes fr-tab { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }
[data-testid="stTabPanel"] { animation: fr-tab 0.35s cubic-bezier(0.2, 0.7, 0.2, 1) both; }
[data-testid="stExpanderDetails"] { animation: fr-tab 0.25s ease-out both; }
@media (prefers-reduced-motion: reduce) {
  [data-testid="stMainBlockContainer"], [data-testid="stTabPanel"], [data-testid="stExpanderDetails"],
  .live-dot { animation: none !important; }
}

/* Page header with a case-file reference line */
.ph { margin: 0.5rem 0 1.5rem; padding-left: 1rem; border-left: 3px solid var(--fr-red); }
.ph h1 { font-size: clamp(1.8rem, 3.2vw, 2.4rem); font-weight: 800; letter-spacing: -0.03em;
  margin: 0; padding: 0; color: var(--fr-title); }
.ph p { color: var(--fr-muted); font-size: 1.05rem; margin: 0.35rem 0 0; max-width: 68ch; }
.ref { font-family: "IBM Plex Mono", ui-monospace, monospace; font-size: 0.8rem; color: var(--fr-red-text);
  letter-spacing: 0.02em; }

/* Home hero, on a faint surveillance grid */
.hero { padding: 2.4rem 0 1.6rem; position: relative; isolation: isolate; }
.hero::before { content: ""; position: absolute; inset: -1rem -2rem; z-index: -1; pointer-events: none;
  background-image: radial-gradient(var(--fr-dots) 1px, transparent 1px); background-size: 22px 22px;
  mask-image: linear-gradient(to right, black, transparent 85%); -webkit-mask-image: linear-gradient(to right, black, transparent 85%); }
.hero h1 { font-size: clamp(2.3rem, 5vw, 3.6rem); line-height: 1.02; letter-spacing: -0.035em;
  font-weight: 800; margin: 0 0 1rem; padding: 0; color: var(--fr-title); max-width: 16ch; }
.hero p { font-size: 1.15rem; color: var(--fr-body); max-width: 56ch; margin: 0; line-height: 1.55; }
.hero .tag { display: inline-flex; align-items: center; gap: 0.5rem; font-weight: 700; font-size: 0.85rem;
  color: var(--fr-red-text); background: var(--fr-red-soft); border: 1px solid var(--fr-red-edge);
  padding: 0.3rem 0.8rem; border-radius: 999px; margin-bottom: 1.1rem; }
.live-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--fr-red); animation: pulse 2s infinite; }
@keyframes pulse { 0% { box-shadow: 0 0 0 0 rgba(229,56,59,0.55); } 70% { box-shadow: 0 0 0 8px rgba(229,56,59,0); }
  100% { box-shadow: 0 0 0 0 rgba(229,56,59,0); } }

/* Chips */
.chip { display: inline-flex; align-items: center; gap: 0.35rem; padding: 0.22rem 0.7rem; border-radius: 999px;
  font-size: 0.84rem; font-weight: 700; white-space: nowrap; border: 1px solid transparent; }
.chip.clear { color: var(--fr-green-text); background: rgba(43,182,115,0.13); border-color: rgba(43,182,115,0.32); }
.chip.flag { color: var(--fr-amber-text); background: rgba(240,168,48,0.14); border-color: rgba(240,168,48,0.36); }
.chip.risk { color: var(--fr-risk-text); background: rgba(255,90,95,0.12); border-color: rgba(255,90,95,0.36); }
.chip.muted { color: var(--fr-body); background: var(--fr-raised); border-color: var(--fr-line); }
.chip.primary { color: var(--fr-red-text); background: var(--fr-red-soft); border-color: var(--fr-red-edge); }
.chips { display: flex; flex-wrap: wrap; gap: 0.45rem; margin: 0.25rem 0 0.75rem; }

/* Step tracker for the investigation */
.steps { display: grid; grid-template-columns: repeat(6, 1fr); gap: 0.4rem; margin: 0.25rem 0 0.5rem; }
.step { height: 5px; border-radius: 999px; background: var(--fr-line); transition: background-color 0.4s ease; }
.step.done { background: #2BB673; }
.step.now { background: var(--fr-red); }

/* Small labelled numbers inside panels */
.kv { display: grid; grid-template-columns: auto 1fr; gap: 0.35rem 1rem; font-size: 0.95rem; }
.kv span:nth-child(odd) { color: var(--fr-muted); }
.kv span:nth-child(even) { font-weight: 600; }

/* Contribution bars on the verdict */
.bar { margin: 0.55rem 0; }
.bar .top { display: flex; justify-content: space-between; font-size: 0.92rem; font-weight: 600; }
.bar .top span:last-child { font-variant-numeric: tabular-nums; color: var(--fr-muted); }
.bar .track { height: 8px; background: var(--fr-raised); border-radius: 999px; margin-top: 0.3rem; overflow: hidden; }
.bar .fill { height: 100%; border-radius: 999px; animation: fr-grow 0.7s cubic-bezier(0.2, 0.7, 0.2, 1) both;
  transform-origin: left; }
@keyframes fr-grow { from { transform: scaleX(0); } to { transform: scaleX(1); } }
@media (prefers-reduced-motion: reduce) { .bar .fill { animation: none; } }

.verdicts { display: flex; flex-wrap: wrap; align-items: center; gap: 0.6rem; margin: 0.4rem 0 1rem; }
.verdict-note { color: var(--fr-muted); font-size: 0.92rem; }
.report-head { display: flex; flex-wrap: wrap; align-items: baseline; gap: 0.75rem; margin-top: 1.5rem; }
.report-head h3 { margin: 0; padding: 0; font-weight: 800; }
.report-head .quarter { color: var(--fr-muted); font-weight: 600; }
blockquote.guidance { border-left: 3px solid var(--fr-red); margin: 1rem 0 1.25rem; padding: 0.4rem 0 0.4rem 1rem; max-width: 72ch; }
.news-meta { color: var(--fr-muted); font-size: 0.82rem; }
.fineprint { font-size: 0.78rem; color: var(--fr-muted); line-height: 1.45; }
.empty { color: var(--fr-muted); border: 1.5px dashed var(--fr-line); border-radius: 0.6rem; padding: 1.1rem 1.25rem; }
mark.hit { background: var(--fr-red-soft); color: var(--fr-red-text); box-shadow: inset 0 -1.5px 0 var(--fr-red-edge);
  padding: 0 0.15rem; border-radius: 3px; }
</style>
"""


def page_enter(name: str) -> None:
    """Fade the page in whenever `name` changes (a new page or a new step).

    A CSS animation restarts when its name changes, so each page gets its own keyframes name.
    Reruns on the same page keep the same name, so they don't flicker.
    """
    import re

    key = re.sub(r"[^a-z0-9]+", "-", str(name).lower()).strip("-")[:40] or "page"
    st.markdown(
        f"<style>@keyframes fr-enter-{key} {{ from {{ opacity: 0; transform: translateY(10px); }} "
        f"to {{ opacity: 1; transform: none; }} }}"
        f'[data-testid="stMainBlockContainer"] {{ animation: fr-enter-{key} 0.45s cubic-bezier(0.2, 0.7, 0.2, 1) both; }}'
        "</style>",
        unsafe_allow_html=True,
    )


def inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def chip(text: str, kind: str = "muted") -> str:
    return f'<span class="chip {kind}">{html.escape(text)}</span>'


def page_header(title: str, subtitle: str, ref: str | None = None) -> None:
    ref_html = f'<span class="ref">{html.escape(ref)}</span>' if ref else ""
    st.markdown(f'<div class="ph">{ref_html}<h1>{html.escape(title)}</h1><p>{html.escape(subtitle)}</p></div>',
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
        number=dict(suffix="%", font=dict(size=44)),
        gauge=dict(
            axis=dict(range=[0, 100], tickvals=[0, 35, 60, 100], tickfont=dict(size=11, color=COLORS["muted"])),
            bar=dict(color=color, thickness=0.32),
            bgcolor=COLORS["track"], borderwidth=0,
            steps=[dict(range=[0, 35], color="rgba(43,182,115,0.12)"), dict(range=[35, 60], color="rgba(240,168,48,0.12)"),
                   dict(range=[60, 100], color="rgba(255,90,95,0.14)")],
        ),
    ))
    fig.update_layout(height=height, margin=dict(l=20, r=20, t=10, b=0), paper_bgcolor="rgba(0,0,0,0)")
    return fig


def style_fig(fig, height: int = 380):
    """House style for Plotly charts."""
    fig.update_layout(
        height=height, margin=dict(l=8, r=8, t=30, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        hovermode="x unified",
        legend=dict(orientation="h", y=1.08, x=0, title=None),
        xaxis=dict(showgrid=False, linecolor=COLORS["line"]),
        yaxis=dict(gridcolor=COLORS["grid"], zeroline=False),
    )
    return fig
