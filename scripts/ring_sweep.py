"""Ring-road density sweep: build, run, check and summarise every run in a config.

For every vehicle count and seed in the config this script
  1. writes the run inputs with scenarios/ring/build_run.py,
  2. runs SUMO and writes the run record (traffic_project.runner),
  3. measures and checks the run (traffic_project.measurements),
  4. writes its time series to results/ring/<name>/<run_id>.csv,
and finally writes the summary table results/ring/<name>.csv. Both files follow
the data interface in traffic_project.results.

Usage (from the repository root):
    python scripts/ring_sweep.py --config configs/ring/idm_sweep.toml
"""
import argparse
import subprocess
import sys

from traffic_project import ROOT, config, measurements, results, runner

BUILD_RUN = ROOT / "scenarios" / "ring" / "build_run.py"


def run_one(cfg, n, seed):
    r = subprocess.run([sys.executable, str(BUILD_RUN), "--config", cfg["_path"],
                        "--vehicles", str(n), "--seed", str(seed)],
                       cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(r.stderr.strip())
    run_id = r.stdout.strip()
    run_dir = ROOT / "runs" / run_id

    parameters = {"vehicles": n, "seed": seed, "ring": cfg["ring"], "run": cfg["run"],
                  "vtype": cfg["vtype"], "measure": cfg["measure"]}
    runner.write_manifest(run_dir, run_id, cfg, parameters)
    _, checks = runner.run_sumo(run_dir)
    m = cfg["measure"]
    measured, ring_checks, series = measurements.ring_summary(
        run_dir / "fcd.xml", n, cfg["ring"]["length_m"], cfg["run"]["warmup_s"],
        m["jam_speed_mps"], m["timeseries_every_s"])
    results.write_timeseries(run_id, series, cfg)
    summary = dict(measured, scenario=cfg["scenario"], model=cfg["model"], variant="",
                   seed=seed, ring_vehicles=n)
    return runner.finish(run_dir, run_id, summary, {**checks, **ring_checks})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, help="configs/ring/<name>.toml")
    args = ap.parse_args()
    cfg = config.load(args.config)

    rows = []
    for n in cfg["sweep"]["vehicles"]:
        for seed in cfg["sweep"]["seeds"]:
            s = run_one(cfg, n, seed)
            rows.append(s)
            failed = [k for k, ok in s["checks"].items() if not ok]
            print(f"{s['run_id']:<26} k={s['density_veh_km']:6.1f}  v={s['mean_speed_mps']:5.2f} m/s  "
                  f"q={s['flow_veh_h']:6.0f} veh/h  phi={s['congested_fraction']:.2f}  "
                  f"{'ok' if s['valid'] else 'INVALID: ' + ', '.join(failed)}")

    out = results.write_summary(rows, cfg)
    print(f"wrote {out.relative_to(ROOT)} and {len(rows)} time series in {out.with_suffix('').relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
