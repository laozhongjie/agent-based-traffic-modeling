"""Grid density sweep: build, run, check and summarise every run in a config.

For every variant, vehicle count and seed in the config this script
  1. writes the run inputs with scenarios/grid/build_run.py,
  2. runs SUMO and writes the run record (traffic_project.runner),
  3. measures and checks the run (traffic_project.measurements.network_summary),
  4. writes its time series to results/<scenario>/<name>/<run_id>.csv,
  5. deletes the run's FCD file unless [run] keep_fcd = true (it is large on a grid),
and finally writes the summary table results/<scenario>/<name>.csv. Both files
follow the data interface in traffic_project.results.

Density is quoted twice: per km of lane of the variant itself (density_veh_km)
and per km of lane of the baseline grid (density_ref_veh_km), so planning
variants can be compared at the same vehicle count.

Usage (from the repository root):
    python scripts/grid_sweep.py --config configs/validation/grid_smoke.toml
"""
import argparse
import json
import subprocess
import sys
import xml.etree.ElementTree as ET

from traffic_project import ROOT, config, measurements, results, runner

GRID = ROOT / "scenarios" / "grid"
BUILD_RUN = GRID / "build_run.py"


def net_stem(cfg, variant):
    g = cfg["grid"]
    return GRID / f"grid{g['n']}x{g['n']}_L{int(g['block_m'])}_{variant}"


def signal_cycle_s(net):
    """Cycle length shared by the network's fixed-time signals, or None if it has none."""
    cycles = {sum(float(p.get("duration")) for p in tl.iter("phase"))
              for tl in ET.parse(net).getroot().iter("tlLogic")}
    if len(cycles) > 1:
        raise SystemExit(f"{net.name}: signals have different cycles {sorted(cycles)}; "
                         "set [measure] variance_block_s to a number")
    return cycles.pop() if cycles else None


def variance_block(cfg, net):
    block = cfg["measure"].get("variance_block_s", "signal_cycle")
    return signal_cycle_s(net) if block == "signal_cycle" else (float(block) or None)


def run_one(cfg, variant, n, seed):
    r = subprocess.run([sys.executable, str(BUILD_RUN), "--config", cfg["_path"],
                        "--variant", variant, "--vehicles", str(n), "--seed", str(seed)],
                       cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(r.stderr.strip())
    run_id = r.stdout.strip()
    run_dir = ROOT / "runs" / run_id
    stem = net_stem(cfg, variant)
    meta = json.loads(stem.with_suffix(".meta.json").read_text())
    block_s = variance_block(cfg, stem.with_suffix(".net.xml"))

    parameters = {"vehicles": n, "seed": seed, "variant": variant, "grid": cfg["grid"],
                  "network": meta, "run": cfg["run"], "vtype": cfg["vtype"],
                  "measure": dict(cfg["measure"], variance_block_used_s=block_s)}
    runner.write_manifest(run_dir, run_id, cfg, parameters)
    _, checks = runner.run_sumo(run_dir)
    m = cfg["measure"]
    fcd = run_dir / "fcd.xml"
    measured, net_checks, series = measurements.network_summary(
        fcd, n, meta["lane_length_m"], cfg["run"]["warmup_s"], m["jam_speed_mps"],
        m["timeseries_every_s"], block_s=block_s,
        reference_length_m=meta["baseline_lane_length_m"])
    results.write_timeseries(run_id, series, cfg)
    if not cfg["run"].get("keep_fcd", False):
        fcd.unlink()
    summary = dict(measured, scenario=cfg["scenario"], model=cfg["model"], variant=variant,
                   seed=seed, network_vehicles=n)
    return runner.finish(run_dir, run_id, summary, {**checks, **net_checks})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, help="configs/<group>/<name>.toml")
    args = ap.parse_args()
    cfg = config.load(args.config)

    rows = []
    for variant in cfg["sweep"]["variants"]:
        for n in cfg["sweep"]["vehicles"]:
            for seed in cfg["sweep"]["seeds"]:
                s = run_one(cfg, variant, n, seed)
                rows.append(s)
                failed = [k for k, ok in s["checks"].items() if not ok]
                print(f"{s['run_id']:<30} k_ref={s['density_ref_veh_km']:6.1f}  "
                      f"v={s['mean_speed_mps']:5.2f} m/s  q={s['flow_veh_h']:6.0f} veh/h  "
                      f"phi={s['congested_fraction']:.2f}  chi={s['congested_fraction_var']:.5f}  "
                      f"{'ok' if s['valid'] else 'INVALID: ' + ', '.join(failed)}")

    out = results.write_summary(rows, cfg)
    print(f"wrote {out.relative_to(ROOT)} and {len(rows)} time series in "
          f"{out.with_suffix('').relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
