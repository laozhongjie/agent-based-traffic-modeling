"""Create IDM SUMO runs for multi-lane ring, closed oval, or open freeway.

Usage (from repository root, with src on PYTHONPATH / package installed):
    python scenarios/ring/build_run_different_track.py --config configs/ring/idm_multi_ring_4800.toml --vehicles 192 --seed 401
"""
import argparse
import math
import os
import random
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.sax.saxutils import quoteattr

from traffic_project import ROOT
import tomllib
from build_net_different_track import geometry, network_stem


def attrs_xml(values):
    return " ".join(f"{k}={quoteattr(str(v).lower() if isinstance(v, bool) else str(v))}" for k, v in values.items())


def build(cfg, n, seed):
    nw = cfg.get("network", {})
    kind = nw.get("type", "ring")
    length = float(nw.get("length_m", cfg.get("ring", {}).get("length_m", 4800)))
    lanes = int(nw.get("lanes", 1))
    if kind not in ("ring", "oval", "freeway") or lanes < 1 or n <= 0:
        raise ValueError("invalid network or vehicle count")
    run, original_vtype = cfg["run"], cfg["vtype"]
    vtype = dict(original_vtype)
    vtype.setdefault("lcSpeedGain", 0)
    vtype.setdefault("lcStrategic", 0)
    vtype.setdefault("lcCooperative", 0)
    vtype.setdefault("lcKeepRight", 0)
    if cfg.get("lane_change", {}).get("enabled", False):
        for key in ("lcSpeedGain", "lcStrategic", "lcCooperative", "lcKeepRight"):
            if key not in original_vtype:
                vtype.pop(key, None)
    here = ROOT / "scenarios" / "ring"
    net = here / (network_stem(kind, length, lanes) + ".net.xml")
    if not net.exists():
        raise SystemExit(f"Missing {net}; first run build_net_different_track.py with matching type/length/lanes")
    straight = float(nw.get("straight_length_m", 1800))
    _, edge_lengths = geometry(kind, length, straight)
    boundaries = [sum(edge_lengths[:k+1]) for k in range(len(edge_lengths))]
    jitter = float(run.get("jitter_m", 0))
    vehicle_length = float(vtype["length"])
    mingap = float(vtype["minGap"])
    # Place vehicles evenly on each lane and leave sufficient longitudinal gap.
    counts = [n // lanes + (1 if lane < n % lanes else 0) for lane in range(lanes)]
    for count in counts:
        if count and length/count - 2*jitter < vehicle_length+mingap:
            raise ValueError(f"Vehicles will overlap on a lane: n={n}, lanes={lanes}, jitter={jitter}")
    run_id = f"{kind}_{cfg['model'].lower()}_L{int(length)}_m{lanes}_n{n}_s{seed}"
    run_dir = ROOT / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    lines = ["<routes>", f'    <vType id="car" {attrs_xml(vtype)}/>']
    closed = kind != "freeway"
    if closed:
        max_speed = float(vtype.get("maxSpeed", nw.get("speed_limit_mps", 30)))
        laps = math.ceil(float(run["end_s"]) * max_speed / length) + 2
        for k in range(4):
            sequence = " ".join(f"e{(k+j)%4}" for j in range(4))
            lines.append(f'    <route id="r{k}" edges="{sequence}" repeat="{laps}"/>')
    else:
        for k in range(4):
            sequence = " ".join(f"e{j}" for j in range(k, 4))
            lines.append(f'    <route id="r{k}" edges="{sequence}"/>')
        lines.append('    <route id="through" edges="e0 e1 e2 e3"/>')
    idx = 0
    for lane, count in enumerate(counts):
        for i in range(count):
            s = ((i + 0.5)*length/count + rng.uniform(-jitter, jitter)) % length
            k = next((j for j, endpoint in enumerate(boundaries) if s < endpoint), 3)
            start = 0 if k == 0 else boundaries[k-1]
            lines.append(f'    <vehicle id="v{idx}" type="car" route="r{k}" depart="0" '
                         f'departLane="{lane}" departPos="{s-start:.3f}" departSpeed="0"/>')
            idx += 1
    if not closed:
        op = cfg.get("open", {})
        rate_per_lane = float(op.get("inflow_veh_h_lane", 0))
        if rate_per_lane > 0:
            begin = float(op.get("inflow_start_s", 10))
            end = float(op.get("inflow_end_s", run["end_s"]))
            if end <= begin:
                raise ValueError("open: inflow_end_s must be greater than inflow_start_s")
            for lane in range(lanes):
                lines.append(f'    <flow id="in{lane}" type="car" route="through" '
                             f'begin="{begin:g}" end="{end:g}" vehsPerHour="{rate_per_lane:g}" '
                             f'departLane="{lane}" departPos="base" departSpeed="max"/>')
    lines.append("</routes>")
    (run_dir/"vehicles.rou.xml").write_text("\n".join(lines)+"\n")
    # Validate XML before handing it to SUMO.
    ET.parse(run_dir/"vehicles.rou.xml")
    fcd = '<fcd-output value="fcd.xml"/>'
    cfg_text = f'''<configuration>
  <input><net-file value="{os.path.relpath(net,run_dir)}"/><route-files value="vehicles.rou.xml"/></input>
  <time><begin value="0"/><end value="{run['end_s']:g}"/><step-length value="{run['step_s']:g}"/></time>
  <random_number><seed value="{seed}"/></random_number>
  <processing><collision.action value="warn"/><time-to-teleport value="-1"/></processing>
  <output>{fcd}</output>
</configuration>
'''
    (run_dir/"run.sumocfg").write_text(cfg_text)
    ET.parse(run_dir/"run.sumocfg")
    return run_id, run_dir


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--vehicles", type=int, required=True)
    ap.add_argument("--seed", type=int, required=True)
    args = ap.parse_args()
    run_id, _ = build(tomllib.loads(Path(args.config).read_text()), args.vehicles, args.seed)
    print(run_id)


if __name__ == "__main__":
    main()
