"""Task 6 measures on the city sweep (C): queues, spillback, onset density, betweenness.

Pure functions on tables that congestion.py already reads; no SUMO process. The flow,
speed, halting share and cluster columns (G1, G2) already come from
measurements.city_summary; this module adds what the sweep does not report.

queue (per edge e and interval t, from edgeData)
    halted_e(t)  = waitingTime_e(t) / P: time-mean number of halting cars (speed < 0.1 m/s)
                   on e over the interval of length P (waitingTime sums the halting seconds
                   of all cars on the edge).
    queue_m_e(t) = halted_e(t) x (veh length + minGap) / lanes_e: the cycle-mean standing
                   queue, metres per lane, at jam spacing.
    queue_ratio  = queue_m / edge length. A cycle mean: the queue at the end of red is
                   longer (SUMO's aggregated queue-output gives that maximum; see
                   read_queue_output).
spillback       congestion.spillback (T3-D8): congested (T3-D1) and occupancy >= 0.8 x
                occ_jam for 2 consecutive intervals, occ_jam = l / (l + minGap).
onset density   congestion.onset_density (T3-D3): lowest swept density at which the edge's
                seed-mean congested share of the measured intervals exceeds a threshold.
betweenness     junction graph: SUMO edges as arcs between junctions, weight = free-flow
                travel time length / speed limit; turn graph: SUMO edges as nodes, lane
                connections as arcs (turn restrictions kept), arc weight = travel time of
                the edge left.
"""
import gzip
import xml.etree.ElementTree as ET

import networkx as nx
import numpy as np
import pandas as pd
from scipy import stats

from traffic_project import congestion as cg


# ---------------------------------------------------------------- queues and spillback

def queue_table(df, edges, period_s, veh_length_m, min_gap_m):
    """edgeData long table -> wide tables (interval x edge, columns = edges.index):
    halted (cars), queue_m (m per lane), queue_ratio (no unit). Missing edge rows count 0."""
    wait = cg.wide(df, "waitingTime", edges).fillna(0.0)
    halted = wait / float(period_s)
    queue_m = halted * (veh_length_m + min_gap_m) / edges.lanes.to_numpy(dtype=float)
    ratio = queue_m / edges.length.to_numpy(dtype=float)
    return halted, queue_m, ratio


def rises(state01):
    """Number of 0 -> 1 transitions per row of a 0/1 table, counting a 1 in the first row
    as a rise (as measurements.city_summary counts spillback events)."""
    x = np.asarray(state01, dtype=np.int8)
    prev = np.vstack([np.zeros((1, x.shape[1]), dtype=np.int8), x[:-1]])
    return ((x == 1) & (prev == 0)).sum(axis=1)


def run_measures(run, state, edges, warmup_s, period_s, n_vehicles, m):
    """Per-run queue, spillback and flow cross-checks over intervals beginning >= warmup_s.

    run    edgeData long table at the criterion period; state: 0/1 table from congestion.analyse
    m      the config's [measure] table (veh_length_m, min_gap_m, spillback_occ_frac, persist_m)
    Returns (summary dict, per-edge DataFrame: congested share, spillback share,
    mean queue ratio over the window, spillback 0/1 table over the whole run)."""
    lane_len = cg.edge_weights(edges, "lane_length")
    halted, queue_m, ratio = queue_table(run, edges, period_s, m["veh_length_m"], m["min_gap_m"])
    occ_jam = m["veh_length_m"] / (m["veh_length_m"] + m["min_gap_m"])
    spill = cg.spillback(state, cg.wide(run, "occupancy", edges), occ_jam,
                         m["spillback_occ_frac"], m["persist_m"])
    keep = state.index >= warmup_s
    win = state.index[keep]
    h, q, r = (t.reindex(win).fillna(0.0).to_numpy() for t in (halted, queue_m, ratio))
    sp, st = spill.to_numpy()[keep], state.to_numpy()[keep]
    n_int = len(win)
    hours = n_int * period_s / 3600
    w = run[run.begin >= warmup_s]
    vkt_m = float((w.sampledSeconds * w.speed.fillna(0.0)).sum())   # vehicle-metres on normal edges
    summary = dict(
        n_intervals=n_int,
        halted_veh=float(h.sum(axis=1).mean()),
        halted_share=float(h.sum(axis=1).mean() / n_vehicles),
        queued_lane_share=float((h.sum(axis=1) * (m["veh_length_m"] + m["min_gap_m"])).mean()
                                / lane_len.sum()),
        queue_m_mean=float(q.mean()),
        queue_m_p95=float(np.percentile(q, 95)),
        queue_ratio_p95=float(np.percentile(r, 95)),
        spill_edge_share=float(sp.mean()),
        spill_len_share=float((sp * lane_len).sum(axis=1).mean() / lane_len.sum()),
        spill_events=int(rises(spill.to_numpy())[keep].sum()),
        spill_events_per_h=float(rises(spill.to_numpy())[keep].sum() / hours),
        spill_edges_ever=int(sp.any(axis=0).sum()),
        spill_given_congested=float(sp.sum() / st.sum()) if st.sum() else np.nan,
        edgedata_flow_veh_h=vkt_m / (lane_len.sum() * n_int * period_s) * 3600,
    )
    per_edge = pd.DataFrame(dict(congested_share=st.mean(axis=0), spill_share=sp.mean(axis=0),
                                 queue_ratio_mean=r.mean(axis=0)), index=edges.index)
    return summary, per_edge, spill


def read_queue_output(path):
    """SUMO aggregated queue-output (queue-output.aggregation) -> long table: begin, end,
    edge, samples, max_veh, max_m, median_m, pct_m (the configured percentile)."""
    cols = (("samples", "samples"), ("max_veh", "maxQueueLengthInVehicles"),
            ("max_m", "maxQueueLengthInMeters"), ("median_m", "medianQueueLengthInMeters"),
            ("pct_m", "percentileQueueLengthInMeters"))
    rows = []
    p = str(path)
    with (gzip.open(p, "rb") if p.endswith(".gz") else open(p, "rb")) as f:
        for _, el in ET.iterparse(f):
            if el.tag == "interval":
                b, e = float(el.get("begin")), float(el.get("end"))
                for ed in el:
                    rows.append((b, e, ed.get("id"), *(float(ed.get(a, "nan")) for _, a in cols)))
                el.clear()
    return pd.DataFrame(rows, columns=("begin", "end", "edge") + tuple(c for c, _ in cols))


def queue_output_measures(q, state, spill, edges, warmup_s, spacing_m):
    """Per-run measures from SUMO's aggregated queue-output (proposed for the reruns).

    q        read_queue_output table (junction-internal ids ':...' are dropped)
    full     an edge-cycle whose maximum queue reaches within one car spacing (spacing_m =
             veh length + minGap) of the edge's upstream end: max_m >= length - spacing_m
             and max_veh >= 1. queue-output counts cars slower than its speed threshold
             (SUMO default 1.39 m/s) from the lane end to the back of the last such car.
    Returns a dict: qo_queue_share (edge-cycles with any queue), qo_full_share,
    qo_full_also_spill (share of full edge-cycles that are T3-D8 spillback),
    qo_spill_also_full (share of T3-D8 spillback edge-cycles that are full), qo_max_m_mean."""
    keep = state.index >= warmup_s
    win = state.index[keep]
    qn = q[q.edge.isin(edges.index)]
    mx = qn.pivot(index="begin", columns="edge", values="max_m").reindex(index=win, columns=edges.index)
    nv = qn.pivot(index="begin", columns="edge", values="max_veh").reindex(index=win, columns=edges.index)
    mx, nv = mx.fillna(0.0).to_numpy(), nv.fillna(0.0).to_numpy()
    full = (mx >= edges.length.to_numpy() - spacing_m) & (nv >= 1)
    sp = spill.to_numpy()[keep].astype(bool)
    return dict(qo_queue_share=float((nv >= 1).mean()), qo_full_share=float(full.mean()),
                qo_full_also_spill=float(sp[full].mean()) if full.any() else np.nan,
                qo_spill_also_full=float(full[sp].mean()) if sp.any() else np.nan,
                qo_max_m_mean=float(mx.mean()))


# ---------------------------------------------------------------- betweenness and onset

def free_flow_time(edges):
    """Free-flow travel time per edge (s) = length / speed limit (the cars' desired speed:
    speedFactor = 1, speedDev = 0, maxSpeed above every limit)."""
    return edges.length / edges.limit


def junction_betweenness(net):
    """Normalised edge betweenness of every SUMO edge on the directed junction graph
    (parallel edges kept as separate arcs), weight = free-flow travel time."""
    tt = free_flow_time(net.edges)
    g = nx.MultiDiGraph()
    for e, row in net.edges.iterrows():
        g.add_edge(row.frm, row.to, key=e, tt=float(tt[e]))
    b = nx.edge_betweenness_centrality(g, weight="tt", normalized=True)
    return pd.Series({k: v for (_, _, k), v in b.items()}).reindex(net.edges.index).fillna(0.0)


def turn_betweenness(net):
    """Normalised node betweenness on the turn graph (SUMO edges as nodes, every lane
    connection between normal edges as an arc, weight = free-flow time of the edge left)."""
    tt = free_flow_time(net.edges)
    g = nx.DiGraph()
    g.add_nodes_from(net.edges.index)
    g.add_weighted_edges_from(((a, b, float(tt[a])) for a, b in net.connections
                               if a in tt.index and b in tt.index), weight="tt")
    b = nx.betweenness_centrality(g, weight="tt", normalized=True)
    return pd.Series(b).reindex(net.edges.index).fillna(0.0)


def congested_shares(per_run):
    """Seed-mean congested share per density and edge.

    per_run  dict {(density, seed): Series indexed by edge (share of measured intervals
             congested)}. Returns DataFrame index = density, columns = edges."""
    df = pd.DataFrame({k: v for k, v in per_run.items()}).T
    df.index = pd.MultiIndex.from_tuples(df.index, names=("density", "seed"))
    return df.groupby(level="density").mean().sort_index()


def onset_correlation(btw, onset, censor_at):
    """Spearman rank correlation between betweenness and onset density.

    onset NaN = never past the threshold in the sweep (right-censored). Returns a dict:
    rho/p on edges with an onset only, and rho/p and Kendall tau-b with censored edges
    set to `censor_at` (above every swept density, so they tie for the highest rank)."""
    b, o = btw.reindex(onset.index), onset
    has = o.notna()
    out = dict(n_edges=int(len(o)), n_onset=int(has.sum()), n_censored=int((~has).sum()))
    if has.sum() > 2:
        r = stats.spearmanr(b[has], o[has])
        out.update(rho_onset_only=float(r.statistic), p_onset_only=float(r.pvalue))
    filled = o.fillna(censor_at)
    r = stats.spearmanr(b, filled)
    t = stats.kendalltau(b, filled)
    out.update(rho_censored=float(r.statistic), p_censored=float(r.pvalue),
               tau_censored=float(t.statistic), p_tau_censored=float(t.pvalue))
    return out
