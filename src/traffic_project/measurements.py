"""Measured quantities computed from SUMO outputs.

Each scenario has one function that reads one run's outputs and returns
(measurements, checks, timeseries). Column names and units follow
traffic_project.results. Ring road (B): ring_summary. Networks with a fixed
vehicle count (grid, city): network_summary.
"""
from .io import iter_fcd


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
                    block_s=None, reference_length_m=None):
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
    checks = {
        "all_vehicles_present": min(counts) == max(counts) == n_vehicles,
        "no_negative_speed": min_speed >= 0,
    }
    return measurements, checks, series
