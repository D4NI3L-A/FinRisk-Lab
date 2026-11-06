"""Offline tests for scoring, network and market helpers."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import samples  # noqa: E402
from core import market, network, scoring  # noqa: E402


def demo_graph():
    edges = pd.DataFrame(samples.NETWORK_EDGES, columns=["source", "target", "relation", "amount"])
    return network.build_graph(pd.DataFrame(samples.NETWORK_NODES), edges)


def test_composite_rescales_to_completed_steps():
    full = scoring.composite({"market": 50, "news": 50, "media": 50, "flags": 50})
    part = scoring.composite({"market": 50, "news": None, "media": None, "flags": 50})
    assert full["score"] == part["score"] == 50 and full["completeness"] == 1.0
    assert part["completeness"] == 0.5
    assert scoring.composite({})["score"] is None


def test_sub_scores_are_bounded():
    assert scoring.market_score(5.0, -0.99) == 100
    assert scoring.news_score(["Negative", "Positive", "Mixed", "Unclassified"]) == 50.0
    assert scoring.media_score([{"flag": True, "confidence": "high"}] * 3) == 100
    assert scoring.band(70) == "High" and scoring.band(10) == "Low"


def test_network_brokers_and_exposure():
    g = demo_graph()
    m = network.entity_metrics(g).set_index("entity")
    assert m.at["Volkov Shipping", "own_risk"] == 50
    assert m.at["Ostrava Logistics", "exposure"] == 25  # half of its sanctioned neighbour's score
    assert m["betweenness"].idxmax() in {"Harbourline Trading", "Meridian Metals", "Kestrel Holdings"}
    path = network.path_between(g, "Port Authority of Aldmere", "Volkov Shipping")
    assert path[0] == "Port Authority of Aldmere" and path[-1] == "Volkov Shipping"


def test_filter_keeps_only_selected_relations():
    h = network.filter_graph(demo_graph(), ["payment"], min_amount=1_000_000)
    assert all("payment" in d["relations"] and d["amount"] >= 1_000_000 for *_, d in h.edges(data=True))


def test_news_parser_accepts_both_formats():
    old = {"title": "A", "link": "http://x", "publisher": "P", "providerPublishTime": 0}
    new = {"content": {"title": "B", "canonicalUrl": {"url": "http://y"}, "provider": {"displayName": "Q"}}}
    assert market._parse_news_item(old)["link"] == "http://x"
    assert market._parse_news_item(new)["publisher"] == "Q"
    assert market._parse_news_item({"content": {}}) is None


def test_price_metrics_on_known_series():
    s = pd.Series([100, 110, 99, 120], index=pd.bdate_range("2026-01-01", periods=4))
    m = market.price_metrics(s)
    assert round(m["period"], 2) == 0.20 and round(m["max_dd"], 2) == -0.10


def test_news_rss_parsing_and_query():
    from core import news

    xml = """<rss><channel>
      <item><title>Acme fined over laundering failures - Daily Ledger</title><link>http://a</link>
        <pubDate>Fri, 06 Nov 2026 09:00:00 GMT</pubDate><source url="http://dl">Daily Ledger</source></item>
      <item><title>Acme opens new office</title><link>http://b</link></item>
    </channel></rss>"""
    items = news.parse_rss(xml)
    assert items[0]["title"] == "Acme fined over laundering failures" and items[0]["publisher"] == "Daily Ledger"
    assert items[0]["published"].startswith("2026-11-06")
    assert news.keyword_hits(items[0]["title"]) == ["laundering", "fine"] or "laundering" in news.keyword_hits(items[0]["title"])
    assert news.keyword_hits(items[1]["title"]) == []
    q = news.build_query("Acme Corp", adverse=True, window="7d")
    assert q.startswith('"Acme Corp" (') and "laundering" in q and q.endswith("when:7d")
    assert '<mark class="hit">fined</mark>' in news.highlight("Acme fined")


def test_demo_mode_answers_every_task_without_a_key(monkeypatch):
    import llm
    from risk import score_flags

    for k in llm.KEY_NAMES.values():
        monkeypatch.delenv(k, raising=False)
    assert llm.is_demo("gemini")
    rows = llm.classify_headlines(["Acme beats estimates", "Acme fined by regulator", "Acme holds meeting"],
                                  ["A", "A", "A"])
    assert [r["sentiment"] for r in rows] == ["Positive", "Negative", "Neutral"]
    media = llm.screen_adverse_media(["Bank fined for anti-money laundering failures", "Shop opens in Cork"])
    assert media[0]["flag"] and media[0]["category"] == "money_laundering" and not media[1]["flag"]
    s = llm.summarise_earnings(samples.TRANSCRIPT)
    assert s["company"] == "Clearbrook Bank" and "1.84" in s["revenue"] and "0.92" in s["eps"]
    flags = ["Shell-company indicators", "Opaque or undisclosed beneficial ownership",
             "Politically exposed person (PEP) involved"]
    a = llm.assess_red_flags(flags, "", score_flags(flags))
    assert a["risk_rating"] == "High" and a["narrative"]
