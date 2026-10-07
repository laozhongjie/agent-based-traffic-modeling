"""Place N vehicles on the ring and write one run's SUMO input files.

Vehicles start at rest, evenly spaced, with a small seeded offset so that the
seed controls the initial perturbation. Each vehicle's route starts on its own
edge and repeats, so it keeps circling for the whole run.

Usage (from the repository root):
    python scenarios/ring/build_run.py --config configs/ring/idm_sweep.toml --vehicles 30 --seed 1
Writes runs/<run-id>/vehicles.rou.xml and run.sumocfg, with
run-id = ring_<model>_L<length>_n<N>_s<seed>, and prints the run-id.
The network scenarios/ring/ring_<length>.net.xml must exist (see build_net.py).
"""
import argparse
import os
import random

from traffic_project import ROOT, config

N_EDGES = 4


def build(cfg, n, seed):
    length = cfg["ring"]["length_m"]
    run, vtype = cfg["run"], cfg["vtype"]
    here = ROOT / "scenarios" / "ring"
    net = here / f"ring_{int(length)}.net.xml"
    if not net.exists():
        raise SystemExit(f"missing {net.name}; run build_net.py --length {length:g} first")

    edge_len = length / N_EDGES
    spacing = length / n
    # Two neighbours can move towards each other by 2 * jitter; SUMO silently delays
    # inserting a vehicle that would start closer than length + minGap.
    need = vtype["length"] + vtype["minGap"]
    if spacing - 2 * run["jitter_m"] < need:
        raise SystemExit(f"{n} vehicles do not fit: spacing {spacing:.2f} m, "
                         f"jitter {run['jitter_m']} m, need {need} m + 2 * jitter")

    run_id = f"ring_{cfg['model'].lower()}_L{int(length)}_n{n}_s{seed}"
    run_dir = ROOT / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    rng = random.Random(seed)
    attrs = " ".join(f'{k}="{v}"' for k, v in vtype.items())
    lines = ["<routes>", f'    <vType id="car" {attrs}/>']
    laps = int(run["end_s"] * vtype["maxSpeed"] / length) + 2  # enough laps for the whole run
    for k in range(N_EDGES):
        edges = " ".join(f"e{(k + j) % N_EDGES}" for j in range(N_EDGES))
        lines.append(f'    <route id="r{k}" edges="{edges}" repeat="{laps}"/>')
    for i in range(n):
        # departPos is the position of the vehicle's front on its first edge; the rear
        # may reach back onto the previous edge, which SUMO handles.
        s = (i * spacing + rng.uniform(-run["jitter_m"], run["jitter_m"])) % length
        edge = min(int(s // edge_len), N_EDGES - 1)
        lines.append(f'    <vehicle id="v{i}" type="car" route="r{edge}" depart="0" '
                     f'departPos="{s - edge * edge_len:.3f}" departSpeed="0"/>')
    lines.append("</routes>")
    (run_dir / "vehicles.rou.xml").write_text("\n".join(lines) + "\n")

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
