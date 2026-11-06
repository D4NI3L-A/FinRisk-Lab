"""LLM utilities for FinRisk Lab.

Follows the structure of the FIN42330 lab "Calling LLM APIs":

1. One function per provider (``ask_deepseek``, ``ask_openai``, ``ask_gemini``,
   ``ask_claude``). Each takes the same inputs and returns a plain string.
2. A ``PROVIDERS`` dictionary that maps a provider name to its function.
3. ``ask_llm()``: one entry point for any provider, with retries and timing.
4. ``ask_llm_json()``: the same, parsed as JSON.
5. Four task-level workflows built on top. Each makes a single batched call,
   so the app stays inside free-tier rate limits.
"""
from __future__ import annotations

import json
import os
import random
import time
from typing import Any, Callable

# ── Setup: keys and models (lab Section 1) ───────────────────────────────
KEY_NAMES = {
    "gemini": "GEMINI_API_KEY",
    "openai": "OPENAI_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "claude": "ANTHROPIC_API_KEY",
}

MODELS = {
    "gemini": os.getenv("GEMINI_MODEL", "gemini-3.6-flash"),
    "openai": os.getenv("OPENAI_MODEL", "gpt-5.6-luna"),
    "deepseek": os.getenv("DEEPSEEK_MODEL", "deepseek-flash"),
    "claude": os.getenv("CLAUDE_MODEL", "claude-haiku-5-5"),
}

PROVIDER_LABELS = {"gemini": "Gemini", "openai": "OpenAI", "deepseek": "DeepSeek", "claude": "Claude"}

DEFAULT_PROVIDER = "gemini"
DEFAULT_MODEL = MODELS[DEFAULT_PROVIDER]
DEFAULT_TEMPERATURE = 0.2
MAX_TOKENS = 4000          # caps the length (and cost) of each answer
MAX_RETRIES = 3
MAX_BATCH = 40             # max headlines / snippets per call
MAX_TRANSCRIPT_CHARS = 60_000

_TRANSIENT_MARKERS = ("429", "RESOURCE_EXHAUSTED", "RateLimit", "500", "503", "529",
                      "UNAVAILABLE", "Overloaded", "DEADLINE")


class LLMError(RuntimeError):
    """Raised when the LLM call fails or returns something unusable."""


def key_status() -> dict[str, bool]:
    """Whether each provider's key was found. Never returns the key itself."""
    return {p: bool(os.getenv(k)) for p, k in KEY_NAMES.items()}


def is_demo(provider: str) -> bool:
    """Demo mode: the provider has no API key, so AI steps return simulated, clearly labelled answers."""
    return provider in KEY_NAMES and not os.getenv(KEY_NAMES[provider])


def _key(provider: str) -> str:
    key = os.getenv(KEY_NAMES[provider])
    if not key:
        raise LLMError(f"{KEY_NAMES[provider]} is not set. Add it to your .env file.")
    return key


# ── One function per provider (lab Sections 2-5 and 7) ──────────────────
# Imports are lazy, so the app (and the tests) still run if one SDK is missing.
def _openai_style(prompt, system, model, temperature, json_mode, base_url=None, key_provider="openai"):
    from openai import OpenAI

    client = OpenAI(api_key=_key(key_provider), base_url=base_url)
    kwargs = {"response_format": {"type": "json_object"}} if json_mode else {}
    r = client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        **kwargs,
    )
    return r.choices[0].message.content


def ask_deepseek(prompt, system, model=MODELS["deepseek"], temperature=DEFAULT_TEMPERATURE, json_mode=False):
    return _openai_style(prompt, system, model, temperature, json_mode,
                         base_url="https://api.deepseek.com", key_provider="deepseek")


def ask_openai(prompt, system, model=MODELS["openai"], temperature=DEFAULT_TEMPERATURE, json_mode=False):
    return _openai_style(prompt, system, model, temperature, json_mode)


def ask_gemini(prompt, system, model=MODELS["gemini"], temperature=DEFAULT_TEMPERATURE, json_mode=False):
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=_key("gemini"))
    config = types.GenerateContentConfig(
        system_instruction=system,
        temperature=temperature,
        response_mime_type="application/json" if json_mode else "text/plain",
    )
    r = client.models.generate_content(model=model, contents=prompt, config=config)
    return r.text


def ask_claude(prompt, system, model=MODELS["claude"], temperature=DEFAULT_TEMPERATURE, json_mode=False):
    import anthropic

    client = anthropic.Anthropic(api_key=_key("claude"))
    if json_mode:  # Claude has no JSON switch; the system prompt already asks for JSON
        system += "\nRespond with the JSON object only, no other text."
    r = client.messages.create(
        model=model,
        max_tokens=MAX_TOKENS,  # required by Anthropic; also caps cost
        temperature=min(temperature, 1.0),
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return r.content[0].text


# ── One dictionary for all providers (lab Section 8) ─────────────────────
PROVIDERS: dict[str, Callable[..., str]] = {
    "gemini": ask_gemini,
    "openai": ask_openai,
    "deepseek": ask_deepseek,
    "claude": ask_claude,
}


def _generate(prompt: str, system: str, model: str, temperature: float, json_mode: bool,
              provider: str = DEFAULT_PROVIDER) -> str:
    """Single dispatch point. The only place that picks a provider function."""
    if provider not in PROVIDERS:
        raise LLMError(f"Unknown provider '{provider}'. Choose from {list(PROVIDERS)}.")
    if is_demo(provider):  # no key: answer with transparent rules instead of failing (see demo_ai.py)
        import demo_ai

        return demo_ai.respond(prompt, system, json_mode)
    try:
        text = PROVIDERS[provider](prompt, system, model=model, temperature=temperature, json_mode=json_mode)
    except ModuleNotFoundError as e:
        raise LLMError(f"The SDK for {PROVIDER_LABELS[provider]} is not installed ({e.name}). "
                       "Run: pip install -r requirements.txt") from e
    if not text:
        raise LLMError("The model returned an empty response (it may have been blocked by safety filters).")
    return text


def ask_llm(
    prompt: str,
    system: str,
    model: str = DEFAULT_MODEL,
    temperature: float = DEFAULT_TEMPERATURE,
    json_mode: bool = False,
    provider: str = DEFAULT_PROVIDER,
) -> str:
    """Call any provider and return text. Retries transient errors with exponential backoff."""
    last_err: Exception | None = None
    attempt = 0
    for attempt in range(MAX_RETRIES):
        try:
            return _generate(prompt, system, model, temperature, json_mode, provider=provider)
        except LLMError:
            raise
        except Exception as e:  # noqa: BLE001 - SDK error types vary between providers
            last_err = e
            if any(k in str(e) for k in _TRANSIENT_MARKERS) and attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt + random.random())  # ~1s, 2s, 4s + jitter
                continue
            break
    label = PROVIDER_LABELS.get(provider, provider)
    raise LLMError(f"{label} call failed after {attempt + 1} attempt(s): {type(last_err).__name__}: {last_err}")



def timed_ask(provider: str, prompt: str, system: str, model: str | None = None,
              temperature: float = DEFAULT_TEMPERATURE) -> dict:
    """Lab Section 8 ``ask_llm``: answer or error, plus seconds taken. Never raises."""
    start = time.perf_counter()
    try:
        answer = ask_llm(prompt, system, model=model or MODELS[provider],
                         temperature=temperature, provider=provider)
    except Exception as e:  # noqa: BLE001
        answer = f"ERROR: {e}"
    return {"provider": provider, "answer": answer, "seconds": round(time.perf_counter() - start, 2)}


def _strip_code_fences(text: str) -> str:
    """Remove ```json ... ``` wrappers if the model adds them anyway."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def ask_llm_json(prompt: str, system: str, model: str = DEFAULT_MODEL,
                 provider: str = DEFAULT_PROVIDER, temperature: float = DEFAULT_TEMPERATURE) -> Any:
    """Call a provider in JSON mode and parse the result (lab Section 9: str -> dict)."""
    raw = ask_llm(prompt, system, model=model, temperature=temperature, json_mode=True, provider=provider)
    try:
        return json.loads(_strip_code_fences(raw))
    except json.JSONDecodeError as e:
        raise LLMError(f"Model did not return valid JSON ({e}). Raw start: {raw[:200]!r}") from e


# ── Troubleshooting (lab summary table) ──────────────────────────────────
TROUBLESHOOTING = [
    (("401", "AuthenticationError", "API key not valid", "API_KEY_INVALID", "is not set"),
     "Key missing or mistyped.",
     "Check that the key is in `.env` (not `.env.txt`), next to `app.py`, then restart the app."),
    (("402", "insufficient", "credit balance"),
     "No prepaid credit on this account.",
     "Add credit on the provider's billing page, or switch provider in the sidebar."),
    (("404", "NotFound", "not found", "does not exist"),
     "Model name retired or misspelled.",
     "Update the model name in the sidebar (or in `.env`)."),
    (("429", "RateLimit", "RESOURCE_EXHAUSTED"),
     "Too many requests. This is common on Gemini's free tier.",
     "Wait a minute and run again; identical requests are served from cache."),
    (("not installed", "ModuleNotFoundError"),
     "The provider's package isn't installed in this environment.",
     "Run `pip install -r requirements.txt`, then restart the app."),
]


def diagnose(message: str) -> tuple[str, str] | None:
    """Map an error message to (likely cause, fix) from the lab's troubleshooting table."""
    for markers, cause, fix in TROUBLESHOOTING:
        if any(m.lower() in message.lower() for m in markers):
            return cause, fix
    return None


# ── Prompts ──────────────────────────────────────────────────────────────
def portfolio_system(allow_mixed: bool = False) -> str:
    labels = "Positive, Negative, Neutral or Mixed" if allow_mixed else "Positive, Negative or Neutral"
    options = "Positive|Negative|Neutral|Mixed" if allow_mixed else "Positive|Negative|Neutral"
    mixed_rule = ("\nUse Mixed only when the headline clearly contains both good and bad news "
                  "for shareholders.") if allow_mixed else ""
    return f"""You are a financial news classifier for a portfolio risk dashboard.
For each numbered headline, assign exactly one sentiment label ({labels})
from the perspective of the named company's shareholders, and a 0-1 confidence.{mixed_rule}

Return JSON:
{{"results": [{{"index": 0, "sentiment": "{options}", "confidence": 0.0, "reasoning": "short phrase"}}]}}
Return one result per headline, in the same order."""


PORTFOLIO_SYSTEM = portfolio_system(False)

EARNINGS_SYSTEM = """You are a sell-side analyst. Produce a concise, decision-useful summary of an
earnings call transcript for portfolio managers. Use only facts stated in the transcript;
write "Not stated" when a figure is missing. Never invent numbers.

Return JSON with keys:
company, quarter, revenue, eps, guidance (all strings), highlights (list of strings),
risks (list of strings), outlook (string), tone ("Positive|Mixed|Negative")."""

ADVERSE_MEDIA_SYSTEM = """You are a compliance analyst screening news for a financial institution.
For each numbered snippet, decide whether it contains an adverse-media red flag relevant to
AML/CTF or financial crime: fraud, bribery/corruption, sanctions, money laundering,
terrorist financing, tax evasion, or regulatory enforcement. Allegations count, but say so.
Ordinary business news (expansion, earnings, hiring) is NOT a flag.

Return JSON:
{"results": [{"index": 0, "flag": true,
  "category": "fraud|bribery_corruption|sanctions|money_laundering|terrorist_financing|tax_evasion|regulatory_enforcement|none",
  "confidence": "low|medium|high", "reasoning": "one sentence"}]}
Return one result per snippet, in the same order."""

RED_FLAG_SYSTEM = """You are a compliance analyst writing an educational counterparty risk note.
You receive JSON with: selected_flags, context, and rule_based_score (a transparent weighted
score already computed by the system, with its band).

Write a 3-4 sentence narrative explaining the risk, list the key drivers, and give your own
rating. If you disagree with the rule-based band, explain why in "divergence_note";
otherwise set it to "".

Return JSON:
{"risk_rating": "Low|Medium|High", "narrative": "...", "key_drivers": ["..."],
 "recommended_next_steps": ["..."], "divergence_note": ""}"""


# ── User-message builders (shown in the app's "Messages sent" panel) ─────
def headlines_prompt(headlines: list[str], tickers: list[str]) -> str:
    numbered = "\n".join(f"{i}. [{t}] {h}" for i, (t, h) in enumerate(zip(tickers, headlines)))
    return f"Classify these headlines:\n\n{numbered}"


def media_prompt(snippets: list[str]) -> str:
    numbered = "\n".join(f"{i}. {s}" for i, s in enumerate(snippets))
    return f"Screen these snippets:\n\n{numbered}"


def earnings_prompt(transcript: str) -> str:
    return f"Summarise this earnings call transcript:\n\n{transcript.strip()}"


def flags_prompt(flags: list[str], context: str, rule_score: dict) -> str:
    payload = {"selected_flags": flags, "context": context, "rule_based_score": rule_score}
    return "Assess this counterparty:\n\n" + json.dumps(payload, ensure_ascii=False, indent=2)


# ── Helpers ──────────────────────────────────────────────────────────────
def _results_list(data: Any) -> list[dict]:
    if isinstance(data, dict):
        data = data.get("results", [])
    if not isinstance(data, list):
        raise LLMError("Unexpected JSON shape: expected a 'results' list.")
    return [r for r in data if isinstance(r, dict)]


def _align(items: list[str], results: list[dict]) -> list[dict]:
    """Map model results back to inputs by index so a dropped row can't shift labels."""
    by_index = {}
    for r in results:
        try:
            by_index[int(r.get("index"))] = r
        except (TypeError, ValueError):
            continue
    return [by_index.get(i, {}) for i in range(len(items))]


def _check_batch(items: list[str], label: str) -> None:
    if len(items) > MAX_BATCH:
        raise LLMError(f"Too many {label} ({len(items)}). Limit is {MAX_BATCH} per run.")


# ── Workflows ────────────────────────────────────────────────────────────
_SENTIMENTS = {"positive": "Positive", "negative": "Negative", "neutral": "Neutral", "mixed": "Mixed"}


def classify_headlines(
    headlines: list[str],
    tickers: list[str] | None = None,
    model: str = DEFAULT_MODEL,
    provider: str = DEFAULT_PROVIDER,
    temperature: float = DEFAULT_TEMPERATURE,
    allow_mixed: bool = False,
) -> list[dict]:
    """Classify a batch of headlines in one call. Returns one row per input headline."""
    if not headlines:
        return []
    _check_batch(headlines, "headlines")
    tickers = tickers or ["GENERAL"] * len(headlines)
    data = ask_llm_json(headlines_prompt(headlines, tickers), portfolio_system(allow_mixed),
                        model, provider, temperature)
    allowed = set(_SENTIMENTS.values()) if allow_mixed else {"Positive", "Negative", "Neutral"}
    rows = []
    for i, r in enumerate(_align(headlines, _results_list(data))):
        sentiment = _SENTIMENTS.get(str(r.get("sentiment", "")).strip().lower(), "Unclassified")
        rows.append({
            "ticker": tickers[i],
            "headline": headlines[i],
            "sentiment": sentiment if sentiment in allowed else "Unclassified",
            "confidence": r.get("confidence"),
            "reasoning": r.get("reasoning", ""),
        })
    return rows


def screen_adverse_media(snippets: list[str], model: str = DEFAULT_MODEL,
                         provider: str = DEFAULT_PROVIDER,
                         temperature: float = DEFAULT_TEMPERATURE) -> list[dict]:
    """Flag adverse media in a batch of news snippets. Returns one row per snippet."""
    if not snippets:
        return []
    _check_batch(snippets, "snippets")
    data = ask_llm_json(media_prompt(snippets), ADVERSE_MEDIA_SYSTEM, model, provider, temperature)
    rows = []
    for i, r in enumerate(_align(snippets, _results_list(data))):
        rows.append({
            "snippet": snippets[i],
            "flag": bool(r.get("flag", False)),
            "category": r.get("category", "none") if r else "not returned",
            "confidence": r.get("confidence", ""),
            "reasoning": r.get("reasoning", ""),
        })
    return rows


def summarise_earnings(transcript: str, model: str = DEFAULT_MODEL,
                       provider: str = DEFAULT_PROVIDER,
                       temperature: float = DEFAULT_TEMPERATURE) -> dict:
    """Structured summary of an earnings call transcript."""
    transcript = transcript.strip()
    if len(transcript) > MAX_TRANSCRIPT_CHARS:
        raise LLMError(f"Transcript too long ({len(transcript):,} chars). Limit is {MAX_TRANSCRIPT_CHARS:,}.")
    data = ask_llm_json(earnings_prompt(transcript), EARNINGS_SYSTEM, model, provider, temperature)
    if not isinstance(data, dict):
        raise LLMError("Unexpected JSON shape for earnings summary.")
    for key in ("company", "quarter", "revenue", "eps", "guidance", "outlook", "tone"):
        data[key] = str(data.get(key) or "Not stated")
    for key in ("highlights", "risks"):
        value = data.get(key) or []
        data[key] = [str(v) for v in value] if isinstance(value, list) else [str(value)]
    return data


def assess_red_flags(
    flags: list[str], context: str, rule_score: dict, model: str = DEFAULT_MODEL,
    provider: str = DEFAULT_PROVIDER, temperature: float = DEFAULT_TEMPERATURE,
) -> dict:
    """LLM narrative on top of the deterministic rule-based score (see risk.py)."""
    data = ask_llm_json(flags_prompt(flags, context, rule_score), RED_FLAG_SYSTEM, model, provider, temperature)
    if not isinstance(data, dict):
        raise LLMError("Unexpected JSON shape for risk assessment.")
    rating = str(data.get("risk_rating", "")).strip().capitalize()
    data["risk_rating"] = rating if rating in {"Low", "Medium", "High"} else "Unrated"
    return data
