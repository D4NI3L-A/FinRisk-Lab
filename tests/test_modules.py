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
