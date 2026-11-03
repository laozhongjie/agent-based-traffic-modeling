"""City-network density sweep with task 4's constant-density controller: build, run, measure.

For every density in [sweep] densities_veh_km and seed in [sweep] seeds, plus the free-flow
reference run ([measure] reference_density_veh_km, reference_seed), this script
  1. checks the config and the net: guard_m must exceed the farthest a car drives in one step,
     every car edge must be reachable from every other one (destinations are drawn uniformly),
     and the settledness blocks must lie inside the measurement window (a warning otherwise);
  2. writes runs/<run_prefix>_k<k>_s<seed>/: N = round(k x total lane length / 1000) cars at
     rest, spread evenly over all car lanes (demand.initial_routes, as task 3), edgeData at the
     criterion period, and a sumocfg with the rerouting device of [rerouting] and the teleport
     setting of [run];
  3. runs SUMO through TraCI with demand.ConstantDensity (runner.run_traci) in [sweep] jobs
     parallel worker processes, and saves the controller's record in the run folder:
     controller.json (counts, checks, teleport start times, wall time) and
     controller_steps.csv.gz (cars on a lane and in mid-teleport after every step);
  4. measures every run but the reference with measurements.city_summary over
     [run] warmup_s-end_s, adds the controller's outputs (N check, teleports per car-hour, cars in
     mid-teleport) and the T3-D9 settledness check on [settle] blocks, and writes summary.json;
  5. writes results/city/<name>.csv (one row per run), results/city/<name>_blocks.csv (one row
     per run and block, the reference included: flow, teleports per car-hour, cars in
     mid-teleport, N) and results/city/<name>/<run_id>.csv (time series).

Usage (from the repository root):
    python scripts/city_sweep.py --config configs/city/bugis_all_controller.toml
Smoke run: options that change the experiment (--densities, --seeds, --end-s, --warmup-s,
--block-s) need their own --prefix and --name, both different from the config's. They go into
each manifest, and the result tables go to runs/<prefix>_results/ (git-ignored) instead of
results/city/:
    python scripts/city_sweep.py --config configs/city/bugis_all_controller.toml --densities 10 \
        --seeds 1 --end-s 1200 --warmup-s 600 --block-s 300 --prefix ctl_smoke_city_bugis_all \
        --name ctl_smoke_bugis_all_controller
--jobs and --verify-routes are free. --measure-only measures finished runs again without
running SUMO.

Planning variants (T4-D2, ruled by C 2026-10-27, member D's ask): in a copy of the config with
its own name and run_prefix, set [network] net_file to the variant, baseline_net_file to the
baseline net (e.g. "scenarios/city/bugis_all.net.xml") and variant to the variant's name (it
fills the results' `variant` column). N then comes from the baseline's lane length, N = round(k x
baseline lane length / 1000), and destinations are drawn from the baseline's car edges that the
variant still has (demand.baseline_destinations), so a closure or a new link changes the roads,
not the number of cars or the trips: a new link is never a destination. Runs are labelled by the
baseline's k (city_k_target); flow, the measured density and v_ref use the variant's own lanes,
and each variant runs its own free-flow reference. The script stops when a net has lanes that
ban cars (close a road by deleting its edge), when more than [network] max_dropped_edges
(default 5) baseline edges are missing from the variant (a rebuilt net renames edges), when the
two nets' measurement periods differ, and when an existing run folder of the same prefix was
made on another net or baseline. The results add city_baseline_net, city_k_variant (1000 N / the
variant's lane length: the target-side counterpart of density_veh_km), city_baseline_lane_length_m,
city_n_destinations, city_new_edges and city_new_edges_vref_own (new edges with their own v_ref
from the variant's reference run).
"""
import argparse
import gzip
import json
import math
import os
import shutil
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

from traffic_project import ROOT, config, demand, measurements, results, runner
from traffic_project import congestion as cg
from traffic_project.io import write_csv

CTX = {}   # network data for the worker processes (passed to each by _init_worker)
CONTROLLER_TAG = "task 4 demand.ConstantDensity"
BLOCK_COLUMNS = ["run_id", "seed", "city_k_target", "reference", "block_start_s", "block_end_s",
                 "flow_veh_h", "teleports", "teleports_per_car_h", "mid_teleport_mean",
                 "n_min", "n_max"]
# CLI overrides: (argument, config table, key, conversion, changes the experiment)
OVERRIDES = [("densities", "sweep", "densities_veh_km", lambda s: [float(x) for x in s.split(",")], True),
             ("seeds", "sweep", "seeds", lambda s: [int(x) for x in s.split(",")], True),
             ("end_s", "run", "end_s", int, True),
             ("warmup_s", "run", "warmup_s", int, True),
             ("block_s", "settle", "block_s", int, True),
             ("jobs", "sweep", "jobs", int, False),
             ("prefix", "sweep", "run_prefix", str, False)]


def parse_args():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", required=True, help="configs/city/<name>.toml")
    ap.add_argument("--densities", help="smoke run: override [sweep] densities_veh_km, comma-separated (veh/km)")
    ap.add_argument("--seeds", help="smoke run: override [sweep] seeds, comma-separated")
    ap.add_argument("--end-s", type=int, help="smoke run: override [run] end_s (s)")
    ap.add_argument("--warmup-s", type=int, help="smoke run: override [run] warmup_s (s)")
    ap.add_argument("--block-s", type=int, help="smoke run: override [settle] block_s (s)")
    ap.add_argument("--jobs", type=int, help="override [sweep] jobs")
    ap.add_argument("--prefix", help="override [sweep] run_prefix")
    ap.add_argument("--name", help="override the config name (names the result files)")
    ap.add_argument("--verify-routes", action="store_true",
                    help="controller also reads every live route every step and counts cache misses (slow)")
    ap.add_argument("--measure-only", action="store_true", help="measure finished runs, run nothing")
    return ap.parse_args()


def apply_overrides(cfg, a):
    """Apply the CLI overrides to cfg; return (overrides for the manifests, smoke run?)."""
    over, smoke = {}, False
    formal_prefix, formal_name = cfg["sweep"]["run_prefix"], cfg["name"]
    for key, table, field, conv, changes in OVERRIDES:
        value = getattr(a, key)
        if value is not None:
            cfg[table][field] = conv(value) if isinstance(value, str) else value
            over[f"{table}.{field}"] = cfg[table][field]
            smoke |= changes
    if a.name:
        cfg["name"] = over["name"] = a.name
    if smoke and (cfg["sweep"]["run_prefix"] == formal_prefix or cfg["name"] == formal_name):
        raise SystemExit("--densities, --seeds, --end-s, --warmup-s and --block-s change the experiment: "
                         "give them a --prefix and a --name of their own, different from the config's")
    if smoke:
        over["smoke_run"] = True
    if a.verify_routes:
        over["verify_routes"] = True
    return over, smoke


def check_config(cfg):
    """Stop on settings that would break the controller's guarantees; warn on a settle window
    that does not measure what T3-D9 says."""
    c, r, v, st = cfg["controller"], cfg["run"], cfg["vehicle"], cfg["settle"]
    reach = v["maxSpeed"] * r["step_length_s"]
    if not c["guard_m"] > reach:
        raise SystemExit(f"[controller] guard_m = {c['guard_m']} m must exceed maxSpeed x step_length_s = "
                         f"{reach:g} m, the farthest a car drives in one step, or cars can arrive")
    if c["destination"] != "uniform_edge":
        raise SystemExit(f"[controller] destination = {c['destination']!r}: only 'uniform_edge' is implemented")
    ok = demand.settle_window_ok(r["end_s"], r["warmup_s"], st["block_s"])
    if not ok:
        print(f"WARNING: end_s = {r['end_s']}, warmup_s = {r['warmup_s']}, block_s = {st['block_s']}: the last two "
              f"blocks are not the run's tail inside the measurement window; city_settle_window_ok = false", flush=True)
    return ok


def _car_lane_m(lanes):
    """Total length (m) of the lanes that allow passenger cars, from demand.car_lanes()."""
    return float(sum(length * len(idx) for _, length, idx in lanes))


def _same_network(meta, run_dir):
    """Stop when an existing run folder was made on another net or baseline: a copied config that
    kept name and run_prefix would otherwise overwrite another sweep's runs and results."""
    if meta.get("net") != str(CTX["net_path"]) or meta.get("baseline") != CTX["baseline"]:
        raise SystemExit(f"{run_dir} holds a run on {meta.get('net')} (baseline "
                         f"{(meta.get('baseline') or {}).get('net')}), but this config uses {CTX['net_path']} "
                         f"(baseline {(CTX['baseline'] or {}).get('net')}): give the config its own name and run_prefix")


def load_network(cfg):
    net_path = ROOT / cfg["network"]["net_file"]
    net = cg.read_net(net_path)
    lanes = demand.car_lanes(net_path)
    outside = demand.outside_largest_scc(demand.car_successors(net_path))
    if outside:
        raise SystemExit(f"{net_path.name}: {len(outside)} car edges cannot be reached from every other car edge "
                         f"(e.g. {outside[:5]}); a car sent there could not be re-targeted and would arrive")
    lane_m = float((net.edges.length * net.edges.lanes).sum())
    CTX.update(cfg=cfg, net_path=net_path, period=cg.cycle_period(net, cfg["measure"]["period_s"]),
               lane_m=lane_m, lanes=lanes, dests=sorted(e for e, *_ in lanes),
               n_lane_m=lane_m, baseline=None)   # n_lane_m: the lane length that sets N
    CTX["variant"] = ""
    base_file = cfg["network"].get("baseline_net_file")
    if base_file:   # planning variant (T4-D2): N and destinations from the baseline net
        nw = cfg["network"]
        if not nw.get("variant"):
            raise SystemExit("[network] variant must name the planning variant when baseline_net_file is set")
        base_path = ROOT / base_file
        base = cg.read_net(base_path)
        base_lanes = demand.car_lanes(base_path)
        base_m = float((base.edges.length * base.edges.lanes).sum())
        for name, total, car_m in ((net_path.name, lane_m, _car_lane_m(lanes)),
                                   (base_path.name, base_m, _car_lane_m(base_lanes))):
            if abs(total - car_m) > 0.5:   # m
                raise SystemExit(f"{name}: {total - car_m:.1f} m of lanes ban passenger cars, so the lane length "
                                 f"that sets N and k is not the car-lane length; close a road by deleting its edge")
        base_period = cg.cycle_period(base, cfg["measure"]["period_s"])
        if base_period != CTX["period"]:
            raise SystemExit(f"measurement period {CTX['period']:g} s here, {base_period:g} s on the baseline: "
                             f"the congested fractions would not compare")
        dests, dropped, new = demand.baseline_destinations(base_lanes, lanes)
        if not dests:
            raise SystemExit(f"{net_path.name} shares no car edge with the baseline {base_path.name}")
        limit = nw.get("max_dropped_edges", 5)
        if len(dropped) > limit:
            raise SystemExit(f"{len(dropped)} baseline car edges are missing from {net_path.name} (limit {limit}, "
                             f"[network] max_dropped_edges), e.g. {dropped[:5]}: was the variant rebuilt with other ids?")
        CTX.update(dests=dests, n_lane_m=base_m, variant=nw["variant"],
                   baseline=dict(net=str(base_path), lane_length_m=base_m, n_destinations=len(dests),
                                 dropped_edges=dropped, new_edges=new))
        print(f"baseline {base_path.name}: N from its lane length {base_m / 1000:.2f} km "
              f"(this net {lane_m / 1000:.2f} km); {len(dests)} destination edges; baseline edges missing "
              f"here: {dropped if len(dropped) <= 10 else len(dropped)}; new edges here, never destinations: "
              f"{new if len(new) <= 10 else len(new)}", flush=True)


def sumocfg_text(cfg, run_dir, seed):
    r, rr = cfg["run"], cfg["rerouting"]
    ttt = r["time_to_teleport_s"] if r.get("allow_teleport", False) else -1
    q = r.get("queue_output_s")   # SUMO's aggregated queue-output for city_measures.py; absent = none
    queue = (f'<queue-output value="queue{q:g}.xml.gz"/><queue-output.aggregation value="{q:g}"/>'
             if q else "")
    return f"""<configuration>
    <input>
        <net-file value="{os.path.relpath(CTX['net_path'], run_dir)}"/>
        <route-files value="vehicles.rou.xml"/>
        <additional-files value="edgedata.add.xml"/>
    </input>
    <time><begin value="0"/><end value="{r['end_s']}"/><step-length value="{r['step_length_s']}"/></time>
    <random_number><seed value="{seed}"/></random_number>
    <processing>
        <collision.action value="warn"/>
        <time-to-teleport value="{ttt}"/>
        <device.rerouting.probability value="{rr['probability']}"/>
        <device.rerouting.period value="{rr['period_s']}"/>
        <device.rerouting.adaptation-interval value="{rr['adaptation_interval_s']}"/>
        <device.rerouting.adaptation-steps value="{rr['adaptation_steps']}"/>
    </processing>
    <output><summary-output value="summary.xml"/>{queue}</output>
</configuration>
"""


def build(cfg, k, seed, overrides):
    """Write one run folder and its manifest; return (run_id, run_dir, N)."""
    run_id = f"{cfg['sweep']['run_prefix']}_k{k:g}_s{seed}"
    run_dir = ROOT / "runs" / run_id
    if (run_dir / "meta.json").exists():
        old_meta = json.loads((run_dir / "meta.json").read_text())
        old = old_meta.get("controller", "")
        if not old.startswith(CONTROLLER_TAG):
            raise SystemExit(f"{run_dir} holds another script's run ({old!r}); choose another --prefix")
        _same_network(old_meta, run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    n = round(k * CTX["n_lane_m"] / 1000)   # the baseline's lane length for a planning variant (T4-D2)
    r = cfg["run"]
    (run_dir / "vehicles.rou.xml").write_text(
        demand.initial_routes(CTX["lanes"], n, cfg["vehicle"], r["placement_jitter_m"], seed))
    edfile = cfg["inputs"]["edgedata_file"].format(period=CTX["period"])
    (run_dir / "edgedata.add.xml").write_text(cg.edgedata_additional(CTX["period"], file=edfile))
    (run_dir / "run.sumocfg").write_text(sumocfg_text(cfg, run_dir, seed))
    meta = dict(net=str(CTX["net_path"]), tag=cfg["network"]["tag"], k_target=k, seed=seed, n_vehicles=n,
                lane_length_m=CTX["lane_m"], period_s=CTX["period"], end_s=r["end_s"], controller=CONTROLLER_TAG)
    if CTX["baseline"]:
        meta["baseline"] = CTX["baseline"]
    (run_dir / "meta.json").write_text(json.dumps(meta, indent=1) + "\n")
    parameters = {"density_veh_km": k, "seed": seed, "n_vehicles": n, "lane_length_m": CTX["lane_m"],
                  "network": cfg["network"], "run": r, "controller": cfg["controller"],
                  "rerouting": cfg["rerouting"], "settle": cfg["settle"], "vehicle": cfg["vehicle"],
                  "measure": cfg["measure"], "overrides": overrides}
    if CTX["baseline"]:
        parameters["baseline"] = CTX["baseline"]
    runner.write_manifest(run_dir, run_id, cfg, parameters)
    return run_id, run_dir, n


def _init_worker(ctx):
    """Give a worker process the network data (works under both 'fork' and 'spawn')."""
    CTX.update(ctx)


def simulate(job):
    """Worker: run one folder with the controller and save the controller's record."""
    run_id, run_dir, seed, n, verify = job
    cfg = CTX["cfg"]
    c, r = cfg["controller"], cfg["run"]
    ctl = demand.ConstantDensity(n, CTX["dests"], seed + c["seed_offset"], c["retarget_at_remaining_edges"],
                                 near=CTX["near"], step_s=r["step_length_s"], verify_routes=verify)
    t0 = time.time()
    log, checks = runner.run_traci(run_dir, ctl, allow_teleport=r.get("allow_teleport", False))
    rec = dict(ctl.record(), wall_s=round(time.time() - t0, 1), log_teleports=demand.teleport_count(log),
               checks={**checks, **ctl.checks()}, teleport_times=ctl.teleport_times)
    with gzip.open(run_dir / "controller_steps.csv.gz", "wt") as f:
        f.write(",".join(demand.STEP_FIELDS) + "\n")
        f.writelines(f"{t:g},{on},{tp},{st},{ar}\n" for t, on, tp, st, ar in ctl.steps)
    (run_dir / "controller.json").write_text(json.dumps(rec, indent=1) + "\n")
    return run_id, rec


def read_steps(run_dir):
    with gzip.open(run_dir / "controller_steps.csv.gz", "rt") as f:
        next(f)
        return np.array([[float(x) for x in line.split(",")] for line in f]).reshape(-1, len(demand.STEP_FIELDS))


def controller_outputs(cfg, run_dir, run_id, k, seed, reference, window_ok):
    """Controller-based measures of one run: (summary columns, checks, block rows, wall time s)."""
    r, st = cfg["run"], cfg["settle"]
    end, warm, block = r["end_s"], r["warmup_s"], st["block_s"]
    rec = json.loads((run_dir / "controller.json").read_text())
    n, tt = rec["n_vehicles"], rec["teleport_times"]
    s = measurements.read_summary_xml(run_dir / cfg["inputs"]["summary_file"])
    lane_km = CTX["lane_m"] / 1000
    flow_t = np.where(s[:, 1] > 0, s[:, 1] / lane_km * np.maximum(s[:, 3], 0) * 3.6, 0.0)   # veh/h per lane
    flows = demand.block_means(s[:, 0], flow_t, block, end)
    steps = read_steps(run_dir)
    times, n_t, tp_t = steps[:, 0], steps[:, 1] + steps[:, 2], steps[:, 2]
    mid = demand.block_means(times, tp_t, block, end)
    starts, ends = demand.teleport_events((run_dir / "log.txt").read_text(errors="replace"))
    mid_log = demand.mid_teleport_counts(starts, ends, times)
    ratio = demand.settle_ratio(flows)
    settled = demand.is_settled(ratio, st["ratio_min"], st["ratio_max"])
    window = times >= warm
    blocks = []
    for b, (q, m) in enumerate(zip(flows, mid)):
        b0, b1 = b * block, (b + 1) * block
        inb = (times >= b0) & (times < b1)
        blocks.append(dict(run_id=run_id, seed=seed, city_k_target=k, reference=reference,
                           block_start_s=b0, block_end_s=b1, flow_veh_h=round(q, 3),
                           teleports=sum(b0 <= t < b1 for t in tt),
                           teleports_per_car_h=round(demand.teleports_per_car_hour(tt, n, b0, b1), 5),
                           mid_teleport_mean=round(m, 4), n_min=int(n_t[inb].min()), n_max=int(n_t[inb].max())))
    # _window: over the measurement window warmup_s-end_s (the number to quote); _run: over 0-end_s
    cols = dict(city_k_target=k, city_n_vehicles=n, city_n_min=rec["n_min"], city_n_max=rec["n_max"],
                city_n_short_steps=rec["n_short_steps"], city_teleports=rec["teleports"],
                city_teleports_per_car_h_window=demand.teleports_per_car_hour(tt, n, warm, end),
                city_teleports_per_car_h_run=demand.teleports_per_car_hour(tt, n, 0, end),
                city_mid_teleport_mean_window=float(tp_t[window].mean()), city_mid_teleport_max=int(tp_t.max()),
                city_flow_prev_block_veh_h=flows[-2] if len(flows) > 1 else math.nan,
                city_flow_last_block_veh_h=flows[-1] if flows else math.nan,
                city_settle_ratio=ratio, city_settled=settled, city_settle_window_ok=window_ok,
                city_retargets=rec["retargets"], city_guard_retargets=rec["guard_retargets"],
                city_reinserted=rec["reinserted"], city_retarget_failed=rec["retarget_failed"],
                city_route_cache_mismatches=rec["route_cache_mismatches"])
    if CTX["baseline"]:   # planning variant (T4-D2): k is the baseline's; also N / the variant's lane length
        cols.update(city_baseline_net=os.path.relpath(CTX["baseline"]["net"], ROOT),
                    city_k_variant=1000 * n / CTX["lane_m"], city_baseline_lane_length_m=CTX["n_lane_m"],
                    city_n_destinations=len(CTX["dests"]))
    checks = dict(rec["checks"])
    checks["teleports_match_log"] = bool(rec["teleports"] == len(starts) == rec["log_teleports"]
                                         and list(tp_t.astype(int)) == mid_log)
    if st["in_valid"]:
        checks["settled"] = settled and window_ok
    return cols, checks, blocks, rec["wall_s"]


def _results_paths(cfg):
    """The files results.write_summary / write_timeseries and this script write for cfg."""
    base = ROOT / "results" / cfg["scenario"]
    return [base / f"{cfg['name']}.csv", base / f"{cfg['name']}_blocks.csv", base / cfg["name"]]


def main():
    a = parse_args()
    cfg = config.load(a.config)
    overrides, smoke = apply_overrides(cfg, a)
    if smoke and any(p.exists() for p in _results_paths(cfg)):
        raise SystemExit(f"results/{cfg['scenario']}/ already holds files named {cfg['name']}; choose another --name")
    window_ok = check_config(cfg)
    load_network(cfg)
    sw, m = cfg["sweep"], cfg["measure"]
    ref_key = (float(m["reference_density_veh_km"]), m["reference_seed"])
    keys = [ref_key] + [(float(k), s) for k in sorted(sw["densities_veh_km"], reverse=True) for s in sw["seeds"]]
    runs = {}
    if a.measure_only:
        for k, s in keys:
            run_id = f"{sw['run_prefix']}_k{k:g}_s{s}"
            meta = json.loads((ROOT / "runs" / run_id / "meta.json").read_text())
            _same_network(meta, ROOT / "runs" / run_id)
            runs[(k, s)] = (run_id, ROOT / "runs" / run_id, meta["n_vehicles"])
    else:
        CTX["near"] = demand.net_near_sets(CTX["net_path"], cfg["controller"]["guard_m"])
        for k, s in keys:
            runs[(k, s)] = build(cfg, k, s, overrides)
        jobs = [(run_id, d, s, n, a.verify_routes) for (k, s), (run_id, d, n) in runs.items()]
        jobs.sort(key=lambda j: -j[3])   # slow, dense runs first
        workers = min(sw["jobs"], len(jobs))
        print(f"{len(jobs)} runs, lane length {CTX['lane_m'] / 1000:.2f} km, period {CTX['period']:g} s, "
              f"{workers} workers", flush=True)
        with Pool(workers, initializer=_init_worker, initargs=(dict(CTX),)) as pool:
            for run_id, rec in pool.imap_unordered(simulate, jobs):
                print(f"{run_id:<34} N {rec['n_min']}-{rec['n_max']} (target {rec['n_vehicles']})  "
                      f"arrived {rec['arrived']}  teleports {rec['teleports']}  guard {rec['guard_retargets']}  "
                      f"reinserted {rec['reinserted']}  wall {rec['wall_s']} s", flush=True)

    ref_id, ref_dir, _ = runs[ref_key]
    edname = cfg["inputs"]["edgedata_file"].format(period=CTX["period"])
    summ = cfg["inputs"]["summary_file"]
    rows, blocks = [], []
    new_cols = {}
    if CTX["baseline"]:   # T4-D2: did each new link get its own v_ref in this variant's reference run?
        new = CTX["baseline"]["new_edges"]
        ref_df = cg.read_edgedata(ref_dir / edname)
        win = ref_df[(ref_df.begin >= cfg["run"]["warmup_s"]) & ref_df.edge.isin(new)]
        sampled = win.groupby("edge").sampledSeconds.sum()
        new_cols = dict(city_new_edges=len(new),
                        city_new_edges_vref_own=int((sampled >= m["vref_min_sampled_s"]).sum()))
    for (k, s), (run_id, d, n) in runs.items():
        reference = (k, s) == ref_key
        cols, checks, b, wall = controller_outputs(cfg, d, run_id, k, s, reference, window_ok)
        blocks += b
        if reference:   # not measured with the criterion; its record shows the controller checks
            runner.finish(d, run_id, dict(cols, reference=True, city_wall_s=wall), checks)
            continue
        meas, mchecks, series = measurements.city_summary(
            d / edname, ref_dir / edname, CTX["net_path"], d / summ, m, cfg["run"]["warmup_s"],
            ref_summary_xml=ref_dir / summ, n_vehicles=n)
        if cfg["inputs"].get("write_timeseries"):
            results.write_timeseries(run_id, series, cfg)
        # reported, not a validity check: the reference run's v_ref must cover > vref_coverage_min (proposal section 4)
        cover_ok = bool(meas["city_vref_coverage"] > m["vref_coverage_min"])
        row = dict(meas, scenario=cfg["scenario"], model=cfg["model"], variant=CTX["variant"], seed=s,
                   city_net=cfg["network"]["tag"], city_vref_coverage_ok=cover_ok, **cols, **new_cols)
        row = runner.finish(d, run_id, dict(row, city_wall_s=wall), {**checks, **mchecks})
        row.pop("city_wall_s")   # in summary.json and controller.json, not in the results table
        rows.append(row)
        failed = [c for c, ok in row["checks"].items() if not ok]
        print(f"{run_id:<34} k={row['density_veh_km']:5.1f}  q={row['flow_veh_h']:6.1f} veh/h per lane  "
              f"tp/car-h={cols['city_teleports_per_car_h_window']:.3f}  settle={cols['city_settle_ratio']:.3f}  "
              f"{'ok' if row['valid'] else 'INVALID: ' + ', '.join(failed)}", flush=True)
    rows.sort(key=lambda r: (r["city_k_target"], r["seed"]))
    path = results.write_summary(rows, cfg)
    bpath = path.with_name(f"{cfg['name']}_blocks.csv")
    write_csv(sorted(blocks, key=lambda b: (b["city_k_target"], b["seed"], b["block_start_s"])), bpath, BLOCK_COLUMNS)
    written = _results_paths(cfg)
    if smoke:   # smoke tables stay out of results/ (in git): move them next to the runs
        out = ROOT / "runs" / f"{sw['run_prefix']}_results"
        out.mkdir(parents=True, exist_ok=True)
        for p in written:
            if p.exists():
                target = out / p.name
                if target.is_dir():
                    shutil.rmtree(target)
                elif target.exists():
                    target.unlink()
                shutil.move(str(p), str(target))
        written = [out / p.name for p in written]
    print("wrote", ", ".join(str(Path(p).relative_to(ROOT)) for p in written if Path(p).exists()))


if __name__ == "__main__":
    main()
