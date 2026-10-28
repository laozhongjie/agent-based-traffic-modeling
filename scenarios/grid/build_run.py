"""Place N vehicles on one grid variant and write one run's SUMO input files.

Vehicles start at rest, spread evenly over every lane of the variant, with a
small seeded offset. Each vehicle starts with a one-edge route on its start edge.

Route rule (T4-D1, agreed by the group 2026-10-27, as on C's city network): the
constant-density controller (traffic_project.demand.ConstantDensity), which
scripts/grid_sweep.py runs through TraCI, gives every vehicle a random destination
edge (uniform over the car edges of the variant) when it departs, again whenever it
nears the end of its route, and as soon as it is within [controller] guard_m of its
destination by road. No vehicle arrives and leaves, which keeps N fixed for the whole
run, as on the ring. SUMO's rerouting device ([rerouting] in the config, written into
run.sumocfg) re-plans every route every 60 s on travel times averaged over the last
180 s, so vehicles react to congestion, as a Braess test needs. Run with plain sumo
instead, without the controller, every vehicle would arrive at the end of its first edge.

Teleports (T3-D11, agreed by member D for the grid): with [run] allow_teleport = true,
SUMO teleports a vehicle stuck for [run] time_to_teleport_s (300 s), and
grid_sweep.py reports the teleports of every run; otherwise teleporting is off.

Usage (from the repository root):
    python scenarios/grid/build_run.py --config configs/validation/grid_smoke.toml \
        --variant base --vehicles 300 --seed 1
Writes runs/<run-id>/vehicles.rou.xml and run.sumocfg, with
run-id = grid<n>_<model>_<variant>_n<N>_s<seed>, and prints the run-id.
The network scenarios/grid/grid<n>x<n>_L<block>_<variant>.net.xml must exist
(see build_net.py).
"""
import argparse
import os
import random
import xml.etree.ElementTree as ET

from traffic_project import ROOT, config


def read_net(path):
    """Lanes per edge, edge lengths, speeds and edge-to-edge connections."""
    root = ET.parse(path).getroot()
    edges, nxt = {}, {}
    for e in root.iter("edge"):
        if e.get("function") == "internal":
            continue
        lanes = e.findall("lane")
        edges[e.get("id")] = {"from": e.get("from"), "to": e.get("to"),
                              "lanes": len(lanes),
                              "length": float(lanes[0].get("length")),
                              "speed": max(float(l.get("speed")) for l in lanes)}
        nxt[e.get("id")] = set()
    for c in root.iter("connection"):
        if c.get("from") in nxt and c.get("to") in nxt:
            nxt[c.get("from")].add(c.get("to"))
    return edges, {k: sorted(v) for k, v in nxt.items()}


def build(cfg, variant, n, seed):
    grid, run, vtype = cfg["grid"], cfg["run"], cfg["vtype"]
    here = ROOT / "scenarios" / "grid"
    net = here / f"grid{grid['n']}x{grid['n']}_L{int(grid['block_m'])}_{variant}.net.xml"
    if not net.exists():
        raise SystemExit(f"missing {net.name}; run scenarios/grid/build_net.py first")
    edges, _ = read_net(net)

    # Usable stretch of each lane for a vehicle's front: the rear must not reach back
    # past the lane start (there is no unique previous edge on a grid), and a vehicle
    # at the very end of one edge must still keep minGap to a vehicle at the start of
    # the next edge on its route, or SUMO silently delays its insertion.
    jitter, vlen, gap = run["jitter_m"], vtype["length"], vtype["minGap"]
    slots = [(eid, lane, vlen + gap + jitter, e["length"] - jitter)
             for eid, e in sorted(edges.items()) for lane in range(e["lanes"])]
    usable = sum(hi - lo for _, _, lo, hi in slots)
    spacing = usable / n
    need = vlen + vtype["minGap"]
    if spacing - 2 * jitter < need:
        raise SystemExit(f"{n} vehicles do not fit: spacing {spacing:.2f} m, "
                         f"jitter {jitter} m, need {need} m + 2 * jitter")

    run_id = f"grid{grid['n']}_{cfg['model'].lower()}_{variant}_n{n}_s{seed}"
    run_dir = ROOT / "runs" / run_id
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
    print(run_id)


if __name__ == "__main__":
    main()
