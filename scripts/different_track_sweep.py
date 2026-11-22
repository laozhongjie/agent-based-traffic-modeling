"""Run SUMO IDM sweeps on ring, oval and open freeway and save one combined CSV.

From the repository root:
  python scripts/different_track_sweep.py --config configs/ring/idm_open_freeway_4800.toml
  python scripts/different_track_sweep.py --config configs/ring/idm_multi_ring_4800.toml --config configs/ring/idm_oval_freeway_4800.toml

Each (vehicle count, seed) gets a separate runs/<run-id>/ directory. Metrics
come from fcd.xml and are averaged over the last fraction of simulation time.
For open roads, initial target density is NOT actual observed density.
"""
import argparse
import csv
import math
import subprocess
import sys
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scenarios" / "ring" / "build_run_different_track.py"
FIELDS = [
    "config", "run_id", "network_type", "length_m", "lanes", "vehicles_requested",
    "seed", "initial_target_density_veh_km_total", "initial_target_density_veh_km_lane",
    "inflow_requested_veh_h_lane", "window_start_s", "window_end_s",
    "samples", "mean_vehicles_observed", "mean_density_veh_km_total",
    "mean_density_veh_km_lane", "mean_speed_mps", "speed_std_mps",
    "jam_fraction_vehicle_samples", "estimated_flow_veh_h_total",
    "vehicles_seen_unique", "first_sample_vehicles", "last_sample_vehicles",
    "status", "error", "run_dir",
]


def parse_fcd(path, length, lanes, window_start, jam_threshold):
    # Read incremental XML to avoid loading the large FCD output into memory.
    timesteps = 0
    t_start = None
    t_end = None
    sum_counts = sum_speed = sum_speed2 = sum_jam = 0.0
    first_count = last_count = None
    seen = set()
    for _, elem in ET.iterparse(path, events=("end",)):
        if elem.tag != "timestep":
            continue
        t = float(elem.attrib["time"])
        if t < window_start:
            elem.clear()
            continue
        count = 0
        total_speed = total_speed_sq = jams = 0.0
        for v in elem.findall("vehicle"):
            speed = float(v.attrib["speed"])
            count += 1
            total_speed += speed
            total_speed_sq += speed * speed
            jams += speed < jam_threshold
            seen.add(v.attrib["id"])
        if first_count is None:
            first_count = count
            t_start = t
        last_count = count
        t_end = t
        timesteps += 1
        sum_counts += count
        sum_speed += total_speed
        sum_speed2 += total_speed_sq
        sum_jam += jams
        elem.clear()
    if not timesteps or not sum_counts:
        raise ValueError(f"No vehicle observations in analysis window: {path}")
    mean_count = sum_counts / timesteps
    mean_speed = sum_speed / sum_counts  # vehicle-time mean speed
    std_speed = math.sqrt(max(0.0, sum_speed2 / sum_counts - mean_speed ** 2))
    density = mean_count / (length / 1000)
    # q = rho * v: estimate only; no detector crossing count measured.
    flow_estimate = density * mean_speed * 3.6
    return dict(window_start_s=t_start, window_end_s=t_end, samples=timesteps,
                mean_vehicles_observed=mean_count, mean_density_veh_km_total=density,
                mean_density_veh_km_lane=density / lanes,
                mean_speed_mps=mean_speed, speed_std_mps=std_speed,
                jam_fraction_vehicle_samples=sum_jam / sum_counts,
                estimated_flow_veh_h_total=flow_estimate,
                vehicles_seen_unique=len(seen), first_sample_vehicles=first_count,
                last_sample_vehicles=last_count)


def run_command(cmd, logfile):
    with logfile.open("w") as fh:
        proc = subprocess.run(cmd, cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT)
    if proc.returncode:
        raise RuntimeError(f"Command exited {proc.returncode}: {' '.join(map(str, cmd))}; see {logfile}")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", action="append", required=True, help="TOML path, repeatable")
    p.add_argument("--output", default="results/different_track/combined_sweep.csv")
    p.add_argument("--window-fraction", type=float, default=0.5,
                   help="Analyze final fraction of simulation (default 0.5)")
    p.add_argument("--sumo", default="sumo", help="Path to SUMO binary")
    p.add_argument("--skip-existing", action="store_true", help="Reuse existing fcd.xml")
    args = p.parse_args()
    if not 0 < args.window_fraction <= 1:
        p.error("--window-fraction must be in (0, 1]")
    if not BUILDER.exists():
        p.error(f"Cannot find run builder: {BUILDER}; put this file in scripts/")
    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    configs = []
    for config_str in args.config:
        path = Path(config_str)
        if not path.is_absolute():
            path = ROOT / path
        cfg = tomllib.loads(path.read_text())
        configs.append((path, cfg))

    # Immediately append rows, so completed results survive a failed/interrupted run.
    file_exists = output.exists() and output.stat().st_size > 0
    with output.open("a", newline="") as fout:
        writer = csv.DictWriter(fout, fieldnames=FIELDS)
        if not file_exists:
            writer.writeheader()
        for cfg_path, cfg in configs:
            net = cfg.get("network", {})
            kind = net.get("type", "ring")
            length = float(net.get("length_m", cfg.get("ring", {}).get("length_m", 4800)))
            lanes = int(net.get("lanes", 1))
            if length <= 0 or lanes < 1:
                raise ValueError("Invalid length or lanes")
            end_s = float(cfg["run"]["end_s"])
            window_start = end_s * (1 - args.window_fraction)
            jam_speed = float(cfg.get("measure", {}).get("jam_speed_mps", 5))
            rate = float(cfg.get("open", {}).get("inflow_veh_h_lane", 0)) if kind == "freeway" else 0
            for n in cfg["sweep"]["vehicles"]:
                for seed in cfg["sweep"]["seeds"]:
                    n, seed = int(n), int(seed)
                    run_id = f"{kind}_{cfg['model'].lower()}_L{int(length)}_m{lanes}_n{n}_s{seed}"
                    run_dir = ROOT / "runs" / run_id
                    fcd = run_dir / "fcd.xml"
                    row = dict(config=str(cfg_path.relative_to(ROOT)) if cfg_path.is_relative_to(ROOT) else str(cfg_path),
                               run_id=run_id, network_type=kind, length_m=length,
                               lanes=lanes, vehicles_requested=n, seed=seed,
                               initial_target_density_veh_km_total=n / (length / 1000),
                               initial_target_density_veh_km_lane=n / (length / 1000) / lanes,
                               inflow_requested_veh_h_lane=rate,
                               status="ok", error="", run_dir=str(run_dir.relative_to(ROOT)))
                    print(f"[{kind}] N={n} seed={seed}", flush=True)
                    try:
                        if not (args.skip_existing and fcd.exists() and fcd.stat().st_size > 0):
                            run_dir.mkdir(parents=True, exist_ok=True)
                            run_command([sys.executable, str(BUILDER), "--config", str(cfg_path),
                                         "--vehicles", str(n), "--seed", str(seed)],
                                        run_dir / "build.log")
                            run_command([args.sumo, "-c", str(run_dir / "run.sumocfg"),
                                         "--no-step-log", "true"], run_dir / "sumo.log")
                        row.update(parse_fcd(fcd, length, lanes, window_start, jam_speed))
                    except (Exception) as exc:
                        row["status"] = "error"
                        row["error"] = str(exc)
                        print(f"  ERROR: {exc}", file=sys.stderr, flush=True)
                    writer.writerow({key: row.get(key, "") for key in FIELDS})
                    fout.flush()
    print(f"Combined results: {output}")
    print("Note: rerunning appends duplicate rows; use a new --output or delete the previous CSV first.")


if __name__ == "__main__":
    main()
