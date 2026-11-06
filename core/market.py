"""Market data: prices, company profile and news from Yahoo Finance (via yfinance).

Every function falls back to clearly-labelled demo data when the network or
yfinance is unavailable, so the app still works offline and in tests.
"""
from __future__ import annotations

import datetime as dt
import hashlib
from urllib.parse import quote_plus

import numpy as np
import pandas as pd

PERIODS = {"1M": "1mo", "3M": "3mo", "6M": "6mo", "1Y": "1y", "5Y": "5y"}
TRADING_DAYS = 252

# Shown on the home page strip: ticker -> short label
MARKET_STRIP = {
    "^GSPC": "S&P 500",
    "^IXIC": "Nasdaq",
    "^STOXX50E": "Euro Stoxx 50",
    "EURUSD=X": "EUR/USD",
    "GC=F": "Gold",
    "BTC-USD": "Bitcoin",
}

SUGGESTED = ["AAPL", "MSFT", "JPM", "HSBC", "BAC", "XOM", "TSLA", "NVDA"]


# ── Prices ────────────────────────────────────────────────────────────────
def _demo_prices(tickers: list[str], period: str) -> pd.DataFrame:
    """Deterministic random-walk prices per ticker (seeded by name)."""
    days = {"1mo": 22, "3mo": 64, "6mo": 127, "1y": 252, "5y": 1260}.get(period, 252)
    idx = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=days)
    out = {}
    for t in tickers:
        seed = int(hashlib.md5(t.encode()).hexdigest()[:8], 16)
        rng = np.random.default_rng(seed)
        vol = 0.15 + (seed % 30) / 100
        rets = rng.normal(0.08 / TRADING_DAYS, vol / np.sqrt(TRADING_DAYS), days)
        out[t] = (50 + seed % 250) * np.exp(np.cumsum(rets))
    return pd.DataFrame(out, index=idx)


def get_prices(tickers: list[str], period: str = "1y") -> tuple[pd.DataFrame, bool]:
    """Daily closing prices, one column per ticker. Returns (prices, is_demo)."""
    tickers = [t.strip().upper() for t in tickers if t and t.strip()]
    if not tickers:
        return pd.DataFrame(), False
    try:
        import yfinance as yf

        raw = yf.download(tickers, period=period, auto_adjust=True, progress=False, threads=True)
        close = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]]
        if isinstance(close, pd.Series):
            close = close.to_frame()
        if close.shape[1] == 1 and len(tickers) == 1:
            close.columns = tickers
        close = close.dropna(how="all")
        if close.empty:
            raise ValueError("no data returned")
        missing = [t for t in tickers if t not in close.columns or close[t].dropna().empty]
        if missing:  # keep real data for the rest; fill the gaps with demo data
            demo = _demo_prices(missing, period).reindex(close.index, method="nearest")
            close = close.drop(columns=[c for c in missing if c in close.columns]).join(demo)
        return close[tickers], bool(missing)
    except Exception:  # noqa: BLE001  offline, blocked, or ticker unknown
        return _demo_prices(tickers, period), True


def price_metrics(series: pd.Series, benchmark: pd.Series | None = None) -> dict:
    """Return, volatility, drawdown and beta for one price series. Percentages are fractions."""
    s = series.dropna()
    if len(s) < 3:
        return {"last": float("nan"), "day": 0.0, "period": 0.0, "vol": 0.0, "max_dd": 0.0, "beta": None}
    rets = s.pct_change().dropna()
    running_max = s.cummax()
    beta = None
    if benchmark is not None:
        b = benchmark.dropna().pct_change().dropna()
        joined = pd.concat([rets, b], axis=1, join="inner").dropna()
        if len(joined) > 10 and joined.iloc[:, 1].var() > 0:
            beta = float(joined.cov().iloc[0, 1] / joined.iloc[:, 1].var())
    return {
        "last": float(s.iloc[-1]),
        "day": float(s.iloc[-1] / s.iloc[-2] - 1),
        "period": float(s.iloc[-1] / s.iloc[0] - 1),
        "vol": float(rets.std() * np.sqrt(TRADING_DAYS)),
        "max_dd": float((s / running_max - 1).min()),
        "beta": beta,
    }


# ── Profile ───────────────────────────────────────────────────────────────
def get_profile(ticker: str) -> dict:
    """Company name, sector, country, size and description. Missing fields are None."""
    ticker = ticker.upper()
    base = {"ticker": ticker, "name": ticker, "sector": None, "industry": None, "country": None,
            "website": None, "market_cap": None, "employees": None, "summary": None, "demo": True}
    try:
        import yfinance as yf

        info = yf.Ticker(ticker).info or {}
        if not info.get("longName") and not info.get("shortName"):
            return base
        base.update({
            "name": info.get("longName") or info.get("shortName"),
            "sector": info.get("sector"), "industry": info.get("industry"),
            "country": info.get("country"), "website": info.get("website"),
            "market_cap": info.get("marketCap"), "employees": info.get("fullTimeEmployees"),
            "summary": info.get("longBusinessSummary"), "demo": False,
        })
    except Exception:  # noqa: BLE001
        pass
    return base


# ── News ──────────────────────────────────────────────────────────────────
def _parse_news_item(item: dict) -> dict | None:
    """yfinance has used two news formats; accept both."""
    c = item.get("content", item)
    title = c.get("title")
    if not title:
        return None
    link = (c.get("canonicalUrl") or {}).get("url") or (c.get("clickThroughUrl") or {}).get("url") or c.get("link")
    publisher = (c.get("provider") or {}).get("displayName") or c.get("publisher") or ""
    when = c.get("pubDate") or c.get("displayTime")
    if not when and c.get("providerPublishTime"):
        when = dt.datetime.fromtimestamp(c["providerPublishTime"], tz=dt.timezone.utc).isoformat()
    return {"title": title.strip(), "link": link, "publisher": publisher, "published": when}


def get_news(ticker: str, limit: int = 12) -> tuple[list[dict], bool]:
    """Latest headlines for a ticker. Returns (items, is_demo)."""
    try:
        import yfinance as yf

        items = [_parse_news_item(i) for i in (yf.Ticker(ticker).news or [])]
        items = [i for i in items if i][:limit]
        if items:
            return items, False
    except Exception:  # noqa: BLE001
        pass
    return demo_news(ticker), True


def demo_news(ticker: str) -> list[dict]:
    from samples import HEADLINES, SNIPPETS

    lines = [h.split(": ", 1)[-1] for h in HEADLINES.splitlines()] + SNIPPETS.splitlines()
    return [{"title": t, "link": None, "publisher": "Demo data (fictional)", "published": None} for t in lines]


# ── Outbound links used across the investigation flow ─────────────────────
def research_links(ticker: str, name: str | None = None) -> dict[str, str]:
    q = quote_plus(name or ticker)
    return {
        "Yahoo Finance": f"https://finance.yahoo.com/quote/{quote_plus(ticker)}",
        "SEC filings (EDGAR)": f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={quote_plus(ticker)}&type=10-K",
        "OpenSanctions": f"https://www.opensanctions.org/search/?q={q}",
        "OFAC sanctions search": "https://sanctionssearch.ofac.treas.gov/",
        "News search": f"https://news.google.com/search?q={q}",
    }


def human_money(x: float | None) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "n/a"
    for unit, div in (("T", 1e12), ("B", 1e9), ("M", 1e6)):
        if abs(x) >= div:
            return f"${x / div:,.1f}{unit}"
    return f"${x:,.0f}"
