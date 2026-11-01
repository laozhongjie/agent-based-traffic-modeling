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
spillback       congestion.spillback: congested and occupancy >= 0.8 x occ_jam, occ_jam =
                l / (l + minGap), for 2 consecutive intervals. The congested state is itself
                debounced over 2 intervals, so from free flow an edge enters spillback in the
                third slow interval in a row (occupancy high in the second and third), as the
                sweep's city_spillback_events counts it.
onset density   congestion.onset_density: lowest swept density at which the edge's
                seed-mean congested share of the measured intervals exceeds a threshold.
betweenness     junction graph: SUMO edges as arcs between junctions; turn graph: SUMO edges
                as nodes, lane connections as arcs (turn restrictions kept), arc weight =
                travel time of the edge left. Weights are free-flow travel times, length /
                speed limit, or length / vref, the edge's measured near-empty speed (task
                3's design); per_lane divides by the lane count.
reference load  car passages per edge in the 2 veh/km reference run (cars leaving it after
                warm-up); partial correlations remove it, and with it the lane count, since
                per-lane betweenness carries 1/lanes and single-lane edges congest earlier.
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
    n_events = int(cg.rises(spill.to_numpy())[keep].sum())   # counted as city_summary does
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
        spill_events=n_events,
        spill_events_per_h=float(n_events / hours),
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


def queue_output_measures(q, state, spill, edges, warmup_s, spacing_m, period_s):
    """Per-run measures from SUMO's aggregated queue-output (proposed for the reruns).

    q        read_queue_output table (junction-internal ids ':...' are dropped); its intervals
             must be the criterion intervals of `state`: each period_s long and starting at
             one of state's interval starts (ValueError otherwise)
    full     an edge-cycle whose maximum queue reaches within one car spacing (spacing_m =
             veh length + minGap) of the edge's upstream end: max_m >= length - spacing_m
             and max_veh >= 1. queue-output counts cars slower than its speed threshold
             (SUMO default 1.39 m/s) from the lane end to the back of the last such car.
    Returns a dict: qo_queue_share (edge-cycles with any queue), qo_full_share,
    qo_full_also_spill (share of full edge-cycles that are in spillback),
    qo_spill_also_full (share of spillback edge-cycles that are full), qo_max_m_mean."""
    lengths = (q.end - q.begin).unique()
    if len(q) and not np.allclose(lengths, period_s):
        raise ValueError(f"queue-output intervals last {sorted(lengths)} s, the criterion period is {period_s:g} s")
    if not set(q.begin) <= set(state.index):
        raise ValueError("queue-output intervals do not start where the criterion intervals start")
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

def free_flow_time(edges, speed=None):
    """Free-flow travel time per edge (s) = length / speed.

    speed  per-edge Series (m/s), e.g. the measured near-empty speed vref of the reference
           run (task 3's measured weights); default the speed limit (the cars' desired speed:
           speedFactor = 1, speedDev = 0, maxSpeed above every limit)."""
    v = edges.limit if speed is None else speed.reindex(edges.index)
    if v.isna().any() or (v <= 0).any():
        raise ValueError("free_flow_time: every edge needs a speed above 0")
    return edges.length / v


def per_lane(btw, edges):
    """Betweenness divided by the edge's lane count (task 3's design: per lane)."""
    return btw / edges.lanes.reindex(btw.index)


def reference_load(ref, edges, warmup_s):
    """Car passages per edge in the reference run: cars leaving the edge (edgeData `left`),
    summed over intervals beginning at or after warmup_s; edges never left count 0."""
    d = ref[ref.begin >= warmup_s]
    return d.groupby("edge")["left"].sum().reindex(edges.index).fillna(0.0)


def partial_spearman(x, y, z):
    """Spearman partial correlation of x and y given the control(s) z: the Pearson
    correlation of the residuals of rank(x) and rank(y) after a least-squares fit on an
    intercept and the ranks of every control (ties get mean ranks).

    z  shape (n,) for one control or (n, k) for k controls.
    Returns (r, two-sided p from t with n - 2 - k degrees of freedom); r is NaN when either
    residual is constant, p is NaN when there are no degrees of freedom left. Raises
    ValueError on NaN input or mismatched lengths."""
    x, y, z = (np.asarray(v, dtype=float) for v in (x, y, z))
    z = z[:, None] if z.ndim == 1 else z
    n = len(x)
    if len(y) != n or z.shape[0] != n:
        raise ValueError("partial_spearman: x, y and z need the same length")
    if np.isnan(x).any() or np.isnan(y).any() or np.isnan(z).any():
        raise ValueError("partial_spearman: NaN in the input")
    rank = lambda v: pd.Series(v).rank().to_numpy()
    A = np.column_stack([np.ones(n)] + [rank(z[:, j]) for j in range(z.shape[1])])
    ex = rank(x) - A @ np.linalg.lstsq(A, rank(x), rcond=None)[0]
    ey = rank(y) - A @ np.linalg.lstsq(A, rank(y), rcond=None)[0]
    if np.allclose(ex, 0) or np.allclose(ey, 0):
        return np.nan, np.nan
    r = float(np.corrcoef(ex, ey)[0, 1])
    dof = n - 2 - z.shape[1]
    if dof < 1:
        return r, np.nan
    t = r * np.sqrt(dof / max(1e-300, 1 - r * r))
    return r, float(2 * stats.t.sf(abs(t), dof))


def junction_betweenness(net, tt=None):
    """Normalised edge betweenness of every SUMO edge on the directed junction graph
    (parallel edges kept as separate arcs), weight = free-flow travel time `tt` (default
    `free_flow_time(net.edges)`, length over speed limit)."""
    tt = free_flow_time(net.edges) if tt is None else tt
    g = nx.MultiDiGraph()
    for e, row in net.edges.iterrows():
        g.add_edge(row.frm, row.to, key=e, tt=float(tt[e]))
    b = nx.edge_betweenness_centrality(g, weight="tt", normalized=True)
    return pd.Series({k: v for (_, _, k), v in b.items()}).reindex(net.edges.index).fillna(0.0)


def turn_betweenness(net, tt=None):
    """Normalised node betweenness on the turn graph (SUMO edges as nodes, every lane
    connection between normal edges as an arc, weight = free-flow time `tt` of the edge left;
    default length over speed limit)."""
    tt = free_flow_time(net.edges) if tt is None else tt
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


def onset_correlation(btw, onset, censor_at, load=None, lanes=None):
    """Spearman rank correlation between betweenness and onset density.

    onset NaN = never past the threshold in the sweep (right-censored). Returns a dict:
    rho/p on edges with an onset only (NaN with 2 or fewer onsets), and rho/p and Kendall
    tau-b with censored edges set to `censor_at` (above every swept density, so they tie for
    the highest rank). With `load` (per-edge car passages in the reference run) it
    adds rho_btw_load and the partial correlations given the load, partial_onset_only and
    partial_censored (with their p), which ask whether network position predicts onset
    beyond the demand an edge carries. With `lanes` as well it adds the same partials with
    the load and the lane count removed, partial_load_lanes_onset_only and
    partial_load_lanes_censored: per-lane betweenness carries 1/lanes, and lane count
    alone predicts onset at a given load."""
    b, o = btw.reindex(onset.index), onset
    has = o.notna()
    out = dict(n_edges=int(len(o)), n_onset=int(has.sum()), n_censored=int((~has).sum()),
               rho_onset_only=np.nan, p_onset_only=np.nan)
    if has.sum() > 2:
        r = stats.spearmanr(b[has], o[has])
        out.update(rho_onset_only=float(r.statistic), p_onset_only=float(r.pvalue))
    filled = o.fillna(censor_at)
    r = stats.spearmanr(b, filled)
    t = stats.kendalltau(b, filled)
    out.update(rho_censored=float(r.statistic), p_censored=float(r.pvalue),
               tau_censored=float(t.statistic), p_tau_censored=float(t.pvalue))
    if lanes is not None and load is None:
        raise ValueError("onset_correlation: lanes needs load (the lane count is removed with it)")
    if load is not None:
        ld = load.reindex(onset.index)
        if ld.isna().any():
            raise ValueError("onset_correlation: load is missing for some edges")
        out["rho_btw_load"] = float(stats.spearmanr(b, ld).statistic)
        po = partial_spearman(b[has], o[has], ld[has]) if has.sum() > 3 else (np.nan, np.nan)
        pc = partial_spearman(b, filled, ld)
        out.update(partial_onset_only=po[0], p_partial_onset_only=po[1],
                   partial_censored=pc[0], p_partial_censored=pc[1])
        if lanes is not None:
            ln = lanes.reindex(onset.index).astype(float)
            if ln.isna().any():
                raise ValueError("onset_correlation: lanes is missing for some edges")
            zc = np.column_stack([ld, ln])
            po = partial_spearman(b[has], o[has], zc[has.to_numpy()]) if has.sum() > 4 else (np.nan, np.nan)
            pc = partial_spearman(b, filled, zc)
            out.update(partial_load_lanes_onset_only=po[0], p_partial_load_lanes_onset_only=po[1],
                       partial_load_lanes_censored=pc[0], p_partial_load_lanes_censored=pc[1])
    return out
