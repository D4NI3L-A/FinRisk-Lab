"""Shared Streamlit helpers: model settings, cached data and LLM calls, error display."""
from __future__ import annotations

import json
import time

import pandas as pd
import streamlit as st

import llm
from core import market

LABEL = llm.PROVIDER_LABELS


# ── Model settings (set in the sidebar by app.py) ─────────────────────────
def settings() -> tuple[str, str, float]:
    p = st.session_state.get("provider", llm.DEFAULT_PROVIDER)
    return p, st.session_state.get(f"model_{p}", llm.MODELS[p]), st.session_state.get("temp", llm.DEFAULT_TEMPERATURE)


# ── Cached market data ────────────────────────────────────────────────────
@st.cache_data(ttl=900, show_spinner=False)
def prices(tickers: tuple, period: str):
    return market.get_prices(list(tickers), period)


@st.cache_data(ttl=86_400, show_spinner=False)
def profile(ticker: str):
    return market.get_profile(ticker)


@st.cache_data(ttl=900, show_spinner=False)
def news(ticker: str):
    return market.get_news(ticker)


# ── Cached LLM calls (same input + provider + model = no extra API call) ──
@st.cache_data(ttl=3600, show_spinner=False)
def headlines(headlines_: tuple, tickers: tuple, provider: str, model: str, temp: float, mixed: bool = False):
    return llm.classify_headlines(list(headlines_), list(tickers), model=model, provider=provider,
                                  temperature=temp, allow_mixed=mixed)


@st.cache_data(ttl=3600, show_spinner=False)
def media(snippets: tuple, provider: str, model: str, temp: float):
    return llm.screen_adverse_media(list(snippets), model=model, provider=provider, temperature=temp)


@st.cache_data(ttl=3600, show_spinner=False)
def earnings(transcript: str, provider: str, model: str, temp: float):
    return llm.summarise_earnings(transcript, model=model, provider=provider, temperature=temp)


@st.cache_data(ttl=3600, show_spinner=False)
def flags(flags_: tuple, context: str, score_json: str, provider: str, model: str, temp: float):
    return llm.assess_red_flags(list(flags_), context, json.loads(score_json), model=model,
                                provider=provider, temperature=temp)


def show_error(message: str) -> None:
    """Show the error with the matching fix from the lab's troubleshooting table."""
    st.error(message)
    hint = llm.diagnose(message)
    if hint:
        st.info(f"**Likely cause:** {hint[0]}  \n**Fix:** {hint[1]}")


def run_llm(fn, *args):
    """Run a cached LLM call and time it. Returns (result, seconds), or None after showing the error.

    No st.stop(): that would also stop anything drawn further down the page.
    """
    start = time.perf_counter()
    try:
        return fn(*args), time.perf_counter() - start
    except llm.LLMError as e:
        show_error(str(e))
    except Exception as e:  # noqa: BLE001
        show_error(f"Unexpected error: {type(e).__name__}: {e}")
    return None


def run_caption(res: dict) -> None:
    served = "served from cache" if res["secs"] < 0.05 else f"{res['secs']:.1f} s"
    st.caption(f"{LABEL[res['provider']]} · `{res['model']}` · temperature {res['temp']} · {served}")


def messages_panel(system: str, user: str) -> None:
    """Lab Section 0: show exactly what is sent to the model."""
    with st.popover("Messages sent to the model", icon=":material/data_object:"):
        st.markdown("**System message** sets the model's role and rules")
        st.code(system, language="text", wrap_lines=True)
        st.markdown("**User message** is the task, built from your input")
        st.code(user if user.strip() else "(fills in from your input)", language="text", wrap_lines=True)


def demo_notice(is_demo: bool, what: str = "data") -> None:
    if is_demo:
        st.caption(f":material/info: Live {what} unavailable, showing fictional demo {what}.")


def pct(x: float | None, signed: bool = True, digits: int = 1) -> str:
    if x is None or pd.isna(x):
        return "n/a"
    return f"{x:+.{digits}%}" if signed else f"{x:.{digits}%}"
