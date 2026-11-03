"""Measured quantities computed from SUMO outputs.

Each scenario has one function that reads one run's outputs and returns
(measurements, checks, timeseries). Column names and units follow
traffic_project.results. Ring road (B): ring_summary. Grid (D), with a fixed
vehicle count: network_summary. City network (C): city_summary, built on
traffic_project.congestion.
"""
import xml.etree.ElementTree as ET

import numpy as np

from . import congestion as cg
from .io import iter_fcd, iter_summary


def ring_summary(fcd, n_vehicles, length_m, warmup_s, jam_speed_mps, sample_every_s):
    """Measurements on a closed ring over t >= warmup_s, checks, and a time series.

    mean_speed_mps          time average of the space-mean speed
    flow_veh_h              q = k * v, exact on a closed ring
    congested_fraction      share of vehicles slower than jam_speed_mps (phi)
    congested_fraction_var  variance of phi over time (chi)

    The time series holds instantaneous values every sample_every_s seconds over
    the whole run, including the warm-up, so the warm-up length can be checked.
    """
    k = 1000 * n_vehicles / length_m
    counts, v_mean, phi, series, min_speed = [], [], [], [], float("inf")
    for t, vehicles in iter_fcd(fcd):
        speeds = [v["speed"] for v in vehicles]
        counts.append(len(speeds))
        if not speeds:
            continue
        min_speed = min(min_speed, min(speeds))
        v_t = sum(speeds) / len(speeds)
        phi_t = sum(s < jam_speed_mps for s in speeds) / len(speeds)
        if t >= warmup_s:
            v_mean.append(v_t)
            phi.append(phi_t)
        if round(t / sample_every_s, 9).is_integer():
            k_t = 1000 * len(speeds) / length_m
            series.append({"time_s": t, "density_veh_km": k_t, "mean_speed_mps": round(v_t, 4),
                           "flow_veh_h": round(k_t * v_t * 3.6, 2), "congested_fraction": round(phi_t, 4)})
    v = sum(v_mean) / len(v_mean)
    mean_phi = sum(phi) / len(phi)
    measurements = {
        "density_veh_km": k,
        "mean_speed_mps": v,
        "flow_veh_h": k * v * 3.6,
        "congested_fraction": mean_phi,
        "congested_fraction_var": sum((p - mean_phi) ** 2 for p in phi) / len(phi),
    }
    checks = {
        "all_vehicles_present": min(counts) == max(counts) == n_vehicles,
        "no_negative_speed": min_speed >= 0,
    }
    return measurements, checks, series


def network_summary(fcd, n_vehicles, lane_length_m, warmup_s, jam_speed_mps, sample_every_s,
                    block_s=None, reference_length_m=None, summary_xml=None):
    """Network-wide measurements with a fixed vehicle count, over t >= warmup_s.

    Same quantities as ring_summary, using Edie's definitions over the whole
    network: when every vehicle is counted, the sum of their speeds divided by
    the total lane length is the length-weighted mean flow per lane, so
    q = k * v stays exact, with k in vehicles per km of lane.

    density_veh_km          N per km of lane of this network (lane_length_m)
    mean_speed_mps          time average of the space-mean speed
    flow_veh_h              q = k * v, per lane
    congested_fraction      share of vehicles slower than jam_speed_mps (phi)
    congested_fraction_var  variance over time of phi averaged in consecutive
                            blocks of block_s seconds (chi). On a signalised network
                            block_s should be the signal cycle, otherwise the
                            switching of the lights dominates the variance.
                            block_s=None uses every step, as on the ring.
    congested_fraction_var_step   the per-step variance, kept for comparison
    density_ref_veh_km      N per km of reference_length_m, e.g. the baseline
                            network of a planning comparison (only if given)

    The time series holds instantaneous values every sample_every_s seconds over
    the whole run, including the warm-up.

    all_vehicles_present counts the vehicles in summary_xml (SUMO's summary-output,
    `running`) when it is given, else in the FCD output. Use summary_xml on any network
    that may teleport: a vehicle in mid-teleport is missing from the FCD output but still
    counted as running, so only the summary count tells a teleport from a vehicle that
    SUMO never inserted (T3-D11).
    """
    k = 1000 * n_vehicles / lane_length_m
    counts, v_mean, phi, phi_t_list, series = [], [], [], [], []
    min_speed = float("inf")
    for t, vehicles in iter_fcd(fcd):
        speeds = [v["speed"] for v in vehicles]
        counts.append(len(speeds))
        if not speeds:
            continue
        min_speed = min(min_speed, min(speeds))
        v_t = sum(speeds) / len(speeds)
        phi_t = sum(s < jam_speed_mps for s in speeds) / len(speeds)
        if t >= warmup_s:
            v_mean.append(v_t)
            phi.append(phi_t)
            phi_t_list.append(t)
        if round(t / sample_every_s, 9).is_integer():
            k_t = 1000 * len(speeds) / lane_length_m
            series.append({"time_s": t, "density_veh_km": k_t, "mean_speed_mps": round(v_t, 4),
                           "flow_veh_h": round(k_t * v_t * 3.6, 2), "congested_fraction": round(phi_t, 4)})
    v = sum(v_mean) / len(v_mean)
    mean_phi = sum(phi) / len(phi)

    def variance(xs):
        m = sum(xs) / len(xs)
        return sum((x - m) ** 2 for x in xs) / len(xs)

    if block_s:
        # Average phi in whole blocks from the end of the warm-up; drop a partial last block.
        blocks = {}
        for t, p in zip(phi_t_list, phi):
            blocks.setdefault(int((t - warmup_s) // block_s), []).append(p)
        last = int((phi_t_list[-1] - warmup_s) // block_s)
        if len(blocks) > 1 and len(blocks[last]) < len(blocks[0]):
            del blocks[last]
        block_means = [sum(b) / len(b) for b in blocks.values()]
        chi = variance(block_means) if len(block_means) > 1 else float("nan")
    else:
        chi = variance(phi)

    measurements = {
        "density_veh_km": k,
        "mean_speed_mps": v,
        "flow_veh_h": k * v * 3.6,
        "congested_fraction": mean_phi,
        "congested_fraction_var": chi,
        "congested_fraction_var_step": variance(phi),
    }
    if reference_length_m:
        measurements["density_ref_veh_km"] = 1000 * n_vehicles / reference_length_m
    if summary_xml is not None:
        counts = [running for _, running in iter_summary(summary_xml)]
    checks = {
        "all_vehicles_present": min(counts) == max(counts) == n_vehicles,
        "no_negative_speed": min_speed >= 0,
    }
    return measurements, checks, series


def read_summary_xml(path):
    """SUMO summary output -> array of (time, running, halting, meanSpeed) per step."""
    rows = [(float(s.get("time")), int(s.get("running")), int(s.get("halting")),
             float(s.get("meanSpeed"))) for s in ET.parse(path).getroot().iter("step")]
    return np.array(rows, dtype=float).reshape(-1, 4)


def city_summary(edgedata_file, ref_edgedata_file, net_path, summary_xml, measure, warmup_s,
                 ref_summary_xml=None, n_vehicles=None):
    """City-network measurements over t >= warmup_s, checks, and a time series.

    Inputs: one run's edgeData (period = the criterion period) and summary output, the
    edgeData (and summary) of the k = 2 veh/km reference run on the same net, and the
    config's [measure] table. Definitions (provisional, Task 3 T3-D1, T3-D2, T3-D6, T3-D8):

    density_veh_km          time-mean vehicles running / total lane length (normal lanes)
    mean_speed_mps          time-mean of the summary output's meanSpeed
    flow_veh_h              k * v * 3.6
    congested_fraction      phi_veh: share of vehicle-time on congested edges, time-mean
                            over criterion intervals (not the ring's share of slow vehicles)
    congested_fraction_var  variance of phi_veh over intervals
    city_*                  lane-length (or road-length) shares: congested length, largest
                            and second-largest cluster (means, variances), cluster count,
                            spillback events, gridlock flag, halting share, v_ref coverage

    The time series has one row every measure["timeseries_every_s"] s over the whole run;
    congested_fraction repeats phi_veh of the last completed interval (0 before the first).
    """
    m = measure
    net = cg.read_net(net_path)
    P = cg.cycle_period(net, m["period_s"])
    mult = m.get("period_mult", 1)
    run, ref = cg.read_edgedata(edgedata_file), cg.read_edgedata(ref_edgedata_file)
    file_P = float((run.end - run.begin).iloc[0])
    adj = cg.edge_adjacency(net, m["adjacency"])
    kw = dict(r_on=m["r_on"], persist_m=m["persist_m"], adjacency=m["adjacency"], period_mult=mult,
              min_sampled_s=m["vref_min_sampled_s"],
              vref_fallback=m.get("vref_fallback", "class_median"), adj=adj)
    weight = m.get("weight", "lane_length")
    other = "road_length" if weight == "lane_length" else "lane_length"
    ser, state, info = cg.analyse(run, ref, net, warmup_s, weight=weight, **kw)
    runm, refm = cg.merge_intervals(run, mult), cg.merge_intervals(ref, mult)
    keep = state.index >= warmup_s
    ser2 = cg.order_parameters(state[keep], runm, net.edges, adj, other)
    s1, s2 = cg.summarise(ser), cg.summarise(ser2)

    # vehicle-time share per interval over the whole run (for the time series)
    sampled = cg.wide(runm, "sampledSeconds", net.edges).reindex(state.index).fillna(0.0).to_numpy()
    tot = sampled.sum(axis=1)
    phi_all = np.where(tot > 0, (sampled * state.to_numpy()).sum(axis=1) / np.where(tot > 0, tot, 1), 0.0)

    # spillback and gridlock (T3-D8 constants)
    occ_jam = m["veh_length_m"] / (m["veh_length_m"] + m["min_gap_m"])
    spill = cg.spillback(state, cg.wide(runm, "occupancy", net.edges), occ_jam,
                         m["spillback_occ_frac"], m["persist_m"])
    rises = np.diff(np.vstack([np.zeros((1, spill.shape[1])), spill.to_numpy()]), axis=0) == 1
    spill_events = int(rises[keep].sum())
    outflow = runm.groupby("begin").left.sum().reindex(state.index).to_numpy()
    s_run = read_summary_xml(summary_xml)
    w_run = s_run[:, 0] >= warmup_s
    free_out = refm[refm.begin >= warmup_s].groupby("begin").left.sum().mean()
    if ref_summary_xml is not None:
        s_ref = read_summary_xml(ref_summary_xml)
        free_out *= s_run[w_run, 1].mean() / s_ref[s_ref[:, 0] >= warmup_s, 1].mean()
    grid = cg.gridlock(outflow, free_out, m["gridlock_outflow_frac"], m["gridlock_cycles"])

    lane_m = float((net.edges.length * net.edges.lanes).sum())
    running, halting, vbar = s_run[w_run, 1], s_run[w_run, 2], s_run[w_run, 3]
    k = 1000 * running.mean() / lane_m
    v = float(np.where(running > 0, np.maximum(vbar, 0), 0).mean())
    suffix = "_road" if other == "road_length" else "_lane"
    measurements = {
        "density_veh_km": k, "mean_speed_mps": v, "flow_veh_h": k * v * 3.6,
        "congested_fraction": s1["phi_veh"], "congested_fraction_var": s1["phi_veh_var"],
        "city_congested_length_fraction": s1["phi_len"],
        "city_congested_length_fraction_var": s1["phi_len_var"],
        "city_largest_cluster": s1["G1"], "city_largest_cluster_var": s1["G1_var"],
        "city_second_cluster": s1["G2"], "city_second_cluster_var": s1["G2_var"],
        "city_n_clusters": s1["n_clusters"],
        f"city_congested_length_fraction{suffix}": s2["phi_len"],
        f"city_largest_cluster{suffix}": s2["G1"], f"city_largest_cluster{suffix}_var": s2["G1_var"],
        f"city_second_cluster{suffix}": s2["G2"],
        "city_spillback_events": spill_events, "city_gridlock": int(grid[keep].any()),
        "city_halting_share": float(np.mean(halting / np.maximum(running, 1))),
        "city_vref_coverage": info["coverage"], "city_period_s": P * mult,
        "city_n_intervals": s1["n_intervals"], "city_lane_length_m": lane_m,
    }
    checks = {
        "all_vehicles_present": bool(running.min() == running.max()
                                     and (n_vehicles is None or running.min() == n_vehicles)),
        "edgedata_period_matches": abs(file_P - P) < 1e-6,
        "edgedata_covers_net": set(net.edges.index) <= set(run.edge),
        "order_parameters_in_range": bool(((0 <= ser.G2) & (ser.G2 <= ser.G1 + 1e-12)
                                           & (ser.G1 <= ser.phi_len + 1e-12) & (ser.phi_len <= 1)).all()),
    }
    every = m["timeseries_every_s"]
    ends = state.index.to_numpy() + P * mult
    series = []
    for t, n, _, vt in s_run:
        if round(t / every, 9).is_integer():
            i = np.searchsorted(ends, t, side="right") - 1
            k_t, v_t = 1000 * n / lane_m, max(vt, 0.0) if n > 0 else 0.0
            series.append({"time_s": t, "density_veh_km": k_t, "mean_speed_mps": round(v_t, 4),
                           "flow_veh_h": round(k_t * v_t * 3.6, 2),
                           "congested_fraction": round(float(phi_all[i]), 4) if i >= 0 else 0.0})
    return measurements, checks, series
