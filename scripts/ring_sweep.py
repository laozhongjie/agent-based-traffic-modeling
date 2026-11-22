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


def resolved_initial(cfg):
    """Return the initialization settings written to the run manifest."""
    initial = dict(cfg.get("initial", {}))
    initial.setdefault("mode", "uniform_jitter")
    if initial["mode"] == "uniform_jitter":
        jitter_value = initial.get("jitter_m", cfg["run"].get("jitter_m"))
        if jitter_value is not None:
            initial["jitter_m"] = jitter_value
    return initial


def ovm_implementation(cfg):
    """Validate and return the requested OVM implementation."""
    implementation = str(cfg.get("implementation", "traci")).lower()
    if implementation not in {"traci", "native"}:
        raise ValueError("OVM implementation must be 'traci' or 'native'")

    vtype = cfg["vtype"]
    if implementation == "traci":
        if "ovm" not in cfg:
            raise ValueError("TraCI OVM requires an [ovm] table")
        for key in ("alpha", "h_c", "h_scale"):
            if key not in cfg["ovm"]:
                raise ValueError(f"TraCI OVM requires ovm.{key}")
    else:
        if vtype.get("carFollowModel") != "OVM":
            raise ValueError("native OVM requires vtype.carFollowModel = 'OVM'")
        for key in ("alpha", "sc", "d"):
            if key not in vtype:
                raise ValueError(f"native OVM requires vtype.{key}")

    return implementation


def run_one(cfg, n, seed):
    r = subprocess.run([sys.executable, str(BUILD_RUN), "--config", cfg["_path"],
                        "--vehicles", str(n), "--seed", str(seed)],
                       cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(r.stderr.strip())
    run_id = r.stdout.strip()
    run_dir = ROOT / "runs" / run_id

    # Record the resolved initialization method. Existing IDM and OVM configs
    # have no [initial] table, so they retain their seeded run.jitter_m setup.
    initial = resolved_initial(cfg)

    parameters = {"vehicles": n, "seed": seed, "ring": cfg["ring"], "run": cfg["run"],
                  "initial": initial, "vtype": cfg["vtype"], "measure": cfg["measure"]}

    implementation = None
    if cfg["model"].upper() == "OVM":
        implementation = ovm_implementation(cfg)
        parameters["implementation"] = implementation
        if implementation == "traci":
            parameters["ovm"] = cfg["ovm"]

    runner.write_manifest(run_dir, run_id, cfg, parameters)

    # Release-SUMO trials may use the Python controller. Formal OVM batches use
    # the pinned native build to avoid per-vehicle TraCI calls at every step.
    if cfg["model"].upper() == "OVM" and implementation == "traci":
        from traffic_project.ovm_traci import make_ovm_controller

        ovm = cfg["ovm"]

        controller = make_ovm_controller(
            ring_length=cfg["ring"]["length_m"],
            dt=cfg["run"]["step_s"],
            alpha=ovm["alpha"],
            v_max=cfg["vtype"]["maxSpeed"],
            h_c=ovm["h_c"],
            h_scale=ovm["h_scale"],
            min_gap=cfg["vtype"]["minGap"],
            expected_vehicles=n,
        )

        _, checks = runner.run_traci(run_dir, controller)

    else:
        _, checks = runner.run_sumo(run_dir)


    m = cfg["measure"]
    measured, ring_checks, series = measurements.ring_summary(
        run_dir / "fcd.xml", n, cfg["ring"]["length_m"], cfg["run"]["warmup_s"],
        m["jam_speed_mps"], m["timeseries_every_s"])
    results.write_timeseries(run_id, series, cfg)
    summary = dict(measured, scenario=cfg["scenario"], model=cfg["model"],
                   variant=cfg.get("variant", ""),
                   seed=seed, ring_vehicles=n)
    return runner.finish(run_dir, run_id, summary, {**checks, **ring_checks})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, help="configs/ring/<name>.toml")
    args = ap.parse_args()
    cfg = config.load(args.config)

    if cfg["model"].upper() == "OVM":
        try:
            implementation = ovm_implementation(cfg)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        if implementation == "native" and not runner.sumo_has_model("OVM"):
            raise SystemExit(
                "The SUMO on PATH has no native OVM. Activate A's pinned build "
                "from sumo/version.txt, or use implementation = 'traci' for a trial."
            )

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
