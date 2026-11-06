"""Investigate: a guided five-step case on one company, ending in a scored verdict and a report."""
from __future__ import annotations

import html
import json

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import ui
from core import market, report, scoring
from risk import MAX_SCORE, RED_FLAGS, score_flags
from theme import (BAND_COLORS, BAND_KIND, COLORS, SENTIMENT_COLORS, chip, contribution_bar, gauge, page_header,
                   page_enter, steps_bar, style_fig)

STEPS = ["Profile", "Market risk", "News sentiment", "Adverse media", "Red flags", "Verdict"]
SCORED = {1: "market", 2: "news", 3: "media", 4: "flags"}
CONFIG = {"displayModeBar": False}


# ── Case state ────────────────────────────────────────────────────────────
def new_case(ticker: str) -> dict:
    return {"ticker": ticker, "visited": set(), "scores": {}, "profile": {}, "links": {}}


def open_case() -> None:
    t = (st.session_state.get("case_input") or "").strip().upper()
    if t:
        st.session_state["case_ticker"] = t
        st.session_state["case_step"] = STEPS[0]


def go_to(i: int) -> None:
    st.session_state["case_step"] = STEPS[i]


ticker = st.session_state.get("case_ticker")
case = st.session_state.get("case")
if ticker and (case is None or case["ticker"] != ticker):
    case = st.session_state["case"] = new_case(ticker)
    st.session_state["case_step"] = STEPS[0]
    st.session_state["case_input"] = ticker

# ── Header: choose a company ──────────────────────────────────────────────
page_header("Investigate", "Work through one company step by step. Each step adds evidence to the "
                           "risk score, and every source is one click away.",
            ref=f"Case file FR-{pd.Timestamp.today():%Y}-{ticker}" if ticker else "New case")
with st.container(border=True):
    c1, c2, c3 = st.columns([3, 1.2, 4], vertical_alignment="bottom")
    st.session_state.setdefault("case_input", ticker or "")
    c1.text_input("Company ticker", key="case_input", placeholder="e.g. JPM", on_change=open_case)
    c2.button("Open case", type="primary", on_click=open_case, icon=":material/folder_open:", width="stretch")
    c3.pills("Suggestions", market.SUGGESTED, key="case_pick", label_visibility="collapsed",
             on_change=lambda: (st.session_state.update(case_input=st.session_state["case_pick"] or ""),
                                open_case(), st.session_state.update(case_pick=None)))

if case is None:
    st.markdown('<p class="empty">Enter a ticker above, or pick one of the suggestions, to open a case.</p>',
                unsafe_allow_html=True)
    st.stop()

# Load the profile once per case
if not case["profile"]:
    with st.spinner(f"Loading {ticker}..."):
        case["profile"] = ui.profile(ticker)
        case["links"] = market.research_links(ticker, case["profile"].get("name"))
prof = case["profile"]

# Which step is open (set by the step selector, the Back/Next buttons, or a new case)
step = STEPS.index(st.session_state.get("case_step") or STEPS[0])
if step in (0, 1):
    case["visited"].add(step)  # data-only steps count as done once viewed
if step == 1 or "market" not in case["scores"]:
    _px, _ = ui.prices((ticker, "^GSPC"), "1y")
    case["market_metrics"] = market.price_metrics(_px[ticker], _px["^GSPC"])
    if 1 in case["visited"]:
        m_ = case["market_metrics"]
        case["scores"]["market"] = scoring.market_score(m_["vol"], m_["max_dd"])

result = scoring.composite({k: case["scores"].get(k) for k in scoring.WEIGHTS})
done_steps = case["visited"] | ({5} if result["score"] is not None else set())
progress = len(case["visited"] & {0, 1, 2, 3, 4}) / 5

# ── Case summary bar ──────────────────────────────────────────────────────
h1, h2, h3, h4 = st.columns([4, 2, 2, 2], vertical_alignment="center")
with h1:
    st.markdown(f"### {html.escape(prof.get('name') or ticker)}")
    tags = [chip(ticker, "primary")] + [chip(x, "muted") for x in (prof.get("sector"), prof.get("country")) if x]
    st.markdown(f'<div class="chips">{"".join(tags)}</div>', unsafe_allow_html=True)
h2.metric("Case complete", f"{progress:.0%}", border=True, help="Share of the five investigation steps you have done.")
h3.metric("Risk score", "n/a" if result["score"] is None else f"{result['score']:.0f}%", border=True,
          help="Weighted from the steps completed so far. 0% is no concern, 100% is maximum concern.")
h4.metric("Risk band", result["band"], border=True)

steps_bar(len(STEPS), done_steps, step)
page_enter(f"investigate {step}")  # each step fades in
st.segmented_control(
    "Step", STEPS, key="case_step", label_visibility="collapsed", width="stretch",
    format_func=lambda s: ("✓ " if STEPS.index(s) in done_steps else f"{STEPS.index(s) + 1}. ") + s,
)


def nav_buttons(i: int) -> None:
    a, _, b = st.columns([1, 3, 1])
    if i > 0:
        a.button(f"Back: {STEPS[i - 1]}", on_click=go_to, args=(i - 1,), icon=":material/arrow_back:",
                 width="stretch", key=f"back_{i}")
    if i < len(STEPS) - 1:
        b.button(f"Next: {STEPS[i + 1]}", on_click=go_to, args=(i + 1,), type="primary",
                 icon=":material/arrow_forward:", icon_position="right", width="stretch", key=f"next_{i}")


def link_row(links: dict[str, str]) -> None:
    with st.container(horizontal=True, gap="small"):
        for label, url in links.items():
            st.link_button(label, url, icon=":material/open_in_new:")


provider, model, temp = ui.settings()

# ── Step 1: Profile ───────────────────────────────────────────────────────
if step == 0:
    left, right = st.columns([3, 2], gap="large")
    with left, st.container(border=True):
        st.markdown("##### About the company")
        st.write(prof.get("summary") or "No description available. Use the links below to research it.")
    with right, st.container(border=True):
        st.markdown("##### Key facts")
        facts = {
            "Industry": prof.get("industry") or "n/a",
            "Country": prof.get("country") or "n/a",
            "Market cap": market.human_money(prof.get("market_cap")),
            "Employees": f"{prof['employees']:,}" if prof.get("employees") else "n/a",
        }
        st.markdown('<div class="kv">' + "".join(f"<span>{k}</span><span>{html.escape(str(v))}</span>"
                                                 for k, v in facts.items()) + "</div>", unsafe_allow_html=True)
        if prof.get("website"):
            st.link_button("Company website", prof["website"], icon=":material/language:", width="stretch")
    if prof.get("demo"):
        st.caption(":material/info: Live profile unavailable. Check the ticker, or research with the links below.")
    st.markdown("##### Research sources")
    link_row(case["links"])
    nav_buttons(0)

# ── Step 2: Market risk ───────────────────────────────────────────────────
elif step == 1:
    px_df, is_demo = ui.prices((ticker, "^GSPC"), "1y")
    m = case["market_metrics"]
    k = st.columns(5)
    k[0].metric("1-year return", ui.pct(m["period"]), border=True)
    k[1].metric("Volatility", ui.pct(m["vol"], signed=False), border=True, help="Annualised.")
    k[2].metric("Max drawdown", ui.pct(m["max_dd"]), border=True, help="Largest fall from a peak.")
    k[3].metric("Beta vs S&P 500", "n/a" if m["beta"] is None else f"{m['beta']:.2f}", border=True)
    k[4].metric("Market risk score", f"{case['scores']['market']:.0f}%", border=True,
                help="60% from volatility (60%+ a year is the maximum) and 40% from drawdown (50%+ is the maximum).")
    norm = px_df / px_df.bfill().iloc[0] - 1
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=norm.index, y=norm["^GSPC"], name="S&P 500",
                             line=dict(color="#6B7891", width=1.6, dash="dot"), hovertemplate="%{y:+.1%}"))
    fig.add_trace(go.Scatter(x=norm.index, y=norm[ticker], name=ticker, fill="tozeroy",
                             line=dict(color=COLORS["info"], width=2.4), fillcolor="rgba(91,141,239,0.10)",
                             hovertemplate="%{y:+.1%}"))
    fig.update_yaxes(tickformat="+.0%")
    st.plotly_chart(style_fig(fig, 380), config=CONFIG, key="inv_px")
    ui.demo_notice(is_demo, "prices")
    nav_buttons(1)

# ── Step 3: News sentiment ────────────────────────────────────────────────
elif step == 2:
    items, news_demo = ui.news(ticker)
    ui.demo_notice(news_demo, "news")
    a, b = st.columns([3, 1], vertical_alignment="center")
    a.write(f"{len(items)} recent headlines. The model labels each one from a shareholder's point of view.")
    if b.button("Score sentiment", type="primary", icon=":material/auto_awesome:", width="stretch"):
        titles = tuple(i["title"] for i in items)
        out = ui.run_llm(ui.headlines, titles, tuple([ticker] * len(titles)), provider, model, temp, True)
        if out:
            case["news_rows"] = out[0]
            case["scores"]["news"] = scoring.news_score([r["sentiment"] for r in out[0]])
            case["visited"].add(2)
            st.rerun()  # refresh the score and progress at the top
    rows = case.get("news_rows")
    if rows:
        ui.demo_ai_note(provider)
        labels = [r["sentiment"] for r in rows]
        counts = pd.Series(labels).value_counts()
        d1, d2 = st.columns([2, 3], gap="large")
        with d1:
            donut = go.Figure(go.Pie(labels=counts.index, values=counts.values, hole=0.62, sort=False,
                                     marker=dict(colors=[SENTIMENT_COLORS.get(x, "#8A97AD") for x in counts.index]),
                                     textinfo="percent", hovertemplate="%{label}: %{value}<extra></extra>"))
            donut.update_layout(height=260, margin=dict(l=0, r=0, t=0, b=0), showlegend=True,
                                legend=dict(orientation="h", y=-0.05), paper_bgcolor="rgba(0,0,0,0)",
                                annotations=[dict(text=f"<b>{case['scores']['news']:.0f}%</b><br>negative",
                                                  showarrow=False, font=dict(size=15))])
            st.plotly_chart(donut, config=CONFIG, key="inv_donut")
        with d2:
            st.metric("News sentiment score", f"{case['scores']['news']:.0f}%", border=True,
                      help="Share of headlines that are negative (Mixed counts half).")
            st.caption("Negative news alone isn't a red flag, but a run of it often comes before trouble.")
    kinds = {"Positive": "clear", "Negative": "risk", "Neutral": "muted", "Mixed": "flag"}
    for i, item in enumerate(items):
        label = rows[i]["sentiment"] if rows and i < len(rows) else None
        with st.container(border=True):
            x, y = st.columns([6, 1], vertical_alignment="center")
            badge = chip(label, kinds.get(label, "muted")) + " " if label else ""
            x.markdown(f"{badge}{html.escape(item['title'])}", unsafe_allow_html=True)
            if item.get("link"):
                y.link_button("Source", item["link"], icon=":material/open_in_new:", width="stretch")
    nav_buttons(2)

# ── Step 4: Adverse media ─────────────────────────────────────────────────
elif step == 3:
    items, news_demo = ui.news(ticker)
    st.write("Screens the same headlines, plus anything you paste below, for signs of fraud, corruption, "
             "sanctions or money laundering.")
    extra = st.text_area("Extra snippets (optional, one per line)", height=90, key=f"extra_{ticker}",
                         placeholder="Paste news or search results about the company or its owners")
    snippets = [i["title"] for i in items] + [ln.strip() for ln in extra.splitlines() if ln.strip()]
    links = [i.get("link") for i in items] + [None] * (len(snippets) - len(items))
    a, b = st.columns([3, 1], vertical_alignment="center")
    a.caption(f"{len(snippets)} snippets ready to screen.")
    if b.button("Screen for financial crime", type="primary", icon=":material/policy:", width="stretch"):
        out = ui.run_llm(ui.media, tuple(snippets), provider, model, temp)
        if out:
            case["media_rows"] = [dict(r, link=lk) for r, lk in zip(out[0], links)]
            case["scores"]["media"] = scoring.media_score(out[0])
            case["visited"].add(3)
            st.rerun()  # refresh the score and progress at the top
    rows = case.get("media_rows")
    if rows:
        ui.demo_ai_note(provider)
        flagged = [r for r in rows if r["flag"]]
        m1, m2, m3 = st.columns(3)
        m1.metric("Screened", len(rows), border=True)
        m2.metric("Flagged", f"{len(flagged)} ({len(flagged) / len(rows):.0%})", border=True)
        m3.metric("Adverse-media score", f"{case['scores']['media']:.0f}%", border=True,
                  help="Confidence-weighted share of flagged snippets, scaled so a few confident flags count.")
        for r in sorted(rows, key=lambda r: not r["flag"]):
            with st.container(border=True):
                x, y = st.columns([6, 1], vertical_alignment="center")
                tag = chip(f"{r['category'].replace('_', ' ')} · {r['confidence']}", "risk") if r["flag"] else chip("Clear", "clear")
                x.markdown(f"{tag} {html.escape(r['snippet'])}", unsafe_allow_html=True)
                if r["flag"] and r.get("reasoning"):
                    x.caption(r["reasoning"])
                if r.get("link"):
                    y.link_button("Source", r["link"], icon=":material/open_in_new:", width="stretch")
    st.markdown("##### Check official lists")
    link_row({k: v for k, v in case["links"].items() if k in ("OpenSanctions", "OFAC sanctions search", "News search")})
    nav_buttons(3)

# ── Step 5: Red flags ─────────────────────────────────────────────────────
elif step == 4:
    st.write("Select every risk factor your research supports. The score updates as you click.")
    selected = st.pills("Red flags", list(RED_FLAGS), selection_mode="multi", key=f"flags_{ticker}",
                        default=case.get("flags") or [], label_visibility="collapsed")
    rule = score_flags(selected)
    flag_pct = scoring.flags_score(rule["score"], MAX_SCORE)
    g1, g2 = st.columns([2, 3], gap="large")
    with g1:
        st.plotly_chart(gauge(flag_pct, rule["band"], 220), config=CONFIG, key="inv_flags_gauge")
        st.markdown(f'<div class="chips">{chip(f"{rule["score"]} of {MAX_SCORE} points", "muted")}'
                    f'{chip("Rule band: " + rule["band"], BAND_KIND.get(rule["band"], "muted"))}</div>',
                    unsafe_allow_html=True)
    with g2:
        for f in RED_FLAGS:
            on = f in selected
            st.markdown(contribution_bar(f, RED_FLAGS[f] if on else 0, 3, COLORS["risk"] if on else COLORS["line"],
                                         f"+{RED_FLAGS[f]}" if on else f"{RED_FLAGS[f]} pts"),
                        unsafe_allow_html=True)
    context = st.text_area("Context for the AI narrative (optional)", key=f"ctx_{ticker}", height=80,
                           placeholder="e.g. Ownership runs through two holding companies in a secrecy jurisdiction")
    b1, b2 = st.columns(2)
    if b1.button("Confirm red flags", type="primary", icon=":material/check:", width="stretch"):
        case["flags"], case["scores"]["flags"] = list(selected), flag_pct
        case["visited"].add(4)
        st.rerun()
    if b2.button("Write AI narrative", icon=":material/auto_awesome:", width="stretch"):
        out = ui.run_llm(ui.flags, tuple(selected), context, json.dumps(rule), provider, model, temp)
        if out:
            case["narrative"] = out[0].get("narrative", "")
            case["narrative_rating"] = out[0].get("risk_rating")
    if case.get("narrative"):
        with st.container(border=True):
            st.markdown(f"**AI rating: {case.get('narrative_rating')}** · rule band: {rule['band']}")
            st.write(case["narrative"])
            ui.demo_ai_note(provider)
    nav_buttons(4)

# ── Step 6: Verdict ───────────────────────────────────────────────────────
else:
    v1, v2 = st.columns([2, 3], gap="large")
    with v1, st.container(border=True):
        st.plotly_chart(gauge(result["score"], result["band"], 250), config=CONFIG, key="inv_verdict_gauge")
        st.markdown(f'<div class="chips" style="justify-content:center">'
                    f'{chip(result["band"] + " risk", BAND_KIND.get(result["band"], "muted"))}'
                    f'{chip(f"{result["completeness"]:.0%} of evidence", "muted")}</div>', unsafe_allow_html=True)
    with v2:
        st.markdown("##### What drives the score")
        for k, label in scoring.LABELS.items():
            sub = case["scores"].get(k)
            if sub is None:
                st.markdown(contribution_bar(label, 0, 100, COLORS["line"], "not done"), unsafe_allow_html=True)
            else:
                color = BAND_COLORS[scoring.band(sub)]
                st.markdown(contribution_bar(label, sub, 100, color,
                                             f"{sub:.0f}% · adds {result['contributions'][k]:.1f} pts"),
                            unsafe_allow_html=True)
        st.markdown("##### Recommended action")
        st.info(report.ACTIONS[result["band"]], icon=":material/gavel:")
        missing = [STEPS[i] for i, k in SCORED.items() if case["scores"].get(k) is None]
        if missing:
            st.caption("Not done yet: " + ", ".join(missing) + ". Finish them for a fuller score.")
            with st.container(horizontal=True, gap="small"):
                for i, k in SCORED.items():
                    if case["scores"].get(k) is None:
                        st.button(f"Go to {STEPS[i]}", on_click=go_to, args=(i,), key=f"goto_{i}",
                                  icon=":material/arrow_forward:")
    md = report.build_markdown(case, result)
    d1, d2, d3 = st.columns(3)
    d1.download_button("Download report", md, f"case_{ticker}.md", "text/markdown", type="primary",
                       icon=":material/download:", width="stretch")
    export = {k: v for k, v in case.items() if k != "visited"} | {"result": result}
    d2.download_button("Download data (JSON)", json.dumps(export, indent=2, default=str), f"case_{ticker}.json",
                       "application/json", icon=":material/data_object:", width="stretch")
    d3.page_link("views/network.py", label="Map counterparties in Network", icon=":material/hub:")
    with st.expander("Preview the report", icon=":material/description:"):
        st.markdown(md)
    nav_buttons(5)
