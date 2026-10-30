"""FinRisk Lab: Streamlit UI.

Run with:  streamlit run app.py
"""
from __future__ import annotations

import html
import json
import re
import time

import altair as alt
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

import llm  # noqa: E402  (after load_dotenv so model overrides in .env are picked up)
import samples  # noqa: E402
from risk import BANDS, MAX_SCORE, RED_FLAGS, score_flags  # noqa: E402
from theme import COLORS, SENTIMENT_COLORS, band_meter, chip, inject_css, pipeline, section_intro  # noqa: E402

st.set_page_config(page_title="FinRisk Lab", page_icon="🛡️", layout="wide",
                   initial_sidebar_state="expanded")
inject_css()

TICKER_RE = re.compile(r"^([A-Z][A-Z0-9.\-]{0,9}):\s*(.+)$")
LABEL = llm.PROVIDER_LABELS


# ── Cached LLM wrappers (same input + provider + model = no extra API call) ──
@st.cache_data(ttl=3600, show_spinner=False)
def cached_headlines(headlines: tuple, tickers: tuple, provider: str, model: str, temp: float, mixed: bool):
    return llm.classify_headlines(list(headlines), list(tickers), model=model, provider=provider,
                                  temperature=temp, allow_mixed=mixed)


@st.cache_data(ttl=3600, show_spinner=False)
def cached_media(snippets: tuple, provider: str, model: str, temp: float):
    return llm.screen_adverse_media(list(snippets), model=model, provider=provider, temperature=temp)


@st.cache_data(ttl=3600, show_spinner=False)
def cached_earnings(transcript: str, provider: str, model: str, temp: float):
    return llm.summarise_earnings(transcript, model=model, provider=provider, temperature=temp)


@st.cache_data(ttl=3600, show_spinner=False)
def cached_flags(flags: tuple, context: str, score_json: str, provider: str, model: str, temp: float):
    return llm.assess_red_flags(list(flags), context, json.loads(score_json), model=model,
                                provider=provider, temperature=temp)


# ── Helpers ──────────────────────────────────────────────────────────────
def load_sample(key: str, value: str) -> None:
    st.session_state[key] = value


def parse_headlines(raw: str) -> tuple[list[str], list[str]]:
    headlines, tickers = [], []
    for line in (ln.strip() for ln in raw.splitlines()):
        if not line:
            continue
        m = TICKER_RE.match(line)
        tickers.append(m.group(1) if m else "GENERAL")
        headlines.append(m.group(2).strip() if m else line)
    return headlines, tickers


def show_error(message: str) -> None:
    """Show the error, plus the matching fix from the lab's troubleshooting table."""
    st.error(message)
    hint = llm.diagnose(message)
    if hint:
        st.info(f"**Likely cause:** {hint[0]}  \n**Fix:** {hint[1]}")


def run_llm(fn, *args):
    """Run a cached LLM call and time it. Returns (result, seconds), or None after showing the error.

    It doesn't call st.stop(): that would also stop the tabs further down the page from drawing.
    """
    start = time.perf_counter()
    try:
        return fn(*args), time.perf_counter() - start
    except llm.LLMError as e:
        show_error(str(e))
    except Exception as e:  # noqa: BLE001
        show_error(f"Unexpected error: {type(e).__name__}: {e}")
    return None


def messages_panel(system: str, user: str) -> None:
    """Lab Section 0: show exactly what is sent. The system message sets the role; the user message is the task."""
    with st.expander("Messages sent to the model"):
        st.markdown("**System message** · sets the model's role and rules")
        st.code(system, language="text", wrap_lines=True)
        st.markdown("**User message** · the task, built from your input")
        st.code(user if user.strip() else "(fills in from your input)", language="text", wrap_lines=True)


def run_caption(res: dict) -> None:
    served = "served from cache" if res["secs"] < 0.05 else f"{res['secs']:.1f} s"
    st.caption(f"{LABEL[res['provider']]} · `{res['model']}` · temperature {res['temp']} · {served}")


def as_confidence(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").clip(0, 1)


def bulleted(items: list[str]) -> str:
    return "\n".join(f"- {x}" for x in items) or "Not stated"


# ── Sidebar: model settings (lab Sections 1, 7 and 8) ────────────────────
keys = llm.key_status()
with st.sidebar:
    st.markdown(
        '<div class="brand"><span class="brand-mark">FR</span>'
        '<div><div class="brand-name">FinRisk Lab</div>'
        '<div class="brand-sub">Market and financial-crime risk triage</div></div></div>',
        unsafe_allow_html=True,
    )
    st.markdown("#### Model")
    provider = st.selectbox(
        "Provider",
        list(llm.PROVIDERS),
        index=list(llm.PROVIDERS).index(llm.DEFAULT_PROVIDER),
        format_func=lambda p: f"{LABEL[p]}" + ("" if keys[p] else " (no key)"),
        help="Every provider sits behind the same function, so the tools work the same with any of them.",
    )
    model = st.text_input("Model name", value=llm.MODELS[provider], key=f"model_{provider}",
                          help="Model names change often. If you get 'model not found', update it here.")
    temp = st.slider("Temperature", 0.0, 1.5, llm.DEFAULT_TEMPERATURE, 0.1,
                     help="0 gives near-identical answers each run; higher values vary more. "
                          "Low values suit classification and screening.")
    if not keys[provider]:
        st.warning(f"No {llm.KEY_NAMES[provider]} found. Add it to `.env` to use {LABEL[provider]}.")

    with st.expander("API keys and connection"):
        st.markdown(
            "\n".join(
                f'<div class="keyrow"><span class="dot {"ok" if keys[p] else "no"}"></span>'
                f'<code>{llm.KEY_NAMES[p]}</code><span>{"found" if keys[p] else "missing"}</span></div>'
                for p in llm.PROVIDERS
            ),
            unsafe_allow_html=True,
        )
        st.caption("Only whether each key exists is shown, never the key.")
        if st.button("Test every provider", width="stretch",
                     help="Sends one short message to each provider with a key and times the reply."):
            with st.spinner("Calling providers..."):
                rows = [llm.timed_ask(p, "Reply with one word: OK.", "You are terse.",
                                      model=st.session_state.get(f"model_{p}", llm.MODELS[p]))
                        for p in llm.PROVIDERS if keys[p]]
            if rows:
                test = pd.DataFrame(rows)
                test["provider"] = test["provider"].map(LABEL)
                for row in test.itertuples():
                    if str(row.answer).startswith("ERROR"):
                        st.markdown(f"**{row.provider}** failed ({row.seconds} s)")
                        show_error(str(row.answer).removeprefix("ERROR: "))
                    else:
                        st.success(f"**{row.provider}** replied in {row.seconds} s")
            else:
                st.info("Add at least one API key to `.env` first.")

    if st.button("Clear cached results", width="stretch",
                 help="Identical requests are cached for an hour. Clear to force fresh calls."):
        st.cache_data.clear()
        for k in ("res_head", "res_earn", "res_media", "res_flags"):
            st.session_state.pop(k, None)
        st.toast("Cached results cleared")

    st.markdown(
        '<p class="fineprint">Educational prototype for FIN42330, Python for Financial Data Science, '
        "UCD. Not financial advice and not a compliance system. Model output can be wrong; "
        "check primary sources.</p>",
        unsafe_allow_html=True,
    )


# ── Tabs ─────────────────────────────────────────────────────────────────
tab_home, tab_head, tab_earn, tab_media, tab_flags = st.tabs(
    ["Overview", "Headline sentiment", "Earnings summary", "Adverse media", "Red-flag score"]
)


# ── Overview ─────────────────────────────────────────────────────────────
with tab_home:
    st.markdown(
        '<section class="hero">'
        '<h1>Read the signal early.<br>Leave the judgment to people.</h1>'
        "<p>FinRisk Lab is a first-pass triage desk for two teams that sit side by side in a bank: "
        "advisors watching market news, and compliance analysts screening counterparties. "
        "Language models do the reading. Transparent rules set the score. An analyst makes the call.</p>"
        "</section>",
        unsafe_allow_html=True,
    )
    pipeline([
        ("Input", "Headlines, transcripts, news snippets or counterparty facts."),
        ("Rules", "Deterministic checks and weights anyone can audit."),
        ("Model", "One batched call returns structured JSON, validated before display."),
        ("Analyst", "Every flag is a lead to verify, not a decision."),
    ])

    left, right = st.columns(2, gap="large")
    with left:
        st.markdown("### Advisory desk")
        st.markdown(
            "**Headline sentiment** classifies news per ticker, scores net sentiment and lets you "
            "compare how different models label the same headline.\n\n"
            "**Earnings summary** turns a call transcript into revenue, EPS, guidance, highlights "
            "and risks, using only figures stated in the transcript."
        )
    with right:
        st.markdown("### Compliance desk")
        st.markdown(
            "**Adverse media** flags snippets that point to fraud, corruption, sanctions or "
            "laundering, with a category and a confidence level.\n\n"
            "**Red-flag score** adds up visible weights for counterparty risk factors, then asks "
            "the model for a narrative that must explain any disagreement with the score."
        )

    st.markdown('<div class="rule"></div>', unsafe_allow_html=True)
    why, roadmap = st.columns([3, 2], gap="large")
    with why:
        st.markdown("### Why this exists")
        st.markdown(
            "Illicit finance rarely shows up in a single transaction. It moves through networks "
            "of shell companies, intermediaries and public contracts, and the first trace is often "
            "a line in the news or a gap in an ownership record. FinRisk Lab is the first module "
            "of a longer project: a toolkit for spotting those patterns early and explaining every "
            "flag it raises."
        )
    with roadmap:
        st.markdown("### Where it goes next")
        st.markdown(
            "- Entity resolution, so the same company is recognised across sources\n"
            "- Counterparty networks in NetworkX, using betweenness centrality to surface brokers\n"
            "- Anomaly detection on contract and payment data\n"
            "- A labelled evaluation set to measure precision before any flag is trusted"
        )

    with st.expander("How this app covers the *Calling LLM APIs* lab"):
        st.markdown(
            """
| Lab section | Where it shows up in FinRisk Lab |
|---|---|
| 0 · What is an API | Every tool has a **Messages sent to the model** panel showing the system and user message |
| 1 · Keys and models | Sidebar shows each key as found or missing, never the key; model names are editable |
| 2–5 · Four providers | DeepSeek, OpenAI, Gemini and Claude, each with its own `ask_*` function in `llm.py` |
| 6–7 · Functions and temperature | Same inputs and output for every provider; temperature slider in the sidebar |
| 8 · One function for all | `PROVIDERS` dictionary and `ask_llm` with `try`/`except` and timing; **Test every provider** compares them |
| 9 · Earnings summary | JSON mode, `json.loads`, field validation and JSON download |
| 10 · News sentiment | Batch classification, optional *Mixed* label, model agreement table and CSV download |
| Troubleshooting | Errors are matched to the lab's table and shown with a suggested fix |
| Cost warning | One batched call per task, one-hour cache, `max_tokens` cap and a 40-item limit |
"""
        )


# ── Headline sentiment (lab Section 10) ──────────────────────────────────
with tab_head:
    section_intro("Headline sentiment",
                  "Label each headline from the shareholder's point of view, then aggregate by ticker.")
    inp, info = st.columns([3, 2], gap="large")
    with inp:
        with st.container(border=True):
            st.button("Load example", key="ex_head", on_click=load_sample,
                      args=("headlines_raw", samples.HEADLINES))
            raw = st.text_area("Headlines, one per line", height=210, key="headlines_raw",
                               placeholder="NWE: Northwind Energy beats quarterly earnings estimates")
            o1, o2 = st.columns(2)
            mode = o1.radio("Run with", ["Selected model", "Compare models"], horizontal=True,
                            help="Compare models sends the same batch to several providers and checks agreement.")
            mixed = o2.toggle("Allow a Mixed label", help="Lab Section 10 exercise: a fourth label for "
                                                          "headlines with both good and bad news.")
            compare_with = []
            if mode == "Compare models":
                compare_with = st.multiselect(
                    "Providers to compare", list(llm.PROVIDERS),
                    default=[p for p in llm.PROVIDERS if keys[p]],
                    format_func=lambda p: LABEL[p],
                )
            go = st.button("Analyse headlines", type="primary", width="stretch")
    headlines, tickers = parse_headlines(raw)
    with info:
        st.markdown("##### How it works")
        st.markdown(
            "Prefix a line with `TICKER:` to group it; lines without one go under GENERAL. "
            "All headlines go in **one call**, and each result is matched back to its headline by "
            "index, so a skipped row shows as *Unclassified* instead of shifting labels."
        )
        messages_panel(llm.portfolio_system(mixed), llm.headlines_prompt(headlines, tickers) if headlines else "")

    if go and not headlines:
        st.warning("Paste at least one headline, or select **Load example**.")
    elif go and mode == "Selected model":
        with st.spinner(f"Classifying {len(headlines)} headlines with {LABEL[provider]}..."):
            out = run_llm(cached_headlines, tuple(headlines), tuple(tickers), provider, model, temp, mixed)
        if out:
            st.session_state["res_head"] = {"mode": "single", "df": pd.DataFrame(out[0]), "secs": out[1],
                                            "provider": provider, "model": model, "temp": temp, "mixed": mixed}
    elif go and len(compare_with) < 2:
        st.warning("Choose at least two providers to compare.")
    elif go:
        table = pd.DataFrame({"ticker": tickers, "headline": headlines})
        timing = []
        progress = st.progress(0.0, text="Starting...")
        for i, p in enumerate(compare_with):
            progress.progress(i / len(compare_with), text=f"Asking {LABEL[p]}...")
            m = st.session_state.get(f"model_{p}", llm.MODELS[p])
            start = time.perf_counter()
            try:
                out = cached_headlines(tuple(headlines), tuple(tickers), p, m, temp, mixed)
                table[LABEL[p]] = [r["sentiment"] for r in out]
                timing.append({"provider": LABEL[p], "model": m,
                               "seconds": round(time.perf_counter() - start, 2), "status": "OK"})
            except Exception as e:  # noqa: BLE001  one failure shouldn't stop the comparison
                table[LABEL[p]] = "Error"
                timing.append({"provider": LABEL[p], "model": m,
                               "seconds": round(time.perf_counter() - start, 2), "status": str(e)[:120]})
        progress.empty()
        cols = [LABEL[p] for p in compare_with]
        table["all_agree"] = table[cols].nunique(axis=1) == 1
        st.session_state["res_head"] = {"mode": "compare", "df": table, "timing": pd.DataFrame(timing),
                                        "cols": cols}

    res = st.session_state.get("res_head")
    if res is None:
        st.markdown('<p class="empty">Results appear here. Try <b>Load example</b>, then '
                    "<b>Analyse headlines</b>.</p>", unsafe_allow_html=True)
    elif res["mode"] == "single":
        df = res["df"]
        df["confidence"] = as_confidence(df["confidence"])
        labels = ["Positive", "Negative", "Neutral"] + (["Mixed"] if res["mixed"] else [])
        n_pos, n_neg = df["sentiment"].eq("Positive").sum(), df["sentiment"].eq("Negative").sum()

        st.markdown("#### Results")
        run_caption(res)
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Headlines", len(df))
        k2.metric("Tickers", df["ticker"].nunique())
        k3.metric("Net sentiment", f"{(n_pos - n_neg) / len(df):+.2f}",
                  help="(Positive − Negative) ÷ all headlines. Ranges from −1 to +1.")
        k4.metric("Unclassified", int(df["sentiment"].eq("Unclassified").sum()))

        mix = df.groupby(["ticker", "sentiment"]).size().reset_index(name="count")
        net = (df.assign(score=df["sentiment"].map({"Positive": 1, "Negative": -1}).fillna(0))
                 .groupby("ticker", as_index=False)["score"].mean().rename(columns={"score": "net"}))
        order = net.sort_values("net")["ticker"].tolist()
        height = 44 * len(order) + 30

        c1, c2 = st.columns([3, 2], gap="large")
        with c1:
            st.markdown("##### Sentiment mix by ticker")
            domain = labels + ["Unclassified"]
            chart = alt.Chart(mix).mark_bar(height=22).encode(
                y=alt.Y("ticker:N", sort=order, title=None),
                x=alt.X("count:Q", stack="normalize", title=None, axis=alt.Axis(format="%")),
                color=alt.Color("sentiment:N", scale=alt.Scale(domain=domain,
                                range=[SENTIMENT_COLORS[s] for s in domain]),
                                legend=alt.Legend(orient="top", title=None)),
                order=alt.Order("sentiment:N"),
                tooltip=["ticker", "sentiment", "count"],
            ).properties(height=height)
            st.altair_chart(chart, width="stretch")
        with c2:
            st.markdown("##### Net score")
            bars = alt.Chart(net).mark_bar(height=22).encode(
                y=alt.Y("ticker:N", sort=order, title=None),
                x=alt.X("net:Q", scale=alt.Scale(domain=[-1, 1]), title=None),
                color=alt.condition(alt.datum.net >= 0, alt.value(COLORS["clear"]), alt.value(COLORS["risk"])),
                tooltip=["ticker", alt.Tooltip("net:Q", format="+.2f")],
            )
            zero = alt.Chart(pd.DataFrame({"x": [0]})).mark_rule(color=COLORS["ink"]).encode(x="x:Q")
            st.altair_chart((bars + zero).properties(height=height), width="stretch")

        st.markdown("##### Every headline")
        st.dataframe(
            df.style.map(lambda v: f"color: {SENTIMENT_COLORS.get(v, COLORS['ink'])}; font-weight: 600",
                         subset=["sentiment"]),
            hide_index=True, width="stretch",
            column_config={
                "ticker": st.column_config.TextColumn("Ticker", width="small"),
                "headline": st.column_config.TextColumn("Headline", width="large"),
                "sentiment": "Sentiment",
                "confidence": st.column_config.ProgressColumn("Confidence", min_value=0, max_value=1, format="%.2f"),
                "reasoning": "Why",
            },
        )
        if df["sentiment"].eq("Unclassified").any():
            st.info("The model skipped some headlines. Run again, or try another provider.")
        st.download_button("Download CSV", df.to_csv(index=False).encode(), "headline_sentiment.csv", "text/csv")
    else:
        table, cols = res["df"], res["cols"]
        st.markdown("#### Model comparison")
        k1, k2 = st.columns(2)
        k1.metric("All models agree", f"{table['all_agree'].mean():.0%}",
                  help="Share of headlines where every selected model gave the same label.")
        k2.metric("Headlines", len(table))
        st.dataframe(
            table.style.map(lambda v: f"color: {SENTIMENT_COLORS.get(v, COLORS['ink'])}; font-weight: 600",
                            subset=cols),
            hide_index=True, width="stretch",
            column_config={"ticker": st.column_config.TextColumn("Ticker", width="small"),
                           "headline": st.column_config.TextColumn("Headline", width="large"),
                           "all_agree": st.column_config.CheckboxColumn("All agree")},
        )
        st.markdown("##### Response time")
        st.dataframe(res["timing"], hide_index=True, width="stretch",
                     column_config={"seconds": st.column_config.NumberColumn("Seconds", format="%.2f")})
        st.caption("A time near zero means the answer came from the one-hour cache.")
        st.download_button("Download CSV", table.to_csv(index=False).encode(), "headline_comparison.csv", "text/csv")


# ── Earnings summary (lab Section 9) ─────────────────────────────────────
with tab_earn:
    section_intro("Earnings summary",
                  "Turn a call transcript into the fields a portfolio manager scans first.")
    inp, info = st.columns([3, 2], gap="large")
    with inp:
        with st.container(border=True):
            st.button("Load example", key="ex_earn", on_click=load_sample,
                      args=("transcript_raw", samples.TRANSCRIPT))
            transcript = st.text_area("Transcript", height=300, key="transcript_raw",
                                      placeholder="Paste the full call transcript here.")
            go = st.button("Summarise transcript", type="primary", width="stretch")
    with info:
        st.markdown("##### How it works")
        st.markdown(
            "The model answers in JSON mode, the text is parsed with `json.loads`, and every field "
            "is checked before display. Missing figures read *Not stated*; the prompt forbids "
            "invented numbers. Limit: 60,000 characters."
        )
        preview = transcript[:600] + ("\n[...]" if len(transcript) > 600 else "")
        messages_panel(llm.EARNINGS_SYSTEM, llm.earnings_prompt(preview) if transcript.strip() else "")

    if go and not transcript.strip():
        st.warning("Paste a transcript first, or select **Load example**.")
    elif go:
        with st.spinner(f"Summarising with {LABEL[provider]}..."):
            out = run_llm(cached_earnings, transcript, provider, model, temp)
        if out:
            st.session_state["res_earn"] = {"s": out[0], "secs": out[1], "provider": provider,
                                            "model": model, "temp": temp}

    res = st.session_state.get("res_earn")
    if res is None:
        st.markdown('<p class="empty">The summary appears here.</p>', unsafe_allow_html=True)
    else:
        s = res["s"]
        tone_kind = {"Positive": "clear", "Negative": "risk", "Mixed": "flag"}.get(s["tone"], "muted")
        st.markdown(
            f'<div class="report-head"><h3>{html.escape(s["company"])}</h3>'
            f'<span class="quarter">{html.escape(s["quarter"])}</span>'
            f'{chip("Tone: " + s["tone"], tone_kind)}</div>',
            unsafe_allow_html=True,
        )
        run_caption(res)
        m1, m2 = st.columns(2)
        m1.metric("Revenue", s["revenue"])
        m2.metric("EPS", s["eps"])
        st.markdown(f'<blockquote class="guidance"><b>Guidance</b><br>{html.escape(s["guidance"])}</blockquote>',
                    unsafe_allow_html=True)
        h, r = st.columns(2, gap="large")
        with h:
            st.markdown("##### Highlights")
            st.markdown(bulleted(s["highlights"]))
        with r:
            st.markdown("##### Risks")
            st.markdown(bulleted(s["risks"]))
        st.markdown("##### Outlook")
        st.write(s["outlook"])
        payload = json.dumps(s, indent=2, ensure_ascii=False)
        with st.expander("Raw JSON"):
            st.code(payload, language="json")
        st.download_button("Download JSON", payload.encode(), "earnings_summary.json", "application/json")


# ── Adverse media ────────────────────────────────────────────────────────
with tab_media:
    section_intro("Adverse-media screening",
                  "Flag news that points to fraud, corruption, sanctions or money laundering.")
    inp, info = st.columns([3, 2], gap="large")
    with inp:
        with st.container(border=True):
            st.button("Load example", key="ex_media", on_click=load_sample,
                      args=("snippets_raw", samples.SNIPPETS))
            snippets_raw = st.text_area("News snippets, one per line", height=210, key="snippets_raw",
                                        placeholder="Harbourline Trading fined €4.2m for AML control failures")
            go = st.button("Screen snippets", type="primary", width="stretch")
    snippets = [ln.strip() for ln in snippets_raw.splitlines() if ln.strip()]
    with info:
        st.markdown("##### How it works")
        st.markdown(
            "Each snippet gets a flag, a financial-crime category and a confidence level. "
            "Allegations count, and the reason says so. Ordinary business news is not flagged. "
            "This is first-pass triage: every flag needs a human check against the source."
        )
        messages_panel(llm.ADVERSE_MEDIA_SYSTEM, llm.media_prompt(snippets) if snippets else "")

    if go and not snippets:
        st.warning("Paste at least one snippet, or select **Load example**.")
    elif go:
        with st.spinner(f"Screening {len(snippets)} snippets with {LABEL[provider]}..."):
            out = run_llm(cached_media, tuple(snippets), provider, model, temp)
        if out:
            st.session_state["res_media"] = {"df": pd.DataFrame(out[0]), "secs": out[1],
                                             "provider": provider, "model": model, "temp": temp}

    res = st.session_state.get("res_media")
    if res is None:
        st.markdown('<p class="empty">Screening results appear here.</p>', unsafe_allow_html=True)
    else:
        df = res["df"]
        flagged = df[df["flag"]]
        st.markdown("#### Results")
        run_caption(res)
        k1, k2, k3 = st.columns(3)
        k1.metric("Screened", len(df))
        k2.metric("Flagged for review", len(flagged))
        k3.metric("Flag rate", f"{len(flagged) / len(df):.0%}")
        if not flagged.empty:
            cats = flagged["category"].str.replace("_", " ").str.capitalize().value_counts().reset_index()
            cats.columns = ["category", "count"]
            st.markdown("##### Flags by category")
            st.altair_chart(
                alt.Chart(cats).mark_bar(height=20, color=COLORS["flag"]).encode(
                    y=alt.Y("category:N", sort="-x", title=None),
                    x=alt.X("count:Q", title=None, axis=alt.Axis(tickMinStep=1, format="d")),
                    tooltip=["category", "count"],
                ).properties(height=40 * len(cats) + 20),
                width="stretch",
            )
        view = df.sort_values("flag", ascending=False)
        st.dataframe(
            view.style.apply(lambda row: [f"background-color: {COLORS['flag_tint']}" if row["flag"] else ""] * len(row),
                             axis=1),
            hide_index=True, width="stretch",
            column_config={"flag": st.column_config.CheckboxColumn("Flag", width="small"),
                           "snippet": st.column_config.TextColumn("Snippet", width="large"),
                           "category": "Category", "confidence": "Confidence", "reasoning": "Why"},
        )
        st.download_button("Download CSV", df.to_csv(index=False).encode(), "adverse_media.csv", "text/csv")


# ── Red-flag score ───────────────────────────────────────────────────────
with tab_flags:
    section_intro("Counterparty red-flag score",
                  "Rules set the score. The model writes the narrative and must explain any disagreement.")
    inp, score_col = st.columns([3, 2], gap="large")
    with inp:
        with st.container(border=True):
            selected = st.multiselect("Red flags present", list(RED_FLAGS), key="aml_flags",
                                      placeholder="Choose the risk factors that apply")
            context = st.text_area("Context (optional)", height=90, key="aml_context",
                                   placeholder="e.g. Trading company, 2 years old, payments routed via a third country")
            go = st.button("Write risk narrative", type="primary", width="stretch")
    result = score_flags(selected)
    with score_col:
        st.markdown("##### Rule-based score")
        st.markdown(band_meter(result["score"], MAX_SCORE, BANDS, result["band"]), unsafe_allow_html=True)
        messages_panel(llm.RED_FLAG_SYSTEM, llm.flags_prompt(selected, context, result))

    weights = pd.DataFrame([{"Flag": f, "Weight": w, "Selected": f in selected} for f, w in RED_FLAGS.items()])
    with st.expander("Weights behind the score", expanded=not selected):
        st.dataframe(
            weights, hide_index=True, width="stretch",
            column_config={"Flag": st.column_config.TextColumn(width="large"),
                           "Weight": st.column_config.ProgressColumn(min_value=0, max_value=3, format="%d"),
                           "Selected": st.column_config.CheckboxColumn(width="small")},
        )
        st.caption("Illustrative weights loosely based on FATF risk factors, not calibrated on data. "
                   "Bands: Low below 4, Medium 4–6, High 7 or more.")

    if go and not selected and not context.strip():
        st.warning("Choose at least one red flag or add some context.")
    elif go:
        with st.spinner(f"Writing narrative with {LABEL[provider]}..."):
            out = run_llm(cached_flags, tuple(selected), context, json.dumps(result), provider, model, temp)
        if out:
            st.session_state["res_flags"] = {"a": out[0], "band": result["band"], "secs": out[1],
                                             "provider": provider, "model": model, "temp": temp}

    res = st.session_state.get("res_flags")
    if res is not None:
        a = res["a"]
        kinds = {"High": "risk", "Medium": "flag", "Low": "clear"}
        agree = a["risk_rating"] == res["band"]
        st.markdown("#### Risk narrative")
        run_caption(res)
        st.markdown(
            f'<div class="verdicts">{chip("Rules: " + res["band"], kinds.get(res["band"], "muted"))}'
            f'{chip("Model: " + a["risk_rating"], kinds.get(a["risk_rating"], "muted"))}'
            f'<span class="verdict-note">{"Rules and model agree." if agree else "Rules and model disagree; see the note below."}</span></div>',
            unsafe_allow_html=True,
        )
        if a.get("divergence_note"):
            st.info(f"**Why the model diverges:** {a['divergence_note']}")
        st.write(a.get("narrative", "Not stated"))
        d, n = st.columns(2, gap="large")
        with d:
            st.markdown("##### Key drivers")
            st.markdown(bulleted(a.get("key_drivers", [])))
        with n:
            st.markdown("##### Next steps")
            st.markdown(bulleted(a.get("recommended_next_steps", [])))
        with st.expander("Raw JSON"):
            st.code(json.dumps(a, indent=2, ensure_ascii=False), language="json")
