"""Density sweep on the ring road: build, run, check and summarise each run.

For every vehicle count N and seed this script
  1. writes the run inputs with scenarios/ring/build_run.py,
  2. runs SUMO and keeps its log,
  3. checks the run (vehicle count, collisions, teleports, negative speeds),
  4. writes runs/<run-id>/manifest.json and summary.json,
and finally collects all summaries into results/ring/<name>.csv.

Usage:
    python scripts/ring_sweep.py --vehicles 10 20 30 --seeds 1 --name idm_sweep
"""
import argparse
import csv
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD_RUN = ROOT / "scenarios" / "ring" / "build_run.py"
JAM_SPEED = 5.0  # m/s; placeholder threshold for "congested vehicle" until B fixes the criterion


def sh(*cmd):
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)


def summarise(fcd, n_expected, length, warmup):
    """Space-mean speed, flow and congested fraction over t >= warmup, plus checks."""
    counts, v_mean, phi, min_speed = [], [], [], float("inf")
    for _, el in ET.iterparse(fcd):
        if el.tag != "timestep":
            continue
        speeds = [float(v.get("speed")) for v in el]
        counts.append(len(speeds))
        if speeds:
            min_speed = min(min_speed, min(speeds))
        if float(el.get("time")) >= warmup and speeds:
            v_mean.append(sum(speeds) / len(speeds))
            phi.append(sum(s < JAM_SPEED for s in speeds) / len(speeds))
        el.clear()
    k = 1000 * n_expected / length                      # veh/km
    v = sum(v_mean) / len(v_mean)                       # m/s, time average of space-mean speed
    q = k * v * 3.6                                     # veh/h, q = k * v on a closed ring
    mean_phi = sum(phi) / len(phi)
    chi = sum((p - mean_phi) ** 2 for p in phi) / len(phi)  # variance of phi over time
    checks = {
        "all_vehicles_present": min(counts) == max(counts) == n_expected,
        "no_negative_speed": min_speed >= 0,
    }
    return {"density_veh_km": k, "mean_speed_mps": v, "flow_veh_h": q,
            "congested_fraction": mean_phi, "congested_fraction_var": chi}, checks


def run_one(length, n, seed, end, warmup):
    run_id = f"ring_idm_L{int(length)}_n{n}_s{seed}"
    run_dir = ROOT / "runs" / run_id
    r = sh(sys.executable, str(BUILD_RUN), "--length", str(length), "--vehicles", str(n),
           "--seed", str(seed), "--end", str(end))
    if r.returncode:
        raise SystemExit(r.stderr)
    r = sh("sumo", "-c", str(run_dir / "run.sumocfg"), "--no-step-log")
    log = r.stdout + r.stderr
    (run_dir / "log.txt").write_text(log)

    summary, checks = summarise(run_dir / "fcd.xml", n, length, warmup)
    checks["sumo_exit_ok"] = r.returncode == 0
    checks["no_collision"] = "collision" not in log.lower()
    checks["no_teleport"] = "teleport" not in log.lower()
    summary.update(run_id=run_id, vehicles=n, seed=seed, valid=all(checks.values()), checks=checks)

    manifest = {
        "run_id": run_id,
        "scenario": "ring", "model": "IDM",
        "parameters": {"length_m": length, "vehicles": n, "seed": seed,
                       "end_s": end, "warmup_s": warmup, "jam_speed_mps": JAM_SPEED},
        "sumo_version": sh("sumo", "--version").stdout.splitlines()[0],
        "git_commit": sh("git", "rev-parse", "--short", "HEAD").stdout.strip()
                      + ("-dirty" if sh("git", "status", "--porcelain").stdout.strip() else ""),
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--length", type=float, default=1000.0)
    ap.add_argument("--vehicles", type=int, nargs="+", required=True)
    ap.add_argument("--seeds", type=int, nargs="+", default=[1])
    ap.add_argument("--end", type=float, default=1800)
    ap.add_argument("--warmup", type=float, default=600)
    ap.add_argument("--name", default="idm_sweep", help="results/ring/<name>.csv")
    args = ap.parse_args()

    rows = []
    for n in args.vehicles:
        for seed in args.seeds:
            s = run_one(args.length, n, seed, args.end, args.warmup)
            rows.append(s)
            print(f"{s['run_id']:<26} k={s['density_veh_km']:6.1f}  v={s['mean_speed_mps']:5.2f} m/s  "
                  f"q={s['flow_veh_h']:6.0f} veh/h  phi={s['congested_fraction']:.2f}  "
                  f"{'ok' if s['valid'] else 'INVALID ' + str(s['checks'])}")

    out = ROOT / "results" / "ring" / f"{args.name}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    cols = ["run_id", "vehicles", "seed", "density_veh_km", "mean_speed_mps", "flow_veh_h",
            "congested_fraction", "congested_fraction_var", "valid"]
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
