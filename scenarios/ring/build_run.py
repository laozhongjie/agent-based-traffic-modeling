"""Place N IDM vehicles on the ring and write one run's SUMO input files.

Vehicles start at rest, evenly spaced, with a small seeded offset so that the
seed controls the initial perturbation. Each vehicle's route starts on its own
edge and repeats, so it keeps circling for the whole run.

Usage:
    python build_run.py --length 1000 --vehicles 30 --seed 1 --end 1800
Writes runs/<run-id>/vehicles.rou.xml and run.sumocfg at the repository root,
with run-id = ring_idm_L<L>_n<N>_s<seed>. SUMO writes its outputs into the
same folder. The network scenarios/ring/ring_<L>.net.xml must exist (see build_net.py).
"""
import argparse
import os
import random
from pathlib import Path

N_EDGES = 4

# IDM parameters (placeholders until the group fixes the ring protocol).
VTYPE = dict(carFollowModel="IDM", length=5, minGap=2, accel=1.0, decel=1.5,
             tau=1.5, delta=4, maxSpeed=30, speedDev=0, speedFactor=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--length", type=float, default=1000.0, help="ring length in m")
    ap.add_argument("--vehicles", type=int, required=True, help="number of vehicles N")
    ap.add_argument("--seed", type=int, default=1, help="seed for the initial offsets and SUMO")
    ap.add_argument("--jitter", type=float, default=0.5, help="max position offset in m")
    ap.add_argument("--end", type=float, default=1800, help="simulation end time in s")
    ap.add_argument("--step", type=float, default=1.0, help="step length in s")
    args = ap.parse_args()

    here = Path(__file__).resolve().parent
    net = here / f"ring_{int(args.length)}.net.xml"
    if not net.exists():
        raise SystemExit(f"missing {net.name}; run build_net.py --length {args.length:g} first")
    run_id = f"ring_idm_L{int(args.length)}_n{args.vehicles}_s{args.seed}"
    run_dir = here.parents[1] / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    edge_len = args.length / N_EDGES
    spacing = args.length / args.vehicles
    # Two neighbours can move towards each other by 2 * jitter; SUMO silently delays
    # inserting a vehicle that would start closer than length + minGap.
    if spacing - 2 * args.jitter < VTYPE["length"] + VTYPE["minGap"]:
        raise SystemExit(f"{args.vehicles} vehicles do not fit: spacing {spacing:.2f} m, "
                         f"jitter {args.jitter} m, need {VTYPE['length'] + VTYPE['minGap']} m + 2 * jitter")

    rng = random.Random(args.seed)
    vtype = " ".join(f'{k}="{v}"' for k, v in VTYPE.items())
    lines = ["<routes>", f'    <vType id="idm" {vtype}/>']
    laps = int(args.end * VTYPE["maxSpeed"] / args.length) + 2  # enough laps for the whole run
    for k in range(N_EDGES):
        edges = " ".join(f"e{(k + j) % N_EDGES}" for j in range(N_EDGES))
        lines.append(f'    <route id="r{k}" edges="{edges}" repeat="{laps}"/>')
    for i in range(args.vehicles):
        # departPos is the position of the vehicle's front on its first edge; the rear
        # may reach back onto the previous edge, which SUMO handles.
        s = (i * spacing + rng.uniform(-args.jitter, args.jitter)) % args.length
        edge = min(int(s // edge_len), N_EDGES - 1)
        pos = s - edge * edge_len
        lines.append(f'    <vehicle id="v{i}" type="idm" route="r{edge}" depart="0" '
                     f'departPos="{pos:.3f}" departSpeed="0"/>')
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
        <end value="{args.end:g}"/>
        <step-length value="{args.step:g}"/>
    </time>
    <random_number>
        <seed value="{args.seed}"/>
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
    print(f"wrote runs/{run_id}/  (k = {1000 * args.vehicles / args.length:.1f} veh/km)")


if __name__ == "__main__":
    main()
