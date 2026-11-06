"""Network: map counterparties, find the brokers, trace the money."""
from __future__ import annotations

import html
import io

import pandas as pd
import streamlit as st

import samples
from core import network as net
from theme import BAND_KIND, chip, page_header

page_header("Network", "Map who is connected to whom. Bigger dots sit between more of the network "
                       "(brokers); redder dots carry more risk. Click any dot to inspect it.")

# ── Data source ───────────────────────────────────────────────────────────
with st.container(border=True):
    s1, s2, s3 = st.columns([2, 3, 2], vertical_alignment="bottom")
    source = s1.segmented_control("Data", ["Demo case", "Upload CSV"], default="Demo case", key="net_src") or "Demo case"
    upload = None
    if source == "Upload CSV":
        upload = s2.file_uploader("Edges CSV: source, target, relation, amount", type="csv",
                                  label_visibility="collapsed")
    else:
        s2.caption("A fictional public-contract case: a construction firm, shell companies, nominee directors, "
                   "a politically exposed official and a sanctioned shipper.")
    s3.download_button("CSV template", samples.NETWORK_CSV, "network_template.csv", "text/csv",
                       icon=":material/download:", width="stretch",
                       help="The demo edges in the format the uploader expects. Relation: owns, director, "
                            "payment or contract.")

if source == "Upload CSV" and upload is None:
    st.markdown('<p class="empty">Upload a CSV with columns <b>source, target, relation, amount</b>. '
                "Download the template to see the format.</p>", unsafe_allow_html=True)
    st.stop()

if upload is not None:
    try:
        edges = pd.read_csv(io.BytesIO(upload.getvalue()))
        edges.columns = [c.strip().lower() for c in edges.columns]
        missing = {"source", "target"} - set(edges.columns)
        if missing:
            st.error(f"The CSV is missing these columns: {', '.join(sorted(missing))}.")
            st.stop()
        edges["relation"] = edges.get("relation", "payment")
        edges["amount"] = pd.to_numeric(edges.get("amount", 0), errors="coerce").fillna(0)
        nodes = None
    except Exception as e:  # noqa: BLE001
        st.error(f"Couldn't read that file: {e}")
        st.stop()
else:
    edges = pd.DataFrame(samples.NETWORK_EDGES, columns=["source", "target", "relation", "amount"])
    nodes = pd.DataFrame(samples.NETWORK_NODES)

full = net.build_graph(nodes, edges)

# ── Filters ───────────────────────────────────────────────────────────────
f1, f2, f3 = st.columns([3, 2, 3], vertical_alignment="bottom")
relations = f1.pills("Show links", list(net.RELATION_COLORS), selection_mode="multi",
                     default=list(net.RELATION_COLORS), format_func=str.capitalize, key="net_rel")
max_amt = max([d["amount"] for *_, d in full.edges(data=True)] + [1])
min_amount = f2.slider("Smallest payment shown (€k)", 0, int(max_amt // 1000), 0, step=50,
                       help="Hide small payments to see where the big money moves.") * 1000
g = net.filter_graph(full, relations or [], min_amount)
metrics = net.entity_metrics(full)  # scores use the full network, filters only change the view
entities = sorted(full.nodes())
trace = f3.multiselect("Trace a path between two entities", entities, max_selections=2, key="net_path",
                       placeholder="Pick two entities")

if g.number_of_nodes() == 0:
    st.markdown('<p class="empty">No links match these filters. Turn a link type back on or lower the '
                "payment threshold.</p>", unsafe_allow_html=True)
    st.stop()

path = net.path_between(g, trace[0], trace[1]) if len(trace) == 2 else []
selected = st.session_state.get("net_selected")
if selected not in g:
    selected = None
pos = net.layout(full)

# ── Graph + details panel ─────────────────────────────────────────────────
left, right = st.columns([7, 4], gap="large")
with left:
    fig = net.figure(g, metrics, pos, selected=selected, path=path)
    event = st.plotly_chart(fig, key="net_chart", on_select="rerun", selection_mode="points",
                            config={"displaylogo": False, "scrollZoom": True})
    points = (event or {}).get("selection", {}).get("points", []) if event else []
    node_curve = len(fig.data) - 1
    # Only the entity dots carry customdata (the entity name); edge lines don't
    clicked = next((p.get("customdata") for p in points if p.get("customdata")), None)
    if clicked is None:
        clicked = next((list(g.nodes())[p["point_index"]] for p in points
                        if p.get("curve_number") == node_curve and "point_index" in p), None)
    if isinstance(clicked, list):
        clicked = clicked[0]
    # Only react to a new click, so the View buttons and the selectbox can change the selection too
    if clicked and clicked != st.session_state.get("net_last_click"):
        st.session_state["net_last_click"] = clicked
        if clicked != selected:
            st.session_state["net_selected"] = clicked
            st.rerun()
    if len(trace) == 2:
        if path:
            st.markdown("**Path:** " + " → ".join(html.escape(p) for p in path) + f" ({len(path) - 1} steps)",
                        unsafe_allow_html=True)
        else:
            st.warning("No path between these two with the current filters.")

with right:
    pick = st.selectbox("Inspect an entity", entities, index=entities.index(selected) if selected else None,
                        placeholder="Click a dot or choose here", key=f"net_pick_{selected}")
    if pick and pick != selected:
        st.session_state["net_selected"] = pick
        st.rerun()
    if not selected:
        st.markdown('<p class="empty">Click any dot in the graph to see its risk, its role in the network '
                    "and who it is connected to.</p>", unsafe_allow_html=True)
    else:
        row = metrics.set_index("entity").loc[selected]
        band = "High" if row["risk"] >= 60 else "Medium" if row["risk"] >= 35 else "Low"
        with st.container(border=True):
            st.markdown(f"#### {html.escape(selected)}")
            tags = [chip(row["type"], "primary")] + ([chip(row["jurisdiction"], "muted")] if row["jurisdiction"] else [])
            tags += [chip(f, "risk") for f in row["flags"].split(", ") if f]
            st.markdown(f'<div class="chips">{"".join(tags)}</div>', unsafe_allow_html=True)
            m1, m2 = st.columns(2)
            m1.metric("Risk", f"{row['risk']:.0f}%", border=True,
                      help="Own flags plus half the score of its riskiest direct counterparty.")
            m2.metric("Broker score", f"{row['broker_pct']:.0f}th pct", border=True,
                      help="Betweenness centrality, ranked: how often it sits on the shortest path between others.")
            st.markdown(f'{chip(band + " risk", BAND_KIND[band])} &nbsp; own flags {row["own_risk"]:.0f}% · '
                        f'exposure {row["exposure"]:.0f}% · {row["connections"]} connections',
                        unsafe_allow_html=True)
        st.markdown("##### Connections")
        for nb in sorted(full.neighbors(selected), key=lambda n: -metrics.set_index("entity").at[n, "risk"]):
            d = full[selected][nb]
            amount = f" · €{d['amount'] / 1e6:.1f}m" if d["amount"] else ""
            r = metrics.set_index("entity").at[nb, "risk"]
            c1, c2 = st.columns([4, 1], vertical_alignment="center")
            c1.markdown(f"**{html.escape(nb)}**  \n<span class='news-meta'>{', '.join(sorted(d['relations']))}"
                        f"{amount} · risk {r:.0f}%</span>", unsafe_allow_html=True)
            c2.button("View", key=f"nb_{selected}_{nb}", on_click=st.session_state.update,
                      kwargs={"net_selected": nb}, width="stretch")

# ── Ranked table ──────────────────────────────────────────────────────────
st.markdown("#### Entities ranked by risk")
st.dataframe(
    metrics.drop(columns=["own_risk", "exposure"]), hide_index=True, width="stretch",
    column_config={
        "entity": "Entity", "type": "Type", "jurisdiction": "Jurisdiction",
        "risk": st.column_config.ProgressColumn("Risk", min_value=0, max_value=100, format="%d%%"),
        "connections": st.column_config.NumberColumn("Links"),
        "betweenness": st.column_config.NumberColumn("Betweenness", format="%.3f",
                                                     help="Share of shortest paths that pass through this entity."),
        "broker_pct": st.column_config.ProgressColumn("Broker percentile", min_value=0, max_value=100, format="%d"),
        "flags": "Flags",
    },
)
st.download_button("Download entity scores (CSV)", metrics.to_csv(index=False), "network_scores.csv", "text/csv",
                   icon=":material/download:")
st.caption("Risk points: sanctioned 50, politically exposed person 30, secrecy jurisdiction 20, adverse media 20, "
           "shell-company indicators 20 (capped at 100). Illustrative weights, not calibrated.")
