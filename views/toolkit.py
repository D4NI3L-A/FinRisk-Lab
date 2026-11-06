"""AI toolkit: the four single-purpose tools from the first version of FinRisk Lab."""
from __future__ import annotations

import html
import json
import re
import time

import altair as alt
import pandas as pd
import streamlit as st

import llm
import samples
import ui
from risk import MAX_SCORE, RED_FLAGS, score_flags
from theme import BAND_KIND, COLORS, SENTIMENT_COLORS, chip, gauge, page_header

TICKER_RE = re.compile(r"^([A-Z][A-Z0-9.\-]{0,9}):\s*(.+)$")
LABEL = llm.PROVIDER_LABELS
provider, model, temp = ui.settings()
keys = llm.key_status()
show_error, run_llm, run_caption, messages_panel = ui.show_error, ui.run_llm, ui.run_caption, ui.messages_panel
cached_headlines, cached_media, cached_earnings, cached_flags = ui.headlines, ui.media, ui.earnings, ui.flags


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


def as_confidence(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").clip(0, 1)


def bulleted(items: list[str]) -> str:
    return "\n".join(f"- {x}" for x in items) or "Not stated"


page_header("AI toolkit", "Four single-purpose tools. Paste your own text or load an example, then run it with "
                          "the model chosen in the sidebar.")
tab_head, tab_earn, tab_media, tab_flags = st.tabs(
    [":material/newspaper: Headline sentiment", ":material/summarize: Earnings summary",
     ":material/policy: Adverse media", ":material/flag: Red-flag score"]
)

# ── Headline sentiment (lab Section 10) ──────────────────────────────────
with tab_head:
    st.subheader("Headline sentiment")
    st.caption("Label each headline from the shareholder's point of view, then aggregate by ticker.")
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
    st.subheader("Earnings summary")
    st.caption("Turn a call transcript into the fields a portfolio manager scans first.")
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
    st.subheader("Adverse-media screening")
    st.caption("Flag news that points to fraud, corruption, sanctions or money laundering.")
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
    st.subheader("Counterparty red-flag score")
    st.caption("Rules set the score. The model writes the narrative and must explain any disagreement.")
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
        st.plotly_chart(gauge(round(100 * result["score"] / MAX_SCORE), result["band"], height=200),
                        config={"displayModeBar": False}, key="tk_gauge")
        st.markdown(chip(f'{result["score"]} of {MAX_SCORE} points · {result["band"]}',
                         BAND_KIND.get(result["band"], "muted")), unsafe_allow_html=True)
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
