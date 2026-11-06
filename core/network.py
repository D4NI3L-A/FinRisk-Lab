"""Counterparty network analysis with NetworkX.

Who sits *between* everyone else matters in financial crime: nominees,
intermediaries and shell companies are often the brokers of a scheme. This
module builds the graph, scores each entity, and measures how central it is.
"""
from __future__ import annotations

import math

import networkx as nx
import pandas as pd

RISK_POINTS = {"sanctioned": 50, "pep": 30, "secrecy_jurisdiction": 20, "adverse_media": 20, "shell": 20}
FLAG_LABELS = {
    "sanctioned": "Sanctioned",
    "pep": "Politically exposed person",
    "secrecy_jurisdiction": "Secrecy jurisdiction",
    "adverse_media": "Adverse media",
    "shell": "Shell-company indicators",
}
RELATION_COLORS = {"owns": "#2A5BD7", "director": "#7C8AA5", "payment": "#D98E04", "contract": "#0F9D6B"}
TYPE_SYMBOLS = {"Company": "circle", "Shell company": "diamond", "Person": "circle-open-dot",
                "Bank": "square", "Public body": "triangle-up", "Entity": "circle"}


def build_graph(nodes: pd.DataFrame | None, edges: pd.DataFrame) -> nx.Graph:
    """Undirected graph; parallel links between the same pair are merged and their amounts summed."""
    g = nx.Graph()
    if nodes is not None:
        for row in nodes.to_dict("records"):
            flags = row.get("flags") or []
            if isinstance(flags, str):
                flags = [f.strip() for f in flags.split(";") if f.strip()]
            g.add_node(row["id"], type=row.get("type", "Entity"), jurisdiction=row.get("jurisdiction", ""),
                       flags=list(flags))
    for row in edges.to_dict("records"):
        s, t = str(row["source"]).strip(), str(row["target"]).strip()
        for n in (s, t):
            if n not in g:
                g.add_node(n, type="Entity", jurisdiction="", flags=[])
        amount = float(row.get("amount") or 0)
        rel = str(row.get("relation", "link")).strip().lower()
        if g.has_edge(s, t):
            g[s][t]["amount"] += amount
            g[s][t]["relations"].add(rel)
        else:
            g.add_edge(s, t, amount=amount, relations={rel})
    return g


def own_risk(flags: list[str]) -> int:
    return min(100, sum(RISK_POINTS.get(f, 0) for f in flags))


def entity_metrics(g: nx.Graph) -> pd.DataFrame:
    """Per-entity table: own risk, exposure through neighbours, degree and betweenness."""
    if g.number_of_nodes() == 0:
        return pd.DataFrame(columns=["entity", "type", "jurisdiction", "own_risk", "exposure", "risk",
                                     "connections", "betweenness", "flags"])
    btw = nx.betweenness_centrality(g, normalized=True)
    rows = []
    for n, d in g.nodes(data=True):
        own = own_risk(d.get("flags", []))
        neighbour = max((own_risk(g.nodes[m].get("flags", [])) for m in g.neighbors(n)), default=0)
        exposure = round(0.5 * neighbour)  # half of the riskiest direct counterparty's score
        rows.append({
            "entity": n, "type": d.get("type", "Entity"), "jurisdiction": d.get("jurisdiction", ""),
            "own_risk": own, "exposure": exposure, "risk": min(100, own + exposure),
            "connections": g.degree(n), "betweenness": round(btw[n], 3),
            "flags": ", ".join(FLAG_LABELS.get(f, f) for f in d.get("flags", [])),
        })
    df = pd.DataFrame(rows)
    df["broker_pct"] = (df["betweenness"].rank(pct=True) * 100).round(0)
    return df.sort_values(["risk", "betweenness"], ascending=False).reset_index(drop=True)


def filter_graph(g: nx.Graph, relations: list[str], min_amount: float = 0) -> nx.Graph:
    keep = [(u, v) for u, v, d in g.edges(data=True)
            if d["relations"] & set(relations) and (d["amount"] >= min_amount or "payment" not in d["relations"])]
    h = g.edge_subgraph(keep).copy()
    return h


def path_between(g: nx.Graph, a: str, b: str) -> list[str]:
    try:
        return nx.shortest_path(g, a, b)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return []


def layout(g: nx.Graph, seed: int = 7) -> dict:
    k = 1.6 / math.sqrt(max(g.number_of_nodes(), 1))
    return nx.spring_layout(g, seed=seed, k=k, iterations=200)


def figure(g: nx.Graph, metrics: pd.DataFrame, pos: dict, selected: str | None = None,
           path: list[str] | None = None):
    """Plotly network: size = betweenness (brokers look big), colour = risk, shape = entity type."""
    import plotly.graph_objects as go

    path_edges = set(zip(path or [], (path or [])[1:])) | set(zip((path or [])[1:], path or []))
    fig = go.Figure()

    # One edge trace per relation type, so the legend explains the colours
    for rel, color in RELATION_COLORS.items():
        xs, ys = [], []
        for u, v, d in g.edges(data=True):
            if rel in d["relations"] and (u, v) not in path_edges:
                xs += [pos[u][0], pos[v][0], None]
                ys += [pos[u][1], pos[v][1], None]
        if xs:
            fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(width=1.4, color=color),
                                     hoverinfo="skip", name=rel.capitalize(), opacity=0.55))
    if path_edges:
        xs, ys = [], []
        for u, v in zip(path, path[1:]):
            xs += [pos[u][0], pos[v][0], None]
            ys += [pos[u][1], pos[v][1], None]
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(width=4, color="#E04848"),
                                 hoverinfo="skip", name="Path"))

    m = metrics.set_index("entity")
    nodes = list(g.nodes())
    bmax = max(m.loc[nodes, "betweenness"].max(), 1e-9)
    top = set(m.loc[nodes].sort_values("betweenness", ascending=False).head(6).index) | {selected} | set(path or [])
    fig.add_trace(go.Scatter(
        x=[pos[n][0] for n in nodes], y=[pos[n][1] for n in nodes],
        mode="markers+text",
        text=[n if n in top else "" for n in nodes],
        textposition="top center", textfont=dict(size=11, color="#0E1B33"),
        customdata=nodes,
        marker=dict(
            size=[14 + 34 * m.at[n, "betweenness"] / bmax for n in nodes],
            color=[m.at[n, "risk"] for n in nodes],
            colorscale=[[0, "#0F9D6B"], [0.45, "#F2C14E"], [1, "#E04848"]], cmin=0, cmax=100,
            symbol=[TYPE_SYMBOLS.get(g.nodes[n].get("type", "Entity"), "circle") for n in nodes],
            line=dict(width=[4 if n == selected else 1 for n in nodes],
                      color=["#0E1B33" if n == selected else "#FFFFFF" for n in nodes]),
            colorbar=dict(title=dict(text="Risk"), thickness=10, len=0.6, x=1.0),
        ),
        hovertemplate=[
            f"<b>{n}</b><br>{g.nodes[n].get('type', 'Entity')} · {g.nodes[n].get('jurisdiction', '') or 'n/a'}"
            f"<br>Risk {m.at[n, 'risk']}/100 · broker score {m.at[n, 'broker_pct']:.0f}th pct"
            f"<br>{m.at[n, 'connections']} connections<extra></extra>"
            for n in nodes
        ],
        name="Entities", showlegend=False,
    ))
    fig.update_layout(
        height=560, margin=dict(l=0, r=0, t=10, b=0), dragmode="pan", clickmode="event+select",
        xaxis=dict(visible=False), yaxis=dict(visible=False, scaleanchor="x"),
        legend=dict(orientation="h", y=1.02, x=0, title=None),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig
