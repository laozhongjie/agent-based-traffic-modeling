"""Measured quantities computed from SUMO outputs.

Ring road (B): ring_summary. City network (C): add network measurements here
following the same pattern — a function that reads one run's outputs and returns
(measurements, checks).
"""
from .io import iter_fcd


def ring_summary(fcd, n_vehicles, length_m, warmup_s, jam_speed_mps):
    """Measurements on a closed ring over t >= warmup_s, plus vehicle checks.

    mean_speed_mps          time average of the space-mean speed
    flow_veh_h              q = k * v, exact on a closed ring
    congested_fraction      share of vehicles slower than jam_speed_mps (phi)
    congested_fraction_var  variance of phi over time (chi)
    """
    counts, v_mean, phi, min_speed = [], [], [], float("inf")
    for t, vehicles in iter_fcd(fcd):
        speeds = [v["speed"] for v in vehicles]
        counts.append(len(speeds))
        if speeds:
            min_speed = min(min_speed, min(speeds))
        if t >= warmup_s and speeds:
            v_mean.append(sum(speeds) / len(speeds))
            phi.append(sum(s < jam_speed_mps for s in speeds) / len(speeds))
    k = 1000 * n_vehicles / length_m
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
    return measurements, checks
