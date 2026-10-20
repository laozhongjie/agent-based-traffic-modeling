"""Pilot-grade constant-vehicle-count runs on a city net, to check the congestion criterion.

NOT the city experiment's controller (Task 4 owns that); single seed, pilot grade.
    python scripts/city_pilot_density.py --config configs/city/bugis_all_density_pilot.toml

For each density in [pilot] densities_veh_km, plus the free-flow reference run at
[measure] reference_density_veh_km / reference_seed, it writes runs/<prefix>_k<k>_s<seed>/
and runs SUMO through TraCI (libsumo when importable):
  - N = round(k x total lane length of normal lanes / 1000) vehicles are spread evenly
    over all lanes that allow passenger cars at t = 0 (the Task 3 grid pilot's placement);
  - each vehicle starts with a one-edge route and gets a random destination edge
    (uniform over car edges); when it is within [pilot] retarget_at_remaining_edges edges
    of its route end it gets a new one ([pilot] retarget_mode: "append" adds the fastest
    path from the route's end, "change_target" re-routes from the current edge), so no
    vehicle arrives;
  - the only output is edgeData at the criterion period (congestion.edgedata_additional,
    trimmed attributes, gzipped) and summary.xml; no FCD.
meta.json records the vehicle count actually loaded, inserted, arrived and teleported.
"""
import argparse
import json
import os
import random
import sys
import time
from multiprocessing import Pool
from pathlib import Path

sys.path.append(os.path.join(os.environ.get("SUMO_HOME", "/usr/share/sumo"), "tools"))
import sumolib  # noqa: E402
from traci import constants as tc  # noqa: E402

from traffic_project import ROOT, config  # noqa: E402
from traffic_project import congestion as cg  # noqa: E402

try:
    import libsumo as sim  # noqa: E402
except ImportError:  # pragma: no cover
    import traci as sim  # noqa: E402


def car_lanes(net_path):
    """[(edge id, length m, [lane indices allowing passenger cars])] for normal edges."""
    net = sumolib.net.readNet(str(net_path))
    out = []
    for e in net.getEdges():
        lanes = [ln.getIndex() for ln in e.getLanes() if ln.allows("passenger")]
        if lanes:
            out.append((e.getID(), e.getLength(), lanes))
    return out


def write_run(cfg, k, seed, net_path, lanes, lane_m, period):
    """Write one run folder (routes, additional, sumocfg, meta) and return its path."""
    p, v = cfg["pilot"], cfg["vehicle"]
    jit = p["placement_jitter_m"]
    n = round(k * lane_m / 1000)
    lo0 = v["length"] + v["minGap"] + jit
    slots = [(eid, ln, lo0, length - jit) for eid, length, idx in sorted(lanes)
             for ln in idx if length - jit > lo0]
    usable = sum(hi - lo for *_, lo, hi in slots)
    spacing = usable / n
    assert spacing - 2 * jit >= v["length"] + v["minGap"], f"k={k}: vehicles do not fit"
    rng = random.Random(seed)
    attrs = " ".join(f'{a}="{x}"' for a, x in v.items())
    out = ["<routes>", f'    <vType id="car" {attrs}/>']
    slot, start = 0, 0.0
    for i in range(n):
        s = (i + 0.5) * spacing + rng.uniform(-jit, jit)
        while s > start + (slots[slot][3] - slots[slot][2]):
            start += slots[slot][3] - slots[slot][2]
            slot += 1
        eid, ln, lo, _ = slots[slot]
        out.append(f'    <vehicle id="v{i}" type="car" depart="0" departLane="{ln}" '
                   f'departPos="{lo + (s - start):.3f}" departSpeed="0"><route edges="{eid}"/>'
                   f'</vehicle>')
    out.append("</routes>")
    d = ROOT / "runs" / f"{p['run_prefix']}_k{k:g}_s{seed}"
    d.mkdir(parents=True, exist_ok=True)
    (d / "vehicles.rou.xml").write_text("\n".join(out) + "\n")
    edfile = cfg["inputs"]["edgedata_file"].format(period=period)
    (d / "edgedata.add.xml").write_text(cg.edgedata_additional(period, file=edfile))
    (d / "run.sumocfg").write_text(f"""<configuration>
    <input>
        <net-file value="{os.path.relpath(net_path, d)}"/>
        <route-files value="vehicles.rou.xml"/>
        <additional-files value="edgedata.add.xml"/>
    </input>
    <time><begin value="0"/><end value="{p['end_s']}"/><step-length value="{p['step_length_s']}"/></time>
    <random_number><seed value="{seed}"/></random_number>
    <processing>
        <collision.action value="warn"/>
        <time-to-teleport value="-1"/>
    </processing>
    <output><summary-output value="summary.xml"/></output>
</configuration>
""")
    meta = dict(net=str(net_path), tag=cfg["network"]["tag"], k_target=k, seed=seed,
                n_vehicles=n, lane_length_m=lane_m, period_s=period, end_s=p["end_s"],
                controller=f"pilot retarget ({p['retarget_mode']}); not the Task 4 controller")
    (d / "meta.json").write_text(json.dumps(meta, indent=1))
    return d


def run(args):
    """Run one folder with the retarget loop; update meta.json with counts and wall time."""
    d, dests, remaining, mode = args
    rng = random.Random(json.loads((d / "meta.json").read_text())["seed"] + 7919)
    t0 = time.time()
    sim.start(["sumo", "-c", str(d / "run.sumocfg"), "--no-step-log", "true",
               "--log", str(d / "log.txt")])
    rlen, inserted, arrived, retargets, failed, teleports = {}, 0, 0, 0, 0, 0

    def retarget(vid):
        """New random destination. "append": keep the rest of the route and add the
        fastest path from its last edge to the new destination (the vehicle's next turns
        do not change, so no late lane changes); "change_target": vehicle.changeTarget."""
        nonlocal retargets, failed
        route, idx = sim.vehicle.getRoute(vid), sim.vehicle.getRouteIndex(vid)
        for _ in range(20):
            dest = rng.choice(dests)
            if dest in (route[-1], route[idx]):
                continue
            try:
                if mode == "append":
                    path = sim.simulation.findRoute(route[-1], dest, vType="car").edges
                    if len(path) < 2:
                        continue
                    sim.vehicle.setRoute(vid, list(route[idx:]) + list(path[1:]))
                else:
                    sim.vehicle.changeTarget(vid, dest)
                rlen[vid] = len(sim.vehicle.getRoute(vid))
                retargets += 1
                return
            except sim.TraCIException:
                continue
        failed += 1

    end = json.loads((d / "meta.json").read_text())["end_s"]
    while sim.simulation.getTime() < end:
        sim.simulationStep()
        for vid in sim.simulation.getDepartedIDList():
            inserted += 1
            sim.vehicle.subscribe(vid, [tc.VAR_ROUTE_INDEX])
            retarget(vid)
        arrived += sim.simulation.getArrivedNumber()
        teleports += sim.simulation.getStartingTeleportNumber()
        for vid, res in sim.vehicle.getAllSubscriptionResults().items():
            if res and res[tc.VAR_ROUTE_INDEX] >= rlen.get(vid, 0) - remaining:
                retarget(vid)
    sim.close()
    meta = json.loads((d / "meta.json").read_text())
    meta.update(n_inserted=inserted, n_arrived=arrived, n_retargets=retargets,
                n_retarget_failed=failed, wall_s=round(time.time() - t0, 1),
                n_teleports=teleports)
    (d / "meta.json").write_text(json.dumps(meta, indent=1))
    return d.name, inserted, arrived, meta["wall_s"]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", required=True)
    cfg = config.load(ap.parse_args().config)
    p, m = cfg["pilot"], cfg["measure"]
    net_path = ROOT / cfg["network"]["net_file"]
    net = cg.read_net(net_path)
    period = cg.cycle_period(net, m["period_s"])
    lane_m = float((net.edges.length * net.edges.lanes).sum())
    lanes = car_lanes(net_path)
    dests = sorted(e for e, *_ in lanes)
    jobs = [(m["reference_density_veh_km"], m["reference_seed"])] + \
        [(k, p["seed"]) for k in p["densities_veh_km"]]
    dirs = [write_run(cfg, k, s, net_path, lanes, lane_m, period) for k, s in jobs]
    print(f"lane length {lane_m / 1000:.2f} km, period {period:g} s, {len(dirs)} runs", flush=True)
    with Pool(min(p["jobs"], 8, len(dirs))) as pool:
        for name, ins, arr, wall in pool.imap_unordered(
                run, [(d, dests, p["retarget_at_remaining_edges"], p["retarget_mode"]) for d in dirs]):
            print(name, "inserted", ins, "arrived", arr, "wall", wall, "s", flush=True)


if __name__ == "__main__":
    main()
