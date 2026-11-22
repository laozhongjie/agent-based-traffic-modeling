"""Run ring-road vehicle-removal interventions through TraCI.

This is intentionally separate from ring_sweep.py. NaSch and IDM retain their
native SUMO car-following models; the existing Python OVM controller is composed
with the removal controller when an [ovm] table is present.

Removal events may be supplied on the command line::

    python scripts/ring_removal_experiment.py \
        --config configs/ring/NaSch_1200_removal.toml \
        --remove 900:3 --remove 1200:3

or in TOML as repeated ``[[removal.events]]`` tables with ``time_s`` and
``count`` keys. The script writes a normal instantaneous time series for every
run, an interventions.json record beside the FCD output, and a segment summary
CSV with one steady-density row before and after each removal.
"""
import argparse
import csv
import importlib.util
import json
import math
import re
from copy import deepcopy
from pathlib import Path

from traffic_project import ROOT, config, io, results, runner


def _load_build_run():
    path = ROOT / "scenarios" / "ring" / "build_run.py"
    spec = importlib.util.spec_from_file_location("ring_build_run", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BUILD_RUN = _load_build_run()


def parse_removal(value):
    """Parse TIME:COUNT from the command line."""
    try:
        time_text, count_text = value.split(":", 1)
        event = {"time_s": float(time_text), "count": int(count_text)}
    except (ValueError, TypeError) as exc:
        raise argparse.ArgumentTypeError(
            f"removal must have the form TIME:COUNT, got {value!r}"
        ) from exc
    return event


def validate_events(events, cfg, vehicle_counts):
    """Return normalized, sorted events after validating the experiment."""
    normalized = [
        {"time_s": float(event["time_s"]), "count": int(event["count"])}
        for event in events
    ]
    normalized.sort(key=lambda event: event["time_s"])

    if not normalized:
        raise ValueError("define at least one removal event")

    times = [event["time_s"] for event in normalized]
    if len(times) != len(set(times)):
        raise ValueError("removal event times must be unique")

    warmup = float(cfg["run"]["warmup_s"])
    end = float(cfg["run"]["end_s"])
    step = float(cfg["run"]["step_s"])
    for event in normalized:
        time_s, count = event["time_s"], event["count"]
        if not warmup < time_s < end:
            raise ValueError(
                f"removal time {time_s:g} must be after warm-up {warmup:g} "
                f"and before end {end:g}"
            )
        if count <= 0:
            raise ValueError("each removal count must be positive")
        if not math.isclose(time_s / step, round(time_s / step), abs_tol=1e-9):
            raise ValueError(
                f"removal time {time_s:g} is not aligned to step_s={step:g}"
            )

    total_removed = sum(event["count"] for event in normalized)
    minimum_remaining = 2 if cfg["model"].upper() == "OVM" else 1
    for n in vehicle_counts:
        if n - total_removed < minimum_remaining:
            raise ValueError(
                f"events remove {total_removed} vehicles, leaving only "
                f"{n - total_removed} from N={n}; {cfg['model']} requires at "
                f"least {minimum_remaining}"
            )
    return normalized


def event_variant(events):
    """Return a stable run-id tag for an intervention schedule."""
    def number_tag(value):
        return f"{value:g}".replace("-", "m").replace(".", "p")

    return "rem_" + "_".join(
        f"t{number_tag(event['time_s'])}_n{event['count']}" for event in events
    )


def _vehicle_sort_key(vehicle_id):
    """Natural order keeps v2 before v10 and preserves ring order."""
    match = re.fullmatch(r"(.*?)(\d+)", vehicle_id)
    if match:
        return match.group(1), int(match.group(2))
    return vehicle_id, -1


def make_removal_controller(events):
    """Return a runner.run_traci callback and mutable event records.

    Vehicles are created in physical ring order and cannot overtake on the
    single lane. Selecting evenly through their natural ID order therefore
    avoids removing one spatially clustered block.
    """
    completed = set()
    actual = []

    def controller(conn, time_s):
        for index, event in enumerate(events):
            if index in completed or time_s + 1e-9 < event["time_s"]:
                continue

            ids = sorted(conn.vehicle.getIDList(), key=_vehicle_sort_key)
            count = event["count"]
            if count > len(ids):
                raise RuntimeError(
                    f"cannot remove {count} vehicles at {time_s:g} s; "
                    f"only {len(ids)} remain"
                )

            selected = [ids[i * len(ids) // count] for i in range(count)]
            for vehicle_id in selected:
                conn.vehicle.remove(vehicle_id)

            completed.add(index)
            actual.append({
                "event_index": index,
                "scheduled_time_s": event["time_s"],
                "actual_time_s": float(time_s),
                "vehicles_before": len(ids),
                "vehicles_after": len(ids) - count,
                "removed_vehicle_ids": selected,
            })

    return controller, completed, actual


def combine_controllers(*controllers):
    active = [controller for controller in controllers if controller is not None]

    def combined(conn, time_s):
        for controller in active:
            controller(conn, time_s)

    return combined


def resolved_initial(cfg):
    initial = dict(cfg.get("initial", {}))
    initial.setdefault("mode", "uniform_jitter")
    if initial["mode"] == "uniform_jitter":
        jitter = initial.get("jitter_m", cfg["run"].get("jitter_m"))
        if jitter is not None:
            initial["jitter_m"] = jitter
    return initial


def read_observations(fcd_path, length_m, jam_speed_mps, sample_every_s):
    """Read FCD once and return per-step observations plus sampled output."""
    observations, series = [], []
    for time_s, vehicles in io.iter_fcd(fcd_path):
        speeds = [vehicle["speed"] for vehicle in vehicles]
        count = len(speeds)
        if not count:
            continue
        mean_speed = sum(speeds) / count
        phi = sum(speed < jam_speed_mps for speed in speeds) / count
        density = 1000 * count / length_m
        observation = {
            "time_s": time_s,
            "vehicles": count,
            "density_veh_km": density,
            "mean_speed_mps": mean_speed,
            "flow_veh_h": density * mean_speed * 3.6,
            "congested_fraction": phi,
        }
        observations.append(observation)
        if math.isclose(
            time_s / sample_every_s,
            round(time_s / sample_every_s),
            abs_tol=1e-9,
        ):
            series.append({
                "time_s": time_s,
                "density_veh_km": density,
                "mean_speed_mps": round(mean_speed, 4),
                "flow_veh_h": round(density * mean_speed * 3.6, 2),
                "congested_fraction": round(phi, 4),
            })
    return observations, series


def segment_summaries(
    observations, events, actual_events, initial_n, cfg, run_id, seed, variant, settle_s
):
    """Summarize each constant-count interval separately."""
    warmup = float(cfg["run"]["warmup_s"])
    end = float(cfg["run"]["end_s"])
    step = float(cfg["run"]["step_s"])
    length = float(cfg["ring"]["length_m"])
    actual_times = [event["actual_time_s"] for event in actual_events]
    boundaries = [warmup] + actual_times + [end]
    removed_before = 0
    rows = []

    for index in range(len(boundaries) - 1):
        # The controller runs after simulationStep(). FCD at the event time
        # therefore still contains the pre-removal count; the new segment
        # starts on the following simulation step.
        start = (
            boundaries[index] + step + settle_s
            if index
            else boundaries[index]
        )
        stop = boundaries[index + 1]
        expected_n = initial_n - removed_before
        samples = [obs for obs in observations if start <= obs["time_s"] < stop]
        count_ok = bool(samples) and all(
            obs["vehicles"] == expected_n for obs in samples
        )

        if samples:
            mean_speed = sum(obs["mean_speed_mps"] for obs in samples) / len(samples)
            mean_phi = sum(obs["congested_fraction"] for obs in samples) / len(samples)
            phi_var = sum(
                (obs["congested_fraction"] - mean_phi) ** 2 for obs in samples
            ) / len(samples)
        else:
            mean_speed = mean_phi = phi_var = float("nan")

        density = 1000 * expected_n / length
        rows.append({
            "run_id": run_id,
            "model": cfg["model"],
            "variant": variant,
            "seed": seed,
            "segment_index": index,
            "start_s": start,
            "end_s": stop,
            "vehicles": expected_n,
            "density_veh_km": density,
            "mean_speed_mps": mean_speed,
            "flow_veh_h": density * mean_speed * 3.6,
            "congested_fraction": mean_phi,
            "congested_fraction_var": phi_var,
            "samples": len(samples),
            "count_ok": count_ok,
        })
        if index < len(events):
            removed_before += events[index]["count"]
    return rows


SEGMENT_COLUMNS = [
    "run_id", "model", "variant", "seed", "segment_index", "start_s", "end_s",
    "vehicles", "density_veh_km", "mean_speed_mps", "flow_veh_h",
    "congested_fraction", "congested_fraction_var", "samples", "count_ok",
]


def write_segment_summary(rows, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SEGMENT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def run_one(base_cfg, n, seed, events, variant, settle_s):
    cfg = deepcopy(base_cfg)
    cfg["variant"] = variant
    run_id, run_dir = BUILD_RUN.build(cfg, n, seed)

    parameters = {
        "vehicles": n,
        "seed": seed,
        "ring": cfg["ring"],
        "run": cfg["run"],
        "initial": resolved_initial(cfg),
        "vtype": cfg["vtype"],
        "measure": cfg["measure"],
        "removal": {"events": events, "settle_s": settle_s},
    }

    ovm_controller = None
    if cfg["model"].upper() == "OVM" and "ovm" in cfg:
        from traffic_project.ovm_traci import make_ovm_controller

        ovm = cfg["ovm"]
        parameters["ovm"] = ovm
        ovm_controller = make_ovm_controller(
            ring_length=cfg["ring"]["length_m"],
            dt=cfg["run"]["step_s"],
            alpha=ovm["alpha"],
            v_max=cfg["vtype"]["maxSpeed"],
            h_c=ovm["h_c"],
            h_scale=ovm["h_scale"],
            min_gap=cfg["vtype"]["minGap"],
            expected_vehicles=None,
        )

    removal_controller, completed, actual_events = make_removal_controller(events)
    controller = combine_controllers(ovm_controller, removal_controller)
    runner.write_manifest(run_dir, run_id, cfg, parameters)
    _, checks = runner.run_traci(run_dir, controller)
    checks["all_removal_events_fired"] = len(completed) == len(events)

    event_record = {
        "planned": events,
        "actual": actual_events,
        "all_events_fired": checks["all_removal_events_fired"],
    }
    (run_dir / "interventions.json").write_text(
        json.dumps(event_record, indent=2) + "\n"
    )

    fcd_path = run_dir / "fcd.xml"
    if not checks["sumo_exit_ok"] or not fcd_path.exists():
        raise RuntimeError(f"SUMO failed for {run_id}; inspect {run_dir / 'log.txt'}")

    measure = cfg["measure"]
    observations, series = read_observations(
        fcd_path,
        cfg["ring"]["length_m"],
        measure["jam_speed_mps"],
        measure["timeseries_every_s"],
    )
    results.write_timeseries(run_id, series, cfg)
    segments = segment_summaries(
        observations, events, actual_events, n, cfg, run_id, seed, variant, settle_s
    )
    checks["segment_vehicle_counts_ok"] = all(row["count_ok"] for row in segments)

    final = segments[-1]
    summary = {
        "scenario": cfg["scenario"],
        "model": cfg["model"],
        "variant": variant,
        "seed": seed,
        "density_veh_km": final["density_veh_km"],
        "mean_speed_mps": final["mean_speed_mps"],
        "flow_veh_h": final["flow_veh_h"],
        "congested_fraction": final["congested_fraction"],
        "congested_fraction_var": final["congested_fraction_var"],
        "ring_initial_vehicles": n,
        "ring_final_vehicles": final["vehicles"],
    }
    runner.finish(run_dir, run_id, summary, checks)
    return segments, checks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument(
        "--remove",
        action="append",
        type=parse_removal,
        default=[],
        metavar="TIME:COUNT",
        help="removal event; repeat for multiple times",
    )
    parser.add_argument(
        "--vehicles",
        type=int,
        nargs="+",
        help="optional subset of sweep vehicle counts for a pilot",
    )
    parser.add_argument(
        "--settle-s",
        type=float,
        help="discard this many seconds after each removal in segment summaries",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    cfg = config.load(args.config)
    vehicle_counts = args.vehicles or list(cfg["sweep"]["vehicles"])
    configured_events = cfg.get("removal", {}).get("events", [])
    events = validate_events(args.remove or configured_events, cfg, vehicle_counts)
    settle_s = args.settle_s
    if settle_s is None:
        settle_s = float(cfg.get("removal", {}).get("settle_s", 0.0))
    if settle_s < 0:
        parser.error("--settle-s must be non-negative")

    schedule_variant = event_variant(events)
    base_variant = str(cfg.get("variant", "")).strip()
    variant = f"{base_variant}_{schedule_variant}" if base_variant else schedule_variant
    seeds = list(cfg["sweep"]["seeds"])
    sigma = cfg["vtype"].get("sigma", "not used by this model")

    print(f"Model: {cfg['model']}")
    print(f"Ring length: {cfg['ring']['length_m']} m")
    print(f"Fixed sigma: {sigma}")
    print(f"Vehicle counts: {vehicle_counts}")
    print(f"Seeds: {seeds}")
    print(f"Events: {events}")
    print(f"Segment settling time: {settle_s:g} s")
    print(f"Variant: {variant}")
    print(f"Total runs: {len(vehicle_counts) * len(seeds)}")

    if args.dry_run:
        for n in vehicle_counts:
            for seed in seeds:
                print(
                    f"ring_{cfg['model'].lower()}_{variant}_"
                    f"L{int(cfg['ring']['length_m'])}_n{n}_s{seed}"
                )
        return

    all_segments = []
    for n in vehicle_counts:
        for seed in seeds:
            segments, checks = run_one(cfg, n, seed, events, variant, settle_s)
            all_segments.extend(segments)
            failed = [name for name, passed in checks.items() if not passed]
            print(
                f"{segments[0]['run_id']}: "
                f"{len(segments)} segments, "
                f"{'ok' if not failed else 'INVALID: ' + ', '.join(failed)}"
            )

    output = (
        ROOT / "results" / cfg["scenario"]
        / f"{cfg['name']}_{variant}_segments.csv"
    )
    write_segment_summary(all_segments, output)
    print(f"wrote {output.relative_to(ROOT)} ({len(all_segments)} segment rows)")


if __name__ == "__main__":
    main()
