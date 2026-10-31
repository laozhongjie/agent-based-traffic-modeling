"""Grid density sweep: build, run, check and summarise every run in a config.

For every variant, vehicle count and seed in the config this script
  1. writes the run inputs into runs/<run_prefix>_<variant>_n<N>_s<seed>/ with
     scenarios/grid/build_run.py (run_prefix: [sweep] run_prefix, or the config's name when
     that is not set; build_run.py stops instead of overwriting another config's run),
  2. runs SUMO through TraCI with the constant-density controller
     (traffic_project.demand.ConstantDensity: the T4-D1 route rule of [controller], so no
     car arrives and N stays exact), writes the run record (traffic_project.runner) and
     saves the controller's record in runs/<run_id>/controller.json (counts, N, teleport
     start times, wall time),
  3. measures and checks the run (traffic_project.measurements.network_summary, and the
     controller's checks: N exact after every step, teleport count as in SUMO's log),
  4. writes its time series to results/<scenario>/<name>/<run_id>.csv,
  5. deletes the run's FCD file unless [run] keep_fcd = true (it is large on a grid),
and finally writes the summary table results/<scenario>/<name>.csv. Both files
follow the data interface in traffic_project.results.

Density is quoted twice: per km of lane of the variant itself (density_veh_km)
and per km of lane of the baseline grid (grid_density_ref_veh_km), so planning
variants can be compared at the same vehicle count.

Run rules agreed by the group 2026-10-27, as on C's city network (scripts/city_sweep.py):
T4-D1, every car gets a random destination edge from the controller and re-plans its route
with SUMO's rerouting device ([rerouting], written into run.sumocfg by build_run.py); and
T3-D11, with [run] allow_teleport = true SUMO teleports a car stuck for time_to_teleport_s,
and every run reports grid_teleports, grid_teleports_per_car_h_window (teleports that
started in warmup_s-end_s, per car and hour; the number to quote) and
grid_teleports_per_car_h_run (the same over 0-end_s).
Before the first run the script stops when [controller] guard_m does not exceed the
farthest a car drives in one step (maxSpeed x step_s), or when a variant has a car edge
that cannot be reached from every other one: destinations are drawn uniformly over the
base grid's car edges that the variant still has (T4-D2, as for city variants: a closure or
a new link changes the roads, not the trips), so a car sent to such an edge could not be
re-targeted. As city_sweep.py does for T4-D2, it also stops when a variant or the base grid
has lanes that ban passenger cars (close a road by deleting its edge), when a variant shares
no car edge with the base grid, and when more than [grid] max_dropped_edges (default 5) base
edges are missing from a variant (a rebuilt net renames edges). The controller columns are
those of the city (grid_ instead of city_): N over the run (grid_n_min, grid_n_max,
grid_n_short_steps), teleports, cars in mid-teleport (grid_mid_teleport_mean_window over
warmup_s-end_s, grid_mid_teleport_max) and re-targets (grid_retargets, grid_guard_retargets,
grid_retarget_failed, grid_reinserted).

Usage (from the repository root):
    python scripts/grid_sweep.py --config configs/validation/grid_smoke.toml
"""
import argparse
import json
import math
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

from traffic_project import ROOT, config, demand, measurements, results, runner

GRID = ROOT / "scenarios" / "grid"
BUILD_RUN = GRID / "build_run.py"
ROUTING = {}  # (net, guard_m) -> the controller's destination edges and near sets


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


def check_config(cfg):
    """Stop on settings that would break the controller's guarantee that no car arrives."""
    c = cfg["controller"]
    reach = cfg["vtype"]["maxSpeed"] * cfg["run"]["step_s"]
    if not c["guard_m"] > reach:
        raise SystemExit(f"[controller] guard_m = {c['guard_m']} m must exceed maxSpeed x step_s = "
                         f"{reach:g} m, the farthest a car drives in one step, or cars can arrive")
    if c["destination"] != "uniform_edge":
        raise SystemExit(f"[controller] destination = {c['destination']!r}: only 'uniform_edge' is implemented")


def lane_length_m(net):
    """Total length (m) of the lanes of the normal (non-internal) edges of a net."""
    return sum(float(ln.get("length")) for e in ET.parse(net).getroot().iter("edge")
               if e.get("function") != "internal" for ln in e.iter("lane"))


def net_routing(cfg, variant):
    """Destination edges (the base grid's car edges this variant has) and near sets (guard_m) on one variant."""
    runner._import_traci()   # demand imports sumolib and traci from $SUMO_HOME/tools (GUIDE section 1)
    net, guard = net_stem(cfg, variant).with_suffix(".net.xml"), cfg["controller"]["guard_m"]
    if (net, guard) not in ROUTING:
        outside = demand.outside_largest_scc(demand.car_successors(net))
        if outside:
            raise SystemExit(f"{net.name}: {len(outside)} car edges cannot be reached from every other car "
                             f"edge (e.g. {outside[:5]}); a car sent there could not be re-targeted and would arrive")
        # T4-D2, as for city variants: destinations are the base grid's car edges that this
        # variant still has, so a closure or a new link changes the roads, not the trips.
        base = net_stem(cfg, "base").with_suffix(".net.xml")
        lanes, base_lanes = demand.car_lanes(net), demand.car_lanes(base)
        for path, car in ((net, lanes), (base, base_lanes)):   # the guards of city_sweep.load_network
            banned = lane_length_m(path) - sum(length * len(idx) for _, length, idx in car)
            if abs(banned) > 0.5:   # m
                raise SystemExit(f"{path.name}: {banned:.1f} m of lanes ban passenger cars, so the lane length "
                                 f"that sets N and k is not the car-lane length; close a road by deleting its edge")
        dests, dropped, _ = demand.baseline_destinations(base_lanes, lanes)
        if not dests:
            raise SystemExit(f"{net.name} shares no car edge with the base grid {base.name}")
        limit = cfg["grid"].get("max_dropped_edges", 5)
        if len(dropped) > limit:
            raise SystemExit(f"{len(dropped)} base grid car edges are missing from {net.name} (limit {limit}, "
                             f"[grid] max_dropped_edges), e.g. {dropped[:5]}: was the variant rebuilt with other ids?")
        ROUTING[net, guard] = dict(dests=dests, near=demand.net_near_sets(net, guard))
    return ROUTING[net, guard]


def controller_outputs(cfg, run_dir, ctl, log, wall_s):
    """The controller's columns and checks of one run; saves its record in controller.json."""
    r, rec = cfg["run"], ctl.record()
    n, tt = rec["n_vehicles"], ctl.teleport_times
    starts, ends = demand.teleport_events(log)
    mid_log = demand.mid_teleport_counts(starts, ends, [s[0] for s in ctl.steps])
    checks = dict(ctl.checks(), teleports_match_log=bool(
        rec["teleports"] == len(starts) == demand.teleport_count(log) and [s[2] for s in ctl.steps] == mid_log))
    (run_dir / "controller.json").write_text(json.dumps(
        dict(rec, wall_s=wall_s, log_teleports=demand.teleport_count(log), checks=checks, teleport_times=tt),
        indent=1) + "\n")
    # cars in mid-teleport after each step, over the measurement window warmup_s-end_s, as city_sweep.py
    mid_window = [s[2] for s in ctl.steps if s[0] >= r["warmup_s"]]
    cols = dict(grid_n_min=rec["n_min"], grid_n_max=rec["n_max"], grid_n_short_steps=rec["n_short_steps"],
                grid_teleports=rec["teleports"],
                grid_teleports_per_car_h_window=demand.teleports_per_car_hour(tt, n, r["warmup_s"], r["end_s"]),
                grid_teleports_per_car_h_run=demand.teleports_per_car_hour(tt, n, 0, r["end_s"]),
                grid_mid_teleport_mean_window=sum(mid_window) / len(mid_window) if mid_window else math.nan,
                grid_mid_teleport_max=rec["mid_teleport_max"],
                grid_retargets=rec["retargets"], grid_guard_retargets=rec["guard_retargets"],
                grid_retarget_failed=rec["retarget_failed"], grid_reinserted=rec["reinserted"])
    return cols, checks


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
                  "controller": cfg["controller"], "rerouting": cfg["rerouting"],
                  "measure": dict(cfg["measure"], variance_block_used_s=block_s)}
    runner.write_manifest(run_dir, run_id, cfg, parameters)
    c, routing = cfg["controller"], net_routing(cfg, variant)
    ctl = demand.ConstantDensity(n, routing["dests"], seed + c["seed_offset"], c["retarget_at_remaining_edges"],
                                 near=routing["near"], step_s=cfg["run"]["step_s"])
    t0 = time.time()
    log, checks = runner.run_traci(run_dir, ctl, allow_teleport=cfg["run"].get("allow_teleport", False))
    wall_s = round(time.time() - t0, 1)
    ctl_cols, ctl_checks = controller_outputs(cfg, run_dir, ctl, log, wall_s)
    rec = ctl.record()
    print(f"{run_id:<30} N {rec['n_min']}-{rec['n_max']} (target {n})  arrived {rec['arrived']}  "
          f"teleports {rec['teleports']}  guard {rec['guard_retargets']}  reinserted {rec['reinserted']}  "
          f"wall {wall_s} s", flush=True)
    m = cfg["measure"]
    fcd = run_dir / "fcd.xml"
    measured, net_checks, series = measurements.network_summary(
        fcd, n, meta["lane_length_m"], cfg["run"]["warmup_s"], m["jam_speed_mps"],
        m["timeseries_every_s"], block_s=block_s,
        reference_length_m=meta["baseline_lane_length_m"], summary_xml=run_dir / "summary.xml")
    results.write_timeseries(run_id, series, cfg)
    measured.update(ctl_cols)  # grid_ columns: N over the run, teleports (T3-D11), mid-teleport, re-targets
    checks.update(ctl_checks)
    if not cfg["run"].get("keep_fcd", False):
        fcd.unlink()
    extra = ("congested_fraction_var_step", "density_ref_veh_km")
    measured = {("grid_" + k if k in extra else k): v for k, v in measured.items()}
    summary = dict(measured, scenario=cfg["scenario"], model=cfg["model"], variant=variant,
                   seed=seed, grid_network_vehicles=n)
    return runner.finish(run_dir, run_id, summary, {**checks, **net_checks})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, help="configs/<group>/<name>.toml")
    args = ap.parse_args()
    runner._import_traci()   # demand imports sumolib and traci from $SUMO_HOME/tools (GUIDE section 1)
    cfg = config.load(args.config)
    check_config(cfg)
    for variant in cfg["sweep"]["variants"]:   # a broken net stops the sweep before any run
        net_routing(cfg, variant)

    rows = []
    for variant in cfg["sweep"]["variants"]:
        for n in cfg["sweep"]["vehicles"]:
            for seed in cfg["sweep"]["seeds"]:
                s = run_one(cfg, variant, n, seed)
                rows.append(s)
                failed = [k for k, ok in s["checks"].items() if not ok]
                print(f"{s['run_id']:<30} k_ref={s['grid_density_ref_veh_km']:6.1f}  "
                      f"v={s['mean_speed_mps']:5.2f} m/s  q={s['flow_veh_h']:6.0f} veh/h  "
                      f"phi={s['congested_fraction']:.2f}  chi={s['congested_fraction_var']:.5f}  "
                      f"{'ok' if s['valid'] else 'INVALID: ' + ', '.join(failed)}")

    out = results.write_summary(rows, cfg)
    print(f"wrote {out.relative_to(ROOT)} and {len(rows)} time series in "
          f"{out.with_suffix('').relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
