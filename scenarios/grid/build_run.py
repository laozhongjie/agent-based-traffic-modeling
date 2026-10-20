"""Place N vehicles on one grid variant and write one run's SUMO input files.

Vehicles start at rest, spread evenly over every lane of the variant, with a
small seeded offset. Each vehicle gets its own long route so that it never
arrives and leaves, which keeps N fixed for the whole run, as on the ring.

Route rule (PLACEHOLDER until agreed with C): a seeded random walk. At every
junction the next edge is drawn uniformly from the reachable outgoing edges,
excluding the U-turn unless it is the only option. Routes are fixed at the
start, so vehicles do not react to congestion; a Braess test needs a rule
where they do (see configs/validation/grid_smoke.toml).

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


def random_walk(start, distance, edges, nxt, rng):
    """Edge list from `start` that is at least `distance` m long."""
    route, total = [start], 0.0
    while total < distance:
        cur = route[-1]
        options = [e for e in nxt[cur] if edges[e]["to"] != edges[cur]["from"]] or nxt[cur]
        if not options:
            raise SystemExit(f"dead end at edge {cur}")
        route.append(rng.choice(options))
        total += edges[route[-1]]["length"]
    return route


def build(cfg, variant, n, seed):
    grid, run, vtype = cfg["grid"], cfg["run"], cfg["vtype"]
    here = ROOT / "scenarios" / "grid"
    net = here / f"grid{grid['n']}x{grid['n']}_L{int(grid['block_m'])}_{variant}.net.xml"
    if not net.exists():
        raise SystemExit(f"missing {net.name}; run scenarios/grid/build_net.py first")
    edges, nxt = read_net(net)

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
    # A vehicle cannot cover more than end_s at its top speed; add one block of margin.
    top = min(vtype["maxSpeed"] * vtype.get("speedFactor", 1),
              max(e["speed"] for e in edges.values()))
    distance = run["end_s"] * top + max(e["length"] for e in edges.values())

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
        route = random_walk(eid, distance, edges, nxt, rng)
        lines.append(f'    <vehicle id="v{i}" type="car" depart="0" departLane="{lane}" '
                     f'departPos="{pos:.3f}" departSpeed="0">')
        lines.append(f'        <route edges="{" ".join(route)}"/>')
        lines.append("    </vehicle>")
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
        <!-- never teleport vehicles stuck in a jam: it would change N and hide gridlock -->
        <time-to-teleport value="-1"/>
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
