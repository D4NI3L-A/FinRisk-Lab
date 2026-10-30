# FinRisk Lab

**LLM-assisted market and financial-crime risk triage, built with Python and Streamlit. Works with Gemini, OpenAI, DeepSeek or Claude.**

FinRisk Lab puts one LLM layer under two workflows that sit next to each other in a
financial institution:

| Workflow | Tool | What it does |
|---|---|---|
| Advisory | Headline sentiment | Classifies news per ticker and aggregates a net sentiment score |
| Advisory | Earnings summary | Turns a call transcript into structured fields (revenue, EPS, guidance, risks, tone) |
| Compliance | Adverse-media screening | Flags snippets that point to fraud, corruption, sanctions or laundering, with category and confidence |
| Compliance | Red-flag assessment | Transparent rule-based counterparty score, plus an LLM narrative that must explain any disagreement |

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

Each tab has a **Load example** button that fills in fictional demo data.

## Tests

```bash
pytest -q
```

The tests run offline by stubbing the API call. They cover index alignment, malformed JSON,
retry behaviour, field normalisation, provider routing, the Mixed label, error diagnosis and
the score bands.

## Project structure

```
app.py        Streamlit UI
theme.py      Colour tokens, CSS and small HTML helpers for the UI
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
