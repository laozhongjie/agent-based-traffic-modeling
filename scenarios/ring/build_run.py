"""Place N vehicles on the ring and write one run's SUMO input files.

Vehicles start at rest. By default they are evenly spaced with a small seeded
offset (the existing IDM/OVM behaviour). Configurations may instead select
``initial.mode = "nasch_lattice"`` to place vehicles on whole NaSch cells.
Each vehicle's route starts on its own edge and repeats, so it keeps circling
for the whole run.

Usage (from the repository root):
    python scenarios/ring/build_run.py --config configs/ring/idm_sweep.toml --vehicles 30 --seed 1
Writes runs/<run-id>/vehicles.rou.xml and run.sumocfg, with
run-id = ring_<model>_L<length>_n<N>_s<seed>, and prints the run-id.
The network scenarios/ring/ring_<length>.net.xml must exist (see build_net.py).
"""
import argparse
import math
import os
import random
import re

from traffic_project import ROOT, config

N_EDGES = 4


def fcd_settings(run):
    """Return validated optional FCD sampling settings."""
    period = run.get("fcd_every_s")
    begin = run.get("fcd_begin_s")

    if period is None and begin is None:
        return None, None
    if period is None:
        raise ValueError("run.fcd_begin_s requires run.fcd_every_s")

    period = float(period)
    step = float(run["step_s"])
    begin = 0.0 if begin is None else float(begin)

    if period <= 0:
        raise ValueError("run.fcd_every_s must be positive")
    if period + 1e-12 < step:
        raise ValueError("run.fcd_every_s cannot be shorter than run.step_s")
    if not math.isclose(period / step, round(period / step), abs_tol=1e-9):
        raise ValueError("run.fcd_every_s must be an integer multiple of run.step_s")
    if begin < 0 or begin >= float(run["end_s"]):
        raise ValueError("run.fcd_begin_s must satisfy 0 <= begin < end_s")

    return period, begin


def run_variant(cfg):
    """Return a filesystem-safe optional run variant."""
    variant = str(cfg.get("variant", "")).strip()
    if not variant:
        return ""
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", variant).strip("-._")
    if not safe:
        raise ValueError(f"variant has no usable run-id characters: {variant!r}")
    return safe


def initial_positions(cfg, n, seed):
    """Return front-bumper positions around the ring in metres."""
    if n <= 0:
        raise ValueError("number of vehicles must be positive")

    length = float(cfg["ring"]["length_m"])
    run = cfg["run"]
    vtype = cfg["vtype"]

    initial = cfg.get("initial", {})
    mode = initial.get("mode", "uniform_jitter")

    if mode == "nasch_lattice":
        if vtype.get("carFollowModel") != "NaSch":
            raise ValueError(
                "initial.mode='nasch_lattice' requires carFollowModel='NaSch'"
            )

        dt = float(run["step_s"])
        if not math.isclose(dt, 1.0):
            raise ValueError(
                "the formal NaSch lattice configuration requires step_s = 1.0"
            )

        # For this NaSch setup:
        # accel = 7.5 m/s², dt = 1 s, so one cell is 7.5 m.
        cell_m = float(vtype["accel"]) * dt**2
        n_cells_float = length / cell_m
        n_cells = round(n_cells_float)

        if not math.isclose(n_cells_float, n_cells, abs_tol=1e-9):
            raise ValueError(
                f"ring length {length:g} m is not an integer number "
                f"of {cell_m:g} m NaSch cells"
            )

        footprint = float(vtype["length"]) + float(vtype["minGap"])
        if footprint > cell_m + 1e-9:
            raise ValueError(
                f"vehicle footprint {footprint:g} m exceeds "
                f"NaSch cell size {cell_m:g} m"
            )

        if n > n_cells:
            raise ValueError(
                f"{n} vehicles cannot fit into {n_cells} NaSch cells"
            )

        speed_unit = cell_m / dt
        vmax_cells = float(vtype["maxSpeed"]) / speed_unit
        if not math.isclose(vmax_cells, round(vmax_cells), abs_tol=1e-9):
            raise ValueError(
                "NaSch maxSpeed must be an integer number of cells per step"
            )

        # Spread the vehicles as evenly as possible over whole cells.
        start_cells = [i * n_cells // n for i in range(n)]

        # departPos describes the front of the vehicle. Placing the front at
        # the end of its assigned cell matches sumo/check_nasch.py.
        return [((cell + 1) * cell_m) % length for cell in start_cells]

    if mode == "uniform_jitter":
        jitter_value = initial.get("jitter_m", run.get("jitter_m"))
        if jitter_value is None:
            raise ValueError(
                "uniform_jitter initialization requires initial.jitter_m "
                "or the legacy run.jitter_m"
            )

        jitter = float(jitter_value)
        spacing = length / n
        footprint = float(vtype["length"]) + float(vtype["minGap"])

        if spacing - 2 * jitter < footprint:
            raise ValueError(
                f"{n} vehicles do not fit: spacing {spacing:.2f} m, "
                f"jitter {jitter:g} m, need {footprint:g} m + 2 * jitter"
            )

        rng = random.Random(seed)
        return [
            (i * spacing + rng.uniform(-jitter, jitter)) % length
            for i in range(n)
        ]

    raise ValueError(f"unsupported initial.mode: {mode!r}")


def build(cfg, n, seed):
    length = cfg["ring"]["length_m"]
    run, vtype = cfg["run"], cfg["vtype"]
    here = ROOT / "scenarios" / "ring"
    net = here / f"ring_{int(length)}.net.xml"
    if not net.exists():
        raise SystemExit(f"missing {net.name}; run build_net.py --length {length:g} first")

    edge_len = length / N_EDGES
    try:
        positions = initial_positions(cfg, n, seed)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    try:
        fcd_period, fcd_begin = fcd_settings(run)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    try:
        variant = run_variant(cfg)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    variant_tag = f"_{variant}" if variant else ""
    run_id = f"ring_{cfg['model'].lower()}{variant_tag}_L{int(length)}_n{n}_s{seed}"
    run_dir = ROOT / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    attrs = " ".join(f'{k}="{v}"' for k, v in vtype.items())
    lines = ["<routes>", f'    <vType id="car" {attrs}/>']
    laps = int(run["end_s"] * vtype["maxSpeed"] / length) + 2  # enough laps for the whole run
    for k in range(N_EDGES):
        edges = " ".join(f"e{(k + j) % N_EDGES}" for j in range(N_EDGES))
        lines.append(f'    <route id="r{k}" edges="{edges}" repeat="{laps}"/>')
    for i, s in enumerate(positions):
        # departPos is the position of the vehicle's front on its first edge; the rear
        # may reach back onto the previous edge, which SUMO handles.
        edge = min(int(s // edge_len), N_EDGES - 1)
        lines.append(f'    <vehicle id="v{i}" type="car" route="r{edge}" depart="0" '
                     f'departPos="{s - edge * edge_len:.3f}" departSpeed="0"/>')
    lines.append("</routes>")
    (run_dir / "vehicles.rou.xml").write_text("\n".join(lines) + "\n")

    fcd_device = ""
    if fcd_period is not None:
        fcd_device = f"""
    <fcd_device>
        <device.fcd.begin value="{fcd_begin:g}"/>
        <device.fcd.period value="{fcd_period:g}"/>
    </fcd_device>"""

    # Paths in a .sumocfg are resolved relative to the .sumocfg itself.
    (run_dir / "run.sumocfg").write_text(f"""<configuration>
    <input>
        <net-file value="{os.path.relpath(net, run_dir)}"/>
        <route-files value="vehicles.rou.xml"/>
    </input>
    <time>
        <begin value="0"/>
        <end value="{run['end_s']:g}"/>
        <step-length value="{run['step_s']:g}"/>
    </time>
    <random_number>
        <seed value="{seed}"/>
    </random_number>
    <processing>
        <collision.action value="warn"/>
        <!-- never teleport vehicles stuck in a jam: it would change N on the ring -->
        <time-to-teleport value="-1"/>
    </processing>
    <output>
        <fcd-output value="fcd.xml"/>
    </output>
{fcd_device}
</configuration>
""")
    return run_id, run_dir


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, help="configs/ring/<name>.toml")
    ap.add_argument("--vehicles", type=int, required=True, help="number of vehicles N")
    ap.add_argument("--seed", type=int, required=True)
    args = ap.parse_args()
    run_id, _ = build(config.load(args.config), args.vehicles, args.seed)
    print(run_id)


if __name__ == "__main__":
    main()
