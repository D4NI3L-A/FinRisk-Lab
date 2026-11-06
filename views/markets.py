"""Markets: compare tickers, check risk, read and score the news."""
from __future__ import annotations

import html

import pandas as pd
import plotly.express as px
import streamlit as st

import ui
from core import market
from theme import COLORS, chip, page_header, style_fig

BENCH = "^GSPC"
page_header("Markets", "Compare companies on one chart, check how risky each one has been, "
                       "and see what the news is saying.")

c1, c2, c3 = st.columns([6, 3, 3], vertical_alignment="bottom")
watch = c1.multiselect("Watchlist", market.SUGGESTED + ["^GSPC", "^STOXX50E"],
                       default=["JPM", "HSBC", "BAC", "AAPL"], accept_new_options=True, max_selections=8,
                       placeholder="Type any Yahoo Finance ticker and press Enter",
                       help="Add any ticker Yahoo Finance knows, e.g. BARC.L for Barclays or AIBG.L for AIB.")
period_label = c2.segmented_control("Period", list(market.PERIODS), default="1Y", key="mk_period") or "1Y"
view = c3.segmented_control("Show", ["Return %", "Price"], default="Return %", key="mk_view") or "Return %"

watch = [t.strip().upper() for t in watch if t.strip()]
if not watch:
    st.markdown('<p class="empty">Add at least one ticker to the watchlist to see charts.</p>',
                unsafe_allow_html=True)
    st.stop()

tickers = tuple(dict.fromkeys(watch + [BENCH]))
with st.spinner("Loading prices..."):
    prices, is_demo = ui.prices(tickers, market.PERIODS[period_label])
ui.demo_notice(is_demo, "prices")

# ── Chart ─────────────────────────────────────────────────────────────────
shown = prices[watch].dropna(how="all")
data = (shown / shown.bfill().iloc[0] - 1) if view == "Return %" else shown
long = data.reset_index(names="Date").melt("Date", var_name="Ticker", value_name="Value").dropna()
fig = px.line(long, x="Date", y="Value", color="Ticker",
              color_discrete_sequence=["#2A5BD7", "#0F9D6B", "#D98E04", "#E04848", "#7C8AA5", "#8B5CF6",
                                       "#0EA5E9", "#B45309"])
fig.update_traces(line=dict(width=2.2), hovertemplate="%{y:+.1%}" if view == "Return %" else "%{y:,.2f}")
if view == "Return %":
    fig.update_yaxes(tickformat="+.0%")
    fig.add_hline(y=0, line_color=COLORS["line"], line_width=1)
fig.update_xaxes(title=None, rangeslider=dict(visible=False))
fig.update_yaxes(title=None)
st.plotly_chart(style_fig(fig, 420), config={"displaylogo": False}, key="mk_chart")

# ── Risk table ────────────────────────────────────────────────────────────
rows = []
for t in watch:
    m = market.price_metrics(prices[t], prices[BENCH] if t != BENCH else None)
    rows.append({"Ticker": t, "Trend": prices[t].dropna().tail(60).round(2).tolist(), "Last": m["last"],
                 "Day": m["day"], "Period": m["period"], "Volatility": m["vol"], "Max drawdown": m["max_dd"],
                 "Beta": m["beta"]})
table = pd.DataFrame(rows)
st.markdown("#### Risk at a glance")
st.dataframe(
    table, hide_index=True, width="stretch",
    column_config={
        "Trend": st.column_config.LineChartColumn("Last 60 days", width="medium"),
        "Last": st.column_config.NumberColumn(format="%.2f"),
        "Day": st.column_config.NumberColumn("1 day", format="percent"),
        "Period": st.column_config.NumberColumn(f"{period_label} return", format="percent"),
        "Volatility": st.column_config.ProgressColumn("Volatility (annual)", format="percent",
                                                       min_value=0, max_value=0.8,
                                                       help="Annualised standard deviation of daily returns."),
        "Max drawdown": st.column_config.NumberColumn(format="percent",
                                                      help="Largest fall from a previous peak in this period."),
        "Beta": st.column_config.NumberColumn(format="%.2f", help="Sensitivity to the S&P 500."),
    },
)

if len(watch) > 1:
    with st.expander("How closely do they move together?", icon=":material/grid_on:"):
        corr = prices[watch].pct_change().corr()
        heat = px.imshow(corr, text_auto=".2f", zmin=-1, zmax=1, aspect="auto",
                         color_continuous_scale=[[0, "#E04848"], [0.5, "#F3F6FB"], [1, "#2A5BD7"]])
        heat.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0), coloraxis_showscale=False)
        st.plotly_chart(heat, config={"displayModeBar": False}, key="mk_corr")
        st.caption("Correlation of daily returns. Close to 1 means they rise and fall together, "
                   "so holding both diversifies less.")

# ── News ──────────────────────────────────────────────────────────────────
st.markdown("#### Latest news")
n1, n2 = st.columns([3, 2], vertical_alignment="bottom")
news_ticker = n1.selectbox("Company", watch, key="mk_news_t")
analyse = n2.button("Score sentiment with AI", icon=":material/auto_awesome:", width="stretch",
                    help="Sends these headlines in one call to the model chosen in the sidebar.")
items, news_demo = ui.news(news_ticker)
ui.demo_notice(news_demo, "news")

state_key = f"res_mknews_{news_ticker}"
if analyse:
    provider, model, temp = ui.settings()
    titles = tuple(i["title"] for i in items)
    out = ui.run_llm(ui.headlines, titles, tuple([news_ticker] * len(titles)), provider, model, temp, False)
    if out:
        st.session_state[state_key] = {"labels": [r["sentiment"] for r in out[0]], "secs": out[1],
                                       "provider": provider, "model": model, "temp": temp}

res = st.session_state.get(state_key)
if res:
    labels = res["labels"]
    known = [lab for lab in labels if lab != "Unclassified"] or ["Neutral"]
    shares = {k: known.count(k) / len(known) for k in ("Positive", "Neutral", "Negative")}
    s1, s2, s3 = st.columns(3)
    s1.metric("Positive", ui.pct(shares["Positive"], signed=False, digits=0), border=True)
    s2.metric("Neutral", ui.pct(shares["Neutral"], signed=False, digits=0), border=True)
    s3.metric("Negative", ui.pct(shares["Negative"], signed=False, digits=0), border=True)
    ui.run_caption(res)
else:
    labels = [None] * len(items)

kinds = {"Positive": "clear", "Negative": "risk", "Neutral": "muted", "Mixed": "flag"}
for item, label in zip(items, labels):
    with st.container(border=True):
        a, b = st.columns([5, 1], vertical_alignment="center")
        badge = chip(label, kinds.get(label, "muted")) + " " if label else ""
        a.markdown(f"{badge}**{html.escape(item['title'])}**", unsafe_allow_html=True)
        meta = " · ".join(x for x in [item.get("publisher"), (item.get("published") or "")[:10]] if x)
        a.markdown(f'<span class="news-meta">{html.escape(meta)}</span>', unsafe_allow_html=True)
        if item.get("link"):
            b.link_button("Read", item["link"], icon=":material/open_in_new:", width="stretch")
