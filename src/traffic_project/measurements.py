"""Measured quantities computed from SUMO outputs.

Each scenario has one function that reads one run's outputs and returns
(measurements, checks, timeseries). Column names and units follow
traffic_project.results. Ring road (B): ring_summary. City network (C): add a
network function here following the same pattern.
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
