"""News lookup: live headlines for any company or person, with an adverse-media search mode."""
from __future__ import annotations

import html

import pandas as pd
import streamlit as st

import ui
from core import news
from theme import chip, page_header


@st.cache_data(ttl=600, show_spinner=False)
def lookup(term: str, adverse: bool, window: str | None):
    return news.search(term, adverse, window)


page_header("News lookup", "Search live news on any company, person or topic. Switch on adverse-media "
                           "mode to add the financial-crime keywords an analyst would use.")

with st.container(border=True):
    with st.form("news_form", border=False):
        a, b = st.columns([5, 1], vertical_alignment="bottom")
        term = a.text_input("Search", key="news_term", placeholder="e.g. Clearbrook Bank, Pemex, a director's name",
                            label_visibility="collapsed")
        b.form_submit_button("Search", type="primary", icon=":material/search:", width="stretch")
    c1, c2, c3 = st.columns([2, 2, 3], vertical_alignment="center")
    adverse = c1.toggle("Adverse-media mode", key="news_adverse",
                        help="Adds: " + ", ".join(news.ADVERSE_TERMS[:9]))
    window_label = c2.selectbox("Published", list(news.WINDOWS), index=3, key="news_window",
                                label_visibility="collapsed")
    if term.strip():
        c3.caption(f"Query sent: `{news.build_query(term, adverse, news.WINDOWS[window_label])}`")

if not term.strip():
    st.markdown('<p class="empty">Type a name above and press Search. Tip: put a person\'s full name, and '
                "switch on adverse-media mode for a negative-news check.</p>", unsafe_allow_html=True)
    st.stop()

with st.spinner("Searching live news..."):
    items, is_demo = lookup(term.strip(), adverse, news.WINDOWS[window_label])
ui.demo_notice(is_demo, "news")

if not items:
    st.markdown('<p class="empty">No articles found. Try a shorter name, a wider date range, or switch '
                "adverse-media mode off.</p>", unsafe_allow_html=True)
    st.stop()

hits = [news.keyword_hits(i["title"]) for i in items]
with_hits = sum(1 for h in hits if h)
sources = len({i["publisher"] for i in items if i["publisher"]})
m1, m2, m3, m4 = st.columns([1, 1, 1, 1.4], vertical_alignment="bottom")
m1.metric("Articles", len(items), border=True)
m2.metric("Sources", sources, border=True)
m3.metric("Risk keywords", f"{with_hits / len(items):.0%}", border=True,
          help="Share of headlines that contain a financial-crime keyword. Keywords are highlighted in red.")
screen = m4.button("Screen these headlines with AI", icon=":material/policy:", width="stretch",
                   help="Sends all headlines in one call to the model in the sidebar and flags financial-crime risk.")

key = f"res_news_{term.strip().lower()}_{adverse}_{window_label}"
if screen:
    provider, model, temp = ui.settings()
    out = ui.run_llm(ui.media, tuple(i["title"] for i in items), provider, model, temp)
    if out:
        st.session_state[key] = {"rows": out[0], "secs": out[1], "provider": provider, "model": model, "temp": temp}
res = st.session_state.get(key)
if res:
    flagged = sum(r["flag"] for r in res["rows"])
    st.markdown(f'<div class="chips">{chip(f"AI flagged {flagged} of {len(res["rows"])}", "risk" if flagged else "clear")}</div>',
                unsafe_allow_html=True)
    ui.run_caption(res)

order = st.segmented_control("Sort", ["Newest", "Risk keywords first"], default="Newest", key="news_sort") or "Newest"
idx = list(range(len(items)))
if order == "Risk keywords first":
    idx.sort(key=lambda i: -len(hits[i]))
else:
    idx.sort(key=lambda i: items[i]["published"] or "", reverse=True)

for i in idx:
    item = items[i]
    row = res["rows"][i] if res and i < len(res["rows"]) else None
    with st.container(border=True):
        x, y = st.columns([6, 1], vertical_alignment="center")
        tag = ""
        if row:
            tag = (chip(f"{row['category'].replace('_', ' ')} · {row['confidence']}", "risk") if row["flag"]
                   else chip("Clear", "clear")) + " "
        x.markdown(f"{tag}**{news.highlight(item['title'])}**", unsafe_allow_html=True)
        when = pd.to_datetime(item["published"]).strftime("%d %b %Y") if item.get("published") else ""
        meta = " · ".join(v for v in [item.get("publisher"), when] if v)
        x.markdown(f'<span class="news-meta">{html.escape(meta)}</span>', unsafe_allow_html=True)
        if row and row["flag"] and row.get("reasoning"):
            x.caption(row["reasoning"])
        if item.get("link"):
            y.link_button("Read", item["link"], icon=":material/open_in_new:", width="stretch")

st.caption("Headlines come from Google News. A keyword match or an AI flag is a lead to check, not a finding.")
