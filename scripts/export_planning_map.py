"""Export the planning results per road to the website (docs/data/planning/planning_map.js).

Reads results/city/planning_seeds1to10/planning_edges.csv (member D's per-road congested shares,
written by scripts/planning_figures.py) and the variants' build records
scenarios/city/bugis_all_<variant>.meta.json, and writes window.PLANNING_MAP for the home page:

  densities      the target densities (veh/km per lane)
  roads          the road IDs in the order of docs/data/network/roads_bugis_all.js
  base[k]        per road, the baseline's share of the measured hour congested, in percent
  change[v][k]   per road, the change of that share against the baseline, in percentage points,
                 kept only where every seed pair moves the same way and the change is at least
                 5 points (member D's rule for the maps); 0 otherwise
  variants[v]    what each variant changes: street, edges, lanes, lane length, new edge shapes
  rankings       the closure and new-link candidates with street names, and the build checks

Usage (from the repository root):
    python scripts/export_planning_map.py
"""
import csv
import json
import xml.etree.ElementTree as ET
from collections import defaultdict

from traffic_project import ROOT

EDGES_CSV = "results/city/planning_seeds1to10/planning_edges.csv"
ROADS_JS = "docs/data/network/roads_bugis_all.js"
BASE_NET = "scenarios/city/bugis_all.net.xml"
VARIANTS = ("closure", "lanecut", "newlink")
OUT = "docs/data/planning/planning_map.js"
MIN_CHANGE = 0.05


def load_roads():
    text = (ROOT / ROADS_JS).read_text()
    data = json.loads(text[text.index("= {") + 2:].rstrip().rstrip(";"))
    return [e["id"] for e in data["edges"]]


def edge_info(net):
    root = ET.parse(ROOT / net).getroot()
    info = {}
    for e in root.findall("edge"):
        if e.get("function"):
            continue
        lanes = e.findall("lane")
        info[e.get("id")] = {"name": e.get("name") or "", "lanes": len(lanes),
                             "length_m": round(float(lanes[0].get("length")), 1),
                             "shape": lanes[0].get("shape")}
    return info


def main():
    roads = load_roads()
    index = {r: i for i, r in enumerate(roads)}
    rows = list(csv.DictReader(open(ROOT / EDGES_CSV)))
    densities = sorted({float(r["k_target"]) for r in rows})
    key = lambda k: f"{k:g}"
    base = {key(k): [0] * len(roads) for k in densities}
    change = {v: {key(k): [0] * len(roads) for k in densities} for v in VARIANTS}
    seeds = defaultdict(set)
    for r in rows:
        i = index.get(r["edge"])
        if i is None:
            continue                      # the new link's own two edges are not in the base roads
        k = key(float(r["k_target"]))
        seeds[(r["variant"], k)].add(int(r["n_seeds"]))
        if r["variant"] == "base":
            base[k][i] = round(100 * float(r["congested_share"]))
        elif r["d_share"] not in ("", "nan"):
            d = float(r["d_share"])
            if r["d_same_sign"] == "True" and abs(d) >= MIN_CHANGE:
                change[r["variant"]][k][i] = round(100 * d)

    names = edge_info(BASE_NET)
    variants, rankings = {}, {}
    for v in VARIANTS:
        meta = json.loads((ROOT / f"scenarios/city/bugis_all_{v}.meta.json").read_text())
        c = meta["change"]
        entry = {"type": c["type"], "edges": c["edges"],
                 "lane_length_m": meta["lane_length_m"], "baseline_lane_length_m": meta["baseline_lane_length_m"],
                 "build_check": {"roads_removed": len(meta["build_check"]["normal_edges"]["removed"]),
                                 "roads_added": len(meta["build_check"]["normal_edges"]["added"]),
                                 "roads_changed": len(meta["build_check"]["normal_edges"]["changed"]),
                                 "turns_removed": len(meta["build_check"]["connections_removed"]),
                                 "turns_added": len(meta["build_check"]["connections_added"]),
                                 "signal_programs_changed": len(meta["build_check"]["signal_programs_changed"]),
                                 "all_roads_reachable": meta["build_check"]["all_car_edges_reachable"]}}
        if v == "newlink":
            net = edge_info(meta["net"] if "/" in meta["net"] else f"scenarios/city/{meta['net']}")
            entry["shapes"] = [[[round(float(x), 1) for x in p.split(",")] for p in net[e]["shape"].split()]
                               for e in c["edges"]]
            entry["length_m"] = round(c["length_m"], 1)
            rankings["newlink"] = [{"from": r["from_at"]["streets"], "to": r["to_at"]["streets"],
                                    "length_m": round(r["length_m"], 1), "gain_share": r["gain_share"]}
                                   for r in meta["ranking"]]
        else:
            entry["street"] = c["street"]
            entry["lanes_before"] = c.get("lanes", c.get("lanes_before"))
            entry["lanes_after"] = c.get("lanes_after", [0, 0])
            if v == "closure":
                rankings["closure"] = [{"streets": sorted({names[e]["name"] for e in r["edges"]}),
                                        "length_m": max(names[e]["length_m"] for e in r["edges"]),
                                        "lanes": [names[e]["lanes"] for e in r["edges"]],
                                        "betweenness": r["betweenness"], "removable": r["keeps_connected"],
                                        "cut_off_roads": r["cut_off_edges"]} for r in meta["ranking"]]
        variants[v] = entry

    out = {"source": {"edges": EDGES_CSV, "roads": ROADS_JS,
                      "meta": [f"scenarios/city/bugis_all_{v}.meta.json" for v in VARIANTS],
                      "rule": f"coloured where every seed pair changes the same way by at least {MIN_CHANGE}"},
           "densities": densities, "roads": roads, "seeds": {f"{v}@{k}": sorted(s) for (v, k), s in sorted(seeds.items())},
           "base": base, "change": change, "variants": variants, "rankings": rankings}
    text = ("// Generated by scripts/export_planning_map.py from " + EDGES_CSV + " and the variants' meta files; do not edit.\n"
            "window.PLANNING_MAP = " + json.dumps(out, separators=(",", ":")) + ";\n")
    (ROOT / OUT).write_text(text)
    print(f"wrote {OUT}: {len(roads)} roads, {len(densities)} densities, {len(text) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
