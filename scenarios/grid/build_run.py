"""Place N vehicles on one grid variant and write one run's SUMO input files.

Vehicles start at rest, spread evenly over every lane of the variant, with a
small seeded offset. Each vehicle starts with a one-edge route on its start edge.

Route rule (T4-D1, agreed by the group 2026-10-27, as on C's city network): the
constant-density controller (traffic_project.demand.ConstantDensity), which
scripts/grid_sweep.py runs through TraCI, gives every vehicle a random destination
edge (uniform over the base grid's car edges that the variant still has, T4-D2, so a
new link is never a destination) when it departs, again whenever it nears the end of
its route, and as soon as it is within [controller] guard_m of its destination by road.
No vehicle arrives and leaves, which keeps N fixed for the whole run, as on the ring.
SUMO's rerouting device ([rerouting] in the config, written into run.sumocfg) re-plans
every route every 60 s on travel times averaged over the last 180 s, so vehicles react
to congestion, as a Braess test needs. Run with plain sumo or sumo-gui instead, without
the controller, every vehicle would arrive at the end of its first edge and leave; the
written run.sumocfg says so in a comment at its top, and main() notes it on stderr.

Teleports (T3-D11, agreed by member D for the grid): with [run] allow_teleport = true,
SUMO teleports a vehicle stuck for [run] time_to_teleport_s (300 s), and
grid_sweep.py reports the teleports of every run; otherwise teleporting is off.

Usage (from the repository root):
    python scenarios/grid/build_run.py --config configs/validation/grid_smoke.toml \
        --variant base --vehicles 300 --seed 1
Writes runs/<run-id>/vehicles.rou.xml and run.sumocfg, with
run-id = <run_prefix>_<variant>_n<N>_s<seed>, and prints the run-id (alone on stdout,
which grid_sweep.py reads; the note that the run needs the controller goes to stderr).
run_prefix is [sweep] run_prefix of the config, or the config's name when that is not set
(as [sweep] run_prefix on the city network, scripts/city_sweep.py), so two grid configs
never share run folders by accident. A run folder that already holds a run of another
config (its manifest.json names another config file) stops the build instead of being
overwritten; running the same config again overwrites its own runs.
The network scenarios/grid/grid<n>x<n>_L<block>_<variant>.net.xml must exist
(see build_net.py).
"""
import argparse
import json
import os
import random
import re
import sys
import xml.etree.ElementTree as ET

from traffic_project import ROOT, config

NEEDS_CONTROLLER = ("this run needs the constant-density controller of scripts/grid_sweep.py "
                    "(T4-D1): plain sumo or sumo-gui would let every vehicle arrive at the end "
                    "of its one-edge start route and leave")


def run_prefix(cfg):
    """[sweep] run_prefix, or the config's name when it is not set."""
    prefix = cfg.get("sweep", {}).get("run_prefix", cfg["name"])
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", prefix):
        raise SystemExit(f"run prefix {prefix!r} ([sweep] run_prefix, or name) may hold only "
                         "letters, digits, '_', '.' and '-': it names folders under runs/")
    return prefix


def check_run_dir(run_dir, cfg):
    """Stop when run_dir holds a run of another config, which this build would overwrite."""
    manifest = run_dir / "manifest.json"
    if not manifest.exists():
        return
    old = json.loads(manifest.read_text()).get("config")
    if old != cfg["_path"]:
        raise SystemExit(f"{run_dir} holds a run of {old}, not of {cfg['_path']}: give this config its own "
                         "name, or its own [sweep] run_prefix, so it does not overwrite that run")


def read_net(path):
    """{edge id: {"lanes": number of lanes, "length": m}} for the normal (non-internal) edges."""
    edges = {}
    for e in ET.parse(path).getroot().iter("edge"):
        if e.get("function") == "internal":
            continue
        lanes = e.findall("lane")
        edges[e.get("id")] = {"lanes": len(lanes), "length": float(lanes[0].get("length"))}
    return edges


def build(cfg, variant, n, seed):
    grid, run, vtype = cfg["grid"], cfg["run"], cfg["vtype"]
    here = ROOT / "scenarios" / "grid"
    net = here / f"grid{grid['n']}x{grid['n']}_L{int(grid['block_m'])}_{variant}.net.xml"
    if not net.exists():
        raise SystemExit(f"missing {net.name}; run scenarios/grid/build_net.py first")
    edges = read_net(net)

    # Usable stretch of each lane for a vehicle's front: the rear must not reach back
    # past the lane start (there is no unique previous edge on a grid), and a further
    # minGap at the lane start keeps a vehicle there at least minGap ahead of a vehicle
    # standing at the very end of any edge that leads into this lane. At insertion every
    # route is the one start edge, so no vehicle has a next edge yet; but the controller
    # appends a path to every vehicle in the step it departs, and from then on a vehicle
    # at the end of an edge may be routed onto this lane, where it must not start closer
    # than minGap to the vehicle ahead.
    jitter, vlen, gap = run["jitter_m"], vtype["length"], vtype["minGap"]
    slots = [(eid, lane, vlen + gap + jitter, e["length"] - jitter)
             for eid, e in sorted(edges.items()) for lane in range(e["lanes"])]
    usable = sum(hi - lo for _, _, lo, hi in slots)
    spacing = usable / n
    need = vlen + vtype["minGap"]
    if spacing - 2 * jitter < need:
        raise SystemExit(f"{n} vehicles do not fit: spacing {spacing:.2f} m, "
                         f"jitter {jitter} m, need {need} m + 2 * jitter")

    run_id = f"{run_prefix(cfg)}_{variant}_n{n}_s{seed}"
    run_dir = ROOT / "runs" / run_id
    check_run_dir(run_dir, cfg)
    run_dir.mkdir(parents=True, exist_ok=True)

    rng = random.Random(seed)

    attrs = " ".join(f'{k}="{v}"' for k, v in vtype.items())
    lines = ["<routes>", f'    <vType id="car" {attrs}/>']
    slot, slot_start = 0, 0.0  # slot_start: usable length of all earlier slots
    for i in range(n):
        s = (i + 0.5) * spacing + rng.uniform(-jitter, jitter)
        while s > slot_start + (slots[slot][3] - slots[slot][2]):
            slot_start += slots[slot][3] - slots[slot][2]
            slot += 1
        eid, lane, lo, _ = slots[slot]
        pos = lo + (s - slot_start)
        # one-edge start: the controller gives the vehicle its destination when it departs
        lines.append(f'    <vehicle id="v{i}" type="car" depart="0" departLane="{lane}" '
                     f'departPos="{pos:.3f}" departSpeed="0">')
        lines.append(f'        <route edges="{eid}"/>')
        lines.append("    </vehicle>")
    lines.append("</routes>")
    (run_dir / "vehicles.rou.xml").write_text("\n".join(lines) + "\n")

    # Teleport time and rerouting device as on C's city network (scripts/city_sweep.py on
    # c/city-network). Paths in a .sumocfg are resolved relative to the .sumocfg itself.
    rr = cfg["rerouting"]
    ttt = run["time_to_teleport_s"] if run.get("allow_teleport", False) else -1
    (run_dir / "run.sumocfg").write_text(f"""<!-- Written by scenarios/grid/build_run.py: {NEEDS_CONTROLLER}. -->
<configuration>
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
        <!-- T3-D11: teleport a vehicle stuck this many seconds (-1: never); a vehicle in
             mid-teleport still counts in N, and grid_sweep.py reports every teleport -->
        <time-to-teleport value="{ttt}"/>
        <!-- T4-D1: every vehicle re-plans its route every period on recent travel times -->
        <device.rerouting.probability value="{rr['probability']}"/>
        <device.rerouting.period value="{rr['period_s']}"/>
        <device.rerouting.adaptation-interval value="{rr['adaptation_interval_s']}"/>
        <device.rerouting.adaptation-steps value="{rr['adaptation_steps']}"/>
    </processing>
    <output>
        <summary-output value="summary.xml"/>
        <fcd-output value="fcd.xml"/>
    </output>
</configuration>
""")
    return run_id, run_dir


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, help="configs/<group>/<name>.toml")
    ap.add_argument("--variant", required=True, choices=["base", "closure", "newlink"])
    ap.add_argument("--vehicles", type=int, required=True, help="number of vehicles N")
    ap.add_argument("--seed", type=int, required=True)
    args = ap.parse_args()
    run_id, _ = build(config.load(args.config), args.variant, args.vehicles, args.seed)
    print(f"note: {NEEDS_CONTROLLER}", file=sys.stderr)   # stdout holds only the run id (grid_sweep.py reads it)
    print(run_id)


if __name__ == "__main__":
    main()
