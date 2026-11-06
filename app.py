"""FinRisk Lab: entry point. Sets up the page, the model settings and the navigation.

Run with:  streamlit run app.py
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

import llm  # noqa: E402  (after load_dotenv so model overrides in .env are picked up)
from theme import inject_css, page_enter  # noqa: E402

ASSETS = Path(__file__).parent / "assets"
st.set_page_config(page_title="FinRisk Lab", page_icon=str(ASSETS / "icon.png"), layout="wide",
                   initial_sidebar_state="collapsed")
st.logo(str(ASSETS / "logo.svg"), icon_image=str(ASSETS / "icon.svg"), size="large")
inject_css()

LABEL = llm.PROVIDER_LABELS
keys = llm.key_status()

# ── Sidebar: AI model settings (lab Sections 1, 7 and 8) ─────────────────
with st.sidebar:
    st.markdown("### AI settings")
    st.caption("Used by every AI step in the app.")
    provider = st.selectbox(
        "Provider", list(llm.PROVIDERS), key="provider",
        index=list(llm.PROVIDERS).index(llm.DEFAULT_PROVIDER),
        format_func=lambda p: LABEL[p] + ("" if keys[p] else " (no key)"),
        help="Every provider sits behind the same function, so the tools work the same with any of them.",
    )
    st.text_input("Model name", value=llm.MODELS[provider], key=f"model_{provider}",
                  help="Model names change often. If you get 'model not found', update it here.")
    st.slider("Temperature", 0.0, 1.5, llm.DEFAULT_TEMPERATURE, 0.1, key="temp",
              help="0 gives near-identical answers each run; higher values vary more. "
                   "Low values suit classification and screening.")
    if not keys[provider]:
        st.warning(f"No {llm.KEY_NAMES[provider]} found. Add it to `.env` to use {LABEL[provider]}.")

    with st.expander("API keys and connection"):
        for p in llm.PROVIDERS:
            st.markdown(f"{':green[●]' if keys[p] else ':orange[●]'} `{llm.KEY_NAMES[p]}` "
                        f"{'found' if keys[p] else 'missing'}")
        st.caption("Only whether each key exists is shown, never the key.")
        if st.button("Test every provider", width="stretch", icon=":material/network_check:"):
            import ui

            with st.spinner("Calling providers..."):
                rows = [llm.timed_ask(p, "Reply with one word: OK.", "You are terse.",
                                      model=st.session_state.get(f"model_{p}", llm.MODELS[p]))
                        for p in llm.PROVIDERS if keys[p]]
            for row in pd.DataFrame(rows).itertuples() if rows else []:
                if str(row.answer).startswith("ERROR"):
                    st.markdown(f"**{LABEL[row.provider]}** failed ({row.seconds} s)")
                    ui.show_error(str(row.answer).removeprefix("ERROR: "))
                else:
                    st.success(f"**{LABEL[row.provider]}** replied in {row.seconds} s")
            if not rows:
                st.info("Add at least one API key to `.env` first.")

    if st.button("Clear cached results", width="stretch", icon=":material/refresh:",
                 help="Prices refresh every 15 minutes and AI answers are cached for an hour."):
        st.cache_data.clear()
        for k in [k for k in st.session_state if k.startswith(("res_", "case"))]:
            st.session_state.pop(k, None)
        st.toast("Cached results cleared")

    st.divider()
    st.caption(":material/contrast: **Light or dark?** Open the ⋮ menu at the top right, then "
               "Settings → Theme.")
    st.markdown('<p class="fineprint">Educational prototype for FIN42330, Python for Financial Data Science, '
                "UCD. Not financial advice and not a compliance system. Model output can be wrong; "
                "check primary sources.</p>", unsafe_allow_html=True)

# ── Navigation ────────────────────────────────────────────────────────────
pages = [
    st.Page("views/home.py", title="Home", icon=":material/home:", default=True),
    st.Page("views/markets.py", title="Markets", icon=":material/monitoring:"),
    st.Page("views/investigate.py", title="Investigate", icon=":material/travel_explore:"),
    st.Page("views/network.py", title="Network", icon=":material/hub:"),
    st.Page("views/news.py", title="News lookup", icon=":material/newspaper:"),
    st.Page("views/toolkit.py", title="AI toolkit", icon=":material/auto_awesome:"),
    st.Page("views/about.py", title="About", icon=":material/info:"),
]
page = st.navigation(pages, position="top")
page_enter(page.title)  # fade in when the page changes
page.run()
