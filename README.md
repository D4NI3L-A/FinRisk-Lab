# FinRisk Lab

**LLM-assisted market and financial-crime risk triage, built with Python and Streamlit. Works with Gemini, OpenAI, DeepSeek or Claude.**

FinRisk Lab is a first-pass risk desk for market and financial-crime signals. Search a company and
work through a guided case, watch the market, or map a network of counterparties.

| Page | What it does |
|---|---|
| **Investigate** | Five-step case on one company: profile, market risk, news sentiment, adverse media and red flags. Each step adds to one composite risk score (shown as a %), with links to Yahoo Finance, SEC EDGAR, OpenSanctions, OFAC and the news sources. Exports a Markdown report. |
| **Markets** | Watchlist of any Yahoo Finance tickers: performance chart, volatility, drawdown, beta, correlation heatmap, and the latest headlines scored by AI. |
| **Network** | Interactive counterparty graph (NetworkX + Plotly). Dot size is betweenness centrality (brokers), colour is risk. Click an entity, filter by link type or payment size, and trace the path between two entities. Upload your own edges as CSV. |
| **AI toolkit** | Headline sentiment (with model comparison), earnings-call summary, adverse-media screening and the red-flag score. |

<!-- Add a screenshot: docs/screenshot.png -->

## Design decisions

- **Rules before judgment.** The counterparty score is a deterministic weighted sum with
  visible weights (`risk.py`). The LLM only writes the narrative, and has to say so when its
  rating differs from the rule-based band. Every number can be audited.
- **No silent misalignment.** Batch results are mapped back to inputs by `index`. If the model
  drops or reorders a row, the affected item shows as *Unclassified*; labels never shift
  onto the wrong headline.
- **Structured output.** Gemini's native JSON mode, then validation and normalisation
  (labels, ratings and field types) before anything reaches the UI.
- **Free-tier friendly.** One batched call per task, exponential backoff with jitter on
  `429`/`503`, and a one-hour cache for repeated requests.
- **Four providers, one interface.** As in the lab: one `ask_*` function per provider with the same
  inputs and output, a `PROVIDERS` dictionary, and a single `ask_llm()` entry point. Switch provider,
  model and temperature in the sidebar, or run the same headlines through several models and check
  how often they agree.
- **Errors you can act on.** Failures are matched to the lab's troubleshooting table (bad key, no
  credit, retired model, rate limit, missing package) and shown with the fix.
- **See what is sent.** Every tool shows the exact system and user message behind each call.

## Run locally

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then paste at least one API key into .env
streamlit run app.py
```

Market data comes from Yahoo Finance through `yfinance`. If it is unreachable, the app switches to clearly
labelled demo data. The demo network on the Network page is entirely fictional.

## Tests

```bash
pytest -q
```

The tests run offline by stubbing the API call. They cover index alignment, malformed JSON,
retry behaviour, field normalisation, provider routing, the Mixed label, error diagnosis and
the score bands.

## Project structure

```
app.py        Entry point: page setup, AI settings sidebar, navigation
views/        One file per page (home, markets, investigate, network, toolkit, about)
core/         Logic without Streamlit: market data, case scoring, network analysis, report export
ui.py         Shared Streamlit helpers: settings, cached data and AI calls, error display
theme.py      Colour tokens, CSS and chart styling
llm.py        Provider functions, prompts, validated workflows
risk.py       Transparent rule-based red-flag scoring
samples.py    Fictional demo inputs
tests/        Offline unit tests
```

## Limitations

This is an educational prototype, not financial advice and not a compliance system.
LLMs can misclassify, miss context or hallucinate, and the red-flag weights are illustrative
rather than calibrated. A real deployment would need source attribution for adverse media,
entity resolution, a labelled evaluation set, and human review of every flag.

---
## Lab coverage

| *Calling LLM APIs* lab | In FinRisk Lab |
|---|---|
| 0 · What is an API | "Messages sent to the model" panel on every tool |
| 1 · Keys and models | Key found/missing status in the sidebar; editable model names |
| 2–5 · DeepSeek, OpenAI, Gemini, Claude | `ask_deepseek`, `ask_openai`, `ask_gemini`, `ask_claude` in `llm.py` |
| 6–7 · Functions, temperature | Same signature for every provider; temperature slider |
| 8 · One function for all | `PROVIDERS` + `ask_llm`; timed comparison of every provider |
| 9 · Earnings summary | JSON mode → `json.loads` → validated fields → download |
| 10 · News sentiment | Batch labels, optional *Mixed*, model-agreement table, CSV export |
| Troubleshooting | `llm.diagnose()` turns errors into fixes in the UI |

---
Built for FIN42330 *Python for Financial Data Science*, MSc Financial Data Science,
University College Dublin.
