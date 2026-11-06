"""About: why FinRisk Lab exists, how it works, and how it covers the course."""
from __future__ import annotations

import streamlit as st

from theme import page_header

page_header("About FinRisk Lab", "A first-pass risk desk for market and financial-crime signals. "
                                 "Models do the reading, transparent rules set the score, people make the call.")

a, b = st.columns([3, 2], gap="large")
with a:
    st.markdown("#### Why this exists")
    st.write(
        "Illicit finance rarely shows up in a single transaction. It moves through networks of shell "
        "companies, intermediaries and public contracts, and the first trace is often a line in the news or "
        "a gap in an ownership record. FinRisk Lab is the first module of a longer project: a toolkit for "
        "spotting those patterns early and explaining every flag it raises."
    )
    st.markdown("#### How a case is scored")
    st.markdown(
        "| Step | What it measures | Weight |\n|---|---|---|\n"
        "| Market risk | Volatility and drawdown over a year | 15% |\n"
        "| News sentiment | Share of negative headlines | 20% |\n"
        "| Adverse media | Confidence-weighted share of financial-crime flags | 30% |\n"
        "| Red flags | Transparent weighted checklist (FATF-style risk factors) | 35% |\n\n"
        "Steps you skip are left out and the other weights are rescaled, so the verdict always shows "
        "how much evidence it rests on. Weights are illustrative, not calibrated."
    )
with b:
    st.markdown("#### Where it goes next")
    st.markdown(
        "- Entity resolution, so the same company is recognised across sources\n"
        "- Ownership and payment data feeding the network map automatically\n"
        "- Anomaly detection on contract and payment data\n"
        "- A labelled evaluation set to measure precision before any flag is trusted"
    )
    st.markdown("#### Built with")
    st.markdown("Python · Streamlit · pandas · NumPy · NetworkX · Plotly · yfinance · "
                "Gemini, OpenAI, DeepSeek and Claude APIs")

with st.expander("How this app covers the *Calling LLM APIs* lab", icon=":material/school:"):
    st.markdown(
        """
| Lab section | Where it shows up in FinRisk Lab |
|---|---|
| 0 · What is an API | Every AI tool has a **Messages sent to the model** button showing the system and user message |
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

st.caption("Educational prototype for FIN42330 Python for Financial Data Science, UCD. Not financial advice "
           "and not a compliance system. Demo companies, people and places in the Network page are fictional.")
