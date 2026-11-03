"""Network congestion criterion and congested clusters for the city network (C).

Pure functions on SUMO files (net, edgeData, summary); no SUMO process, no TraCI.
Ported from C's Task 3 pilot (sandbox/c/task3/congestion.py, 20 Oct 2026). Every
option is a key of the config's [measure] table; the values in configs/city/ are
provisional until the team rules on T3-D1, T3-D2, T3-D6 and T3-D8.

    net   = read_net(net_path)                         # edges, connections, signal cycles
    P     = cycle_period(net, measure["period_s"])     # "cycle" -> longest signal cycle
    run   = read_edgedata(run_file); ref = read_edgedata(ref_file)
    vref, info = free_flow_reference(ref, net.edges, warmup_s, min_sampled_s=60)
    state = classify(relative_speed(run, vref), r_on=0.5, persist_m=2)
    adj   = edge_adjacency(net, "directed")
    ser   = order_parameters(state, run, net.edges, adj, weight="lane_length")

Definitions (reasons in the Task 3 evidence note, private repo):

relative speed   r_e(t) = v_e(t) / vref_e. v_e(t) is edgeData `speed`, the space-mean
                 speed of edge e over interval t. vref_e is the sampledSeconds-weighted
                 mean speed of e in a low-density run with the same net and signals,
                 so it includes the edge's own red-light delay at zero load.
empty interval   sampledSeconds = 0 (SUMO writes no speed): free, never congested.
state            persist rule: an edge's state flips only after `persist_m`
                 consecutive intervals on the other side of r_on (m = 1 is the raw
                 rule r < r_on). Classification starts at t = 0 in the free state;
                 intervals before the warm-up are dropped afterwards.
clusters         weakly connected components of congested edges. "directed": e1 -> e2
                 when the net has a lane connection e1 -> e2 and e2 is not e1's U-turn;
                 "junction": e1 ~ e2 when they share an end node.
order parameters per interval: phi_len (congested share of lane length), phi_veh
                 (share of vehicle-time on congested edges), G1 and G2 (largest and
                 second-largest cluster as a share of total length), n_clusters.
"""
import gzip
import xml.etree.ElementTree as ET
from collections import namedtuple

import numpy as np
import pandas as pd
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

Net = namedtuple("Net", "edges connections tls_cycles")
EDGEDATA_COLS = ("sampledSeconds", "speed", "occupancy", "waitingTime", "entered", "left",
                 "density")
WEIGHTS = ("lane_length", "road_length")


def _open(path):
    path = str(path)
    return gzip.open(path, "rb") if path.endswith(".gz") else open(path, "rb")


# ---------------------------------------------------------------- network

def read_net(net_path):
    """Read a SUMO .net.xml into Net(edges, connections, tls_cycles).

    edges        DataFrame indexed by edge id (non-internal edges only): frm, to,
                 length (m), lanes, limit (m/s, fastest lane)
    connections  set of (from_edge, to_edge) lane connections between normal edges
    tls_cycles   {tlLogic id: cycle length in s = sum of its phase durations}
    """
    rows, conns, cycles = [], set(), {}
    with _open(net_path) as f:
        for _, el in ET.iterparse(f):
            if el.tag == "edge" and el.get("function") != "internal":
                lanes = el.findall("lane")
                if lanes:
                    rows.append(dict(edge=el.get("id"), frm=el.get("from"), to=el.get("to"),
                                     length=float(lanes[0].get("length")), lanes=len(lanes),
                                     limit=max(float(l.get("speed")) for l in lanes)))
            elif el.tag == "connection" and not el.get("from", "").startswith(":"):
                conns.add((el.get("from"), el.get("to")))
            elif el.tag == "tlLogic":
                cycles[el.get("id")] = sum(float(p.get("duration")) for p in el.iter("phase"))
            if el.tag in ("edge", "junction", "connection", "tlLogic"):
                el.clear()
    return Net(pd.DataFrame(rows).set_index("edge"), conns, cycles)


def cycle_period(net, period_s):
    """Interval length in s. "cycle" -> the longest signal cycle in the net."""
    if period_s == "cycle":
        if not net.tls_cycles:
            raise ValueError("period_s = 'cycle' but the net has no traffic lights")
        return max(net.tls_cycles.values())
    return float(period_s)


def edgedata_additional(period_s, file="edgedata.xml.gz", data_id="congestion"):
    """Text of a SUMO additional file that writes the edgeData this module reads.

    excludeEmpty="false" keeps empty edges (sampledSeconds = 0) in every interval.
    """
    attrs = " ".join(EDGEDATA_COLS)
    return (f'<additional>\n    <edgeData id="{data_id}" period="{period_s:g}" file="{file}" '
            f'excludeEmpty="false" writeAttributes="{attrs}"/>\n</additional>\n')


def edge_adjacency(net, mode="directed"):
    """(i, j) index pairs (into net.edges.index) of adjacent edges; see module doc."""
    edges = net.edges
    idx = {e: i for i, e in enumerate(edges.index)}
    if mode == "directed":
        return [(idx[a], idx[b]) for a, b in net.connections
                if a in idx and b in idx and edges.at[b, "to"] != edges.at[a, "frm"]]
    if mode == "junction":
        by_node = {}
        for e, row in edges.iterrows():
            by_node.setdefault(row.frm, set()).add(idx[e])
            by_node.setdefault(row.to, set()).add(idx[e])
        pairs = set()
        for members in by_node.values():
            m = sorted(members)
            pairs.update((a, b) for k, a in enumerate(m) for b in m[k + 1:])
        return sorted(pairs)
    raise ValueError(f"adjacency must be 'directed' or 'junction', not {mode!r}")


def edge_weights(edges, weight="lane_length"):
    """Length weight per edge (m): length x lanes, or road length."""
    if weight == "lane_length":
        return (edges.length * edges.lanes).to_numpy(dtype=float)
    if weight == "road_length":
        return edges.length.to_numpy(dtype=float)
    raise ValueError(f"weight must be one of {WEIGHTS}, not {weight!r}")


# ---------------------------------------------------------------- edgeData

def read_edgedata(path):
    """edgeData file -> long table: begin, end, edge, sampledSeconds, speed, occupancy (%), ...

    speed and occupancy are NaN when the edge was empty in the interval."""
    rows = []
    with _open(path) as f:
        for _, el in ET.iterparse(f):
            if el.tag == "interval":
                b, e = float(el.get("begin")), float(el.get("end"))
                for ed in el:
                    rows.append((b, e, ed.get("id"),
                                 *(float(ed.get(c)) if ed.get(c) is not None else np.nan
                                   for c in EDGEDATA_COLS)))
                el.clear()
    return pd.DataFrame(rows, columns=("begin", "end", "edge") + EDGEDATA_COLS)


def merge_intervals(df, mult):
    """Merge edgeData intervals into intervals `mult` times longer, paired on absolute
    boundaries (begin // (P * mult)). Speed is sampledSeconds-weighted (SUMO's own rule);
    sampledSeconds, waitingTime, entered and left add up; occupancy and density are
    time means. Incomplete trailing groups are dropped."""
    if mult == 1:
        return df
    P = float((df.end - df.begin).iloc[0])
    long = P * mult
    d = df.copy()
    d["begin"] = np.floor(d.begin / long + 1e-9) * long
    d["sv"] = d.speed.fillna(0) * d.sampledSeconds
    g = d.groupby(["begin", "edge"], sort=True)
    out = g[["sampledSeconds", "sv", "waitingTime", "entered", "left"]].sum()
    out[["occupancy", "density"]] = g[["occupancy", "density"]].sum() / mult
    out["n"] = g.size()
    out = out[out.n == mult].reset_index()
    out["speed"] = np.where(out.sampledSeconds > 0,
                            out.sv / out.sampledSeconds.where(out.sampledSeconds > 0), np.nan)
    out.loc[out.sampledSeconds <= 0, ["occupancy", "density"]] = np.nan
    out["end"] = out.begin + long
    return out[["begin", "end", "edge", *EDGEDATA_COLS]]


def wide(df, column, edges):
    """Wide table interval x edge of one edgeData column, columns in edges.index order."""
    return df.pivot(index="begin", columns="edge", values=column).reindex(columns=edges.index)


# ---------------------------------------------------------------- criterion

def free_flow_reference(df_ref, edges, warmup_s=0.0, min_sampled_s=60.0, fallback="class_median"):
    """Per-edge empirical free-flow speed vref (m/s) from a low-density reference run.

    vref_e = sampledSeconds-weighted mean speed of edge e over intervals beginning at or
    after warmup_s. Edges with less than min_sampled_s sampled seconds in total (and edges
    never visited) get limit x the median vref/limit of the well-sampled edges with the
    same speed limit ("class_median"), or of all well-sampled edges ("network_median";
    also used when a speed class has no well-sampled edge).

    Returns (vref Series indexed like edges, info dict: coverage = share of edges with
    their own vref, n_fallback).
    """
    d = df_ref[(df_ref.begin >= warmup_s) & (df_ref.sampledSeconds > 0)]
    w = d.sampledSeconds
    total = w.groupby(d.edge).sum().reindex(edges.index).fillna(0.0)
    v = ((d.speed * w).groupby(d.edge).sum() / w.groupby(d.edge).sum()).reindex(edges.index)
    own = (total > 0) & (total >= min_sampled_s) & v.notna()
    ratio = v[own] / edges.limit[own]
    if not own.any():
        raise ValueError("reference run: no edge has enough sampled seconds")
    net_med = float(np.median(ratio))
    if fallback == "network_median":
        fill = pd.Series(net_med, index=edges.index)
    elif fallback == "class_median":
        cls = edges.limit.round(2)
        med = ratio.groupby(cls[own]).median()
        fill = cls.map(med).fillna(net_med)
    else:
        raise ValueError(f"vref_fallback must be 'class_median' or 'network_median', not {fallback!r}")
    vref = v.where(own, edges.limit * fill)
    return vref, dict(coverage=float(own.mean()), n_fallback=int((~own).sum()))


def relative_speed(df, vref):
    """Wide table r[t, e] = speed / vref (rows: interval begin; columns: vref.index)."""
    w = df.pivot(index="begin", columns="edge", values="speed")
    return w.reindex(columns=vref.index) / vref.values


def classify(r, r_on=0.5, persist_m=2, rule="persist", r_off=None, window=3):
    """0/1 congested state per interval and edge. Empty intervals (NaN) count as free.

    persist  state flips only after persist_m consecutive intervals on the other side
             of r_on (persist_m = 1 is the raw rule r < r_on)
    hyst     enter when r < r_on, leave when r > r_off (r_off > r_on); comparison only
    rolling  trailing mean of r over `window` intervals (NaN -> 1) below r_on; comparison only
    """
    x = r.to_numpy(dtype=float)
    raw = np.where(np.isnan(x), 0, x < r_on).astype(np.int8)
    if rule == "rolling":
        filled = pd.DataFrame(np.where(np.isnan(x), 1.0, x))
        out = (filled.rolling(window, min_periods=1).mean().to_numpy() < r_on).astype(np.int8)
        return pd.DataFrame(out, index=r.index, columns=r.columns)
    if rule == "persist":
        return pd.DataFrame(persist(raw, persist_m), index=r.index, columns=r.columns)
    if rule != "hyst":
        raise ValueError(f"rule must be 'persist', 'hyst' or 'rolling', not {rule!r}")
    out = np.zeros_like(raw)
    state = np.zeros(raw.shape[1], dtype=np.int8)
    for t in range(raw.shape[0]):
        xt = x[t]
        enter = (~np.isnan(xt)) & (xt < r_on)
        leave = np.isnan(xt) | (xt > r_off)
        state = np.where(state == 0, enter, ~leave).astype(np.int8)
        out[t] = state
    return pd.DataFrame(out, index=r.index, columns=r.columns)


def persist(raw, m):
    """Debounce a 0/1 array (time x edge): flip only after m consecutive opposite values."""
    raw = np.asarray(raw, dtype=np.int8)
    out = np.zeros_like(raw)
    state = np.zeros(raw.shape[1], dtype=np.int8)
    run = np.zeros(raw.shape[1], dtype=int)
    for t in range(raw.shape[0]):
        run = np.where(raw[t] != state, run + 1, 0)
        flip = run >= m
        state = np.where(flip, 1 - state, state).astype(np.int8)
        run = np.where(flip, 0, run)
        out[t] = state
    return out


# ---------------------------------------------------------------- order parameters

def clusters(state, adj, lengths):
    """Cluster sizes (sum of `lengths`), largest first, of the congested edges."""
    state = np.asarray(state)
    on = np.flatnonzero(state)
    if on.size == 0:
        return np.array([])
    pos = -np.ones(len(state), dtype=int)
    pos[on] = np.arange(on.size)
    a = np.array([(pos[i], pos[j]) for i, j in adj if state[i] and state[j]], dtype=int)
    a = a.reshape(-1, 2)
    g = coo_matrix((np.ones(len(a)), (a[:, 0], a[:, 1])), shape=(on.size, on.size))
    n, lab = connected_components(g, directed=True, connection="weak")
    sizes = np.bincount(lab, weights=np.asarray(lengths, dtype=float)[on], minlength=n)
    return np.sort(sizes)[::-1]


def order_parameters(state, edgedata, edges, adj, weight="lane_length"):
    """Per interval (index = begin): phi_len, phi_veh, G1, G2, n_clusters.

    phi_len, G1 and G2 are shares of total length under `weight`; phi_veh is
    sum(sampledSeconds x state) / sum(sampledSeconds), NaN in an interval with no vehicle.
    """
    L = edge_weights(edges, weight)
    tot = L.sum()
    sampled = wide(edgedata, "sampledSeconds", edges).reindex(state.index).fillna(0.0)
    rows = []
    for (t, s), w in zip(zip(state.index, state.to_numpy()), sampled.to_numpy()):
        sz = clusters(s, adj, L)
        rows.append(dict(begin=t, phi_len=(L * s).sum() / tot,
                         phi_veh=(w * s).sum() / w.sum() if w.sum() > 0 else np.nan,
                         G1=sz[0] / tot if sz.size else 0.0,
                         G2=sz[1] / tot if sz.size > 1 else 0.0, n_clusters=sz.size))
    return pd.DataFrame(rows).set_index("begin")


def spillback(state, occupancy_pct, occ_jam, occ_frac=0.8, persist_m=2):
    """Spillback state (time x edge, 0/1): congested and occupancy >= occ_frac x occ_jam,
    debounced with the same persistence. occ_jam = veh length / (veh length + minGap);
    occupancy_pct is edgeData occupancy in % (NaN = empty edge = no spillback)."""
    occ = occupancy_pct.reindex(index=state.index, columns=state.columns).to_numpy() / 100
    raw = state.to_numpy().astype(bool) & (np.nan_to_num(occ, nan=0.0) >= occ_frac * occ_jam)
    return pd.DataFrame(persist(raw.astype(np.int8), persist_m), index=state.index,
                        columns=state.columns)


def onsets(state01):
    """Number of 0 -> 1 transitions in a 0/1 table (time x edge), from the first row."""
    x = np.asarray(state01)
    return int((np.diff(x, axis=0) == 1).sum())


def rises(state01):
    """Where a 0/1 table (time x edge) turns on: a boolean array of the same shape, True
    where a 1 follows a 0. The row before the first counts as 0, so a 1 in the first row
    is a rise. Spillback events are rises of the spillback state (city_summary and
    mfd_measures count them with this function)."""
    x = np.asarray(state01)
    return np.diff(np.vstack([np.zeros((1, x.shape[1])), x]), axis=0) == 1


def gridlock(outflow, free_outflow, frac=0.01, cycles=3):
    """True per interval when outflow (sum of edgeData `left`) has stayed below
    frac x free_outflow for at least `cycles` consecutive intervals ending here."""
    low = (np.asarray(outflow, dtype=float) < frac * free_outflow).astype(int)
    out, run = np.zeros(low.size, dtype=bool), 0
    for i, v in enumerate(low):
        run = run + 1 if v else 0
        out[i] = run >= cycles
    return out


def onset_density(shares, threshold=0.5):
    """Onset density per edge (T3-D3): the lowest density at which the edge is congested
    for more than `threshold` of the measurement window.

    shares  DataFrame, index = density (veh/km), columns = edges, values = share of
            intervals congested (seeds already averaged). NaN where never reached.
    """
    s = shares.sort_index()
    hit = s > threshold
    first = hit.idxmax().where(hit.any())
    return first.astype(float)


# ---------------------------------------------------------------- one analysis

def analyse(run, ref, net, warmup_s, r_on=0.5, persist_m=2, adjacency="directed",
            weight="lane_length", period_mult=1, min_sampled_s=60.0,
            vref_fallback="class_median", adj=None):
    """One criterion variant on one run. `run`, `ref`: edgeData tables at the base period.

    Returns (series, state, vref_info): series per interval with t >= warmup_s, state the
    0/1 table over the whole run (classified from t = 0).
    """
    run, ref = merge_intervals(run, period_mult), merge_intervals(ref, period_mult)
    vref, info = free_flow_reference(ref, net.edges, warmup_s, min_sampled_s, vref_fallback)
    state = classify(relative_speed(run, vref), r_on=r_on, persist_m=persist_m)
    keep = state.index >= warmup_s
    adj = edge_adjacency(net, adjacency) if adj is None else adj
    ser = order_parameters(state[keep], run, net.edges, adj, weight)
    return ser, state, info


def summarise(ser):
    """Time means and population variances (ddof = 0) of the per-interval series."""
    out = dict(n_intervals=len(ser))
    for c in ("phi_len", "phi_veh", "G1", "G2"):
        out[c], out[c + "_var"] = ser[c].mean(), ser[c].var(ddof=0)
    out["n_clusters"] = ser.n_clusters.mean()
    return out


def sensitivity_table(run, ref, net, warmup_s, measure):
    """All variants of [measure.sensitivity] (r_on x persist_m x adjacency x period_mult,
    60 by default) on one run; one row per variant with both length weights."""
    sens = measure["sensitivity"]
    adjs = {a: edge_adjacency(net, a) for a in sens["adjacency"]}
    P = float((run.end - run.begin).iloc[0])
    rows = []
    for pm in sens["period_mult"]:
        runm, refm = merge_intervals(run, pm), merge_intervals(ref, pm)
        vref, info = free_flow_reference(refm, net.edges, warmup_s,
                                         measure["vref_min_sampled_s"],
                                         measure.get("vref_fallback", "class_median"))
        r = relative_speed(runm, vref)
        for r_on in sens["r_on"]:
            for m in sens["persist_m"]:
                state = classify(r, r_on=r_on, persist_m=m)
                st = state[state.index >= warmup_s]
                for a in sens["adjacency"]:
                    row = dict(r_on=r_on, persist_m=m, adjacency=a, period_mult=pm,
                               period_s=P * pm, vref_coverage=info["coverage"])
                    for wname in WEIGHTS:
                        s = summarise(order_parameters(st, runm, net.edges, adjs[a], wname))
                        if wname == measure.get("weight", "lane_length"):
                            row.update(s)
                        else:
                            row.update({f"{k}_{wname}": s[k] for k in
                                        ("phi_len", "phi_len_var", "G1", "G1_var", "G2")})
                    rows.append(row)
    return pd.DataFrame(rows)
