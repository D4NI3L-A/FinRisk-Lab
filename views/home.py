"""Home: search a company, glance at the market, jump into a module."""
from __future__ import annotations

import streamlit as st

import ui
from core import market


def _pick_ticker() -> None:
    """Runs before the page redraws: remember the pick, clear the pill, then go to the case."""
    pick = st.session_state.get("home_pick")
    if pick:
        st.session_state["case_ticker"] = pick
        st.session_state["go_case"] = True
    st.session_state["home_pick"] = None


left, right = st.columns([7, 5], gap="large", vertical_alignment="center")
with left:
    st.markdown(
        '<section class="hero"><span class="tag"><span class="live-dot"></span>Market and financial-crime risk, in one place</span>'
        "<h1>Investigate any company in minutes.</h1>"
        "<p>Search a ticker to get its market risk, what the news is saying, any adverse media and a "
        "transparent red-flag score, all combined into one case you can export.</p></section>",
        unsafe_allow_html=True,
    )
with right:
    with st.container(border=True):
        st.markdown("**Start an investigation**")
        with st.form("start_case", border=False):
            ticker = st.text_input("Ticker", placeholder="e.g. JPM, HSBC, AAPL", label_visibility="collapsed")
            start = st.form_submit_button("Investigate", type="primary", icon=":material/search:", width="stretch")
        st.caption("or pick one")
        st.pills("Popular", market.SUGGESTED, label_visibility="collapsed", key="home_pick",
                 on_change=_pick_ticker)
        if start and (ticker or "").strip():
            st.session_state["case_ticker"] = ticker.strip().upper()
            st.session_state["go_case"] = True
        if st.session_state.pop("go_case", False):
            st.switch_page("views/investigate.py")

# ── Live market strip ─────────────────────────────────────────────────────
st.markdown("#### Markets today")
strip = list(market.MARKET_STRIP)
prices, is_demo = ui.prices(tuple(strip), "3mo")
cols = st.columns(len(strip))
for col, t in zip(cols, strip):
    s = prices[t].dropna()
    m = market.price_metrics(s)
    col.metric(market.MARKET_STRIP[t], f"{m['last']:,.2f}", ui.pct(m["day"]), border=True,
               chart_data=s.tail(40).round(2).tolist(), chart_type="area",
               help=f"{t} · last close and change on the day. Sparkline: last 40 trading days.")
ui.demo_notice(is_demo, "prices")

# ── Modules ───────────────────────────────────────────────────────────────
st.markdown("#### What you can do")
modules = [
    ("views/investigate.py", ":material/travel_explore:", "Investigate a company",
     "A guided case in five steps: profile, market risk, news sentiment, adverse media and red flags, "
     "ending in one risk score and a report."),
    ("views/markets.py", ":material/monitoring:", "Watch the market",
     "Compare tickers on one chart, check volatility and drawdowns, and read the latest headlines."),
    ("views/network.py", ":material/hub:", "Map a network",
     "See who connects to whom. Brokers and risky counterparties stand out, and you can trace the path "
     "between any two entities."),
    ("views/news.py", ":material/newspaper:", "Look up live news",
     "Search today's news on any company or person, with an adverse-media mode that adds "
     "financial-crime keywords."),
    ("views/toolkit.py", ":material/auto_awesome:", "Use the AI toolkit",
     "Classify headlines, summarise an earnings call, screen news for financial crime, or score red flags."),
    ("views/about.py", ":material/info:", "Read how it works",
     "How the case score is built, what comes next, and how the app covers the course lab."),
]
for row in (modules[:3], modules[3:]):
    for col, (page, icon, title, text) in zip(st.columns(3, gap="medium"), row):
        with col.container(border=True, height="stretch"):
            st.markdown(f"##### {title}")
            st.write(text)
            st.page_link(page, label=f"Open {title.split()[0].lower()}", icon=icon)
