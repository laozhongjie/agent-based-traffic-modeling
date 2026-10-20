"""Spot-check main roads of a city network: OSM way tags against the SUMO net.

For each distinct named trunk / primary / secondary / tertiary road, take its
longest edge in the net, read the OSM way id from the lane's `origId` parameter
(netconvert --output.original-names), and compare the way's `lanes`,
`lanes:forward`, `lanes:backward`, `oneway` and `maxspeed` tags with the edge's
lane count and speed. This checks net = OSM only; whether OSM = reality is a
separate Street View check (T1-D8), for which each row carries a link at the
edge midpoint.

Writes scenarios/city/<name>.spotcheck.csv and prints the score (rows whose lane
count and speed both match). Exit status 1 if any row fails.

Usage (from the repository root, SUMO_HOME set):
    python -I scenarios/city/spotcheck.py --config configs/city/bugis_all.toml \
        --osm-dir data/raw/osm/bugis_api --rows 18
"""
import argparse
import csv
import gzip
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from traffic_project import ROOT, config

sys.path.append(os.path.join(os.environ["SUMO_HOME"], "tools"))
import sumolib  # noqa: E402

MAIN = ("highway.trunk", "highway.primary", "highway.secondary", "highway.tertiary")
DEFAULT_KMH = 50  # type-map fallback where OSM has no maxspeed (sg_types.typ.xml, T1-D6)
COLUMNS = ["rank", "road", "osm_highway", "sumo_edge", "edge_length_m", "osm_way", "osm_lanes",
           "osm_lanes_forward", "osm_lanes_backward", "osm_oneway", "osm_maxspeed", "expected_lanes",
           "net_lanes", "net_speed_kmh", "lanes_ok", "speed_ok", "lat", "lon", "streetview_url"]


def pick_edges(net, n_rows):
    """Longest edge of each distinct (name, type) main road, longest first."""
    best = {}
    for e in net.getEdges():
        if e.getType() in MAIN and e.getName():
            k = (e.getName(), e.getType())
            if k not in best or e.getLength() > best[k].getLength():
                best[k] = e
    return sorted(best.values(), key=lambda e: -e.getLength())[:n_rows]


def way_id(edge):
    """First OSM way id of an edge (lane param origId)."""
    return edge.getLanes()[0].getParam("origId", "").split(" ")[0]


def read_way_tags(tiles, wanted):
    """Tags of the wanted OSM ways, streamed from the (gzipped) OSM XML tiles."""
    tags = {}
    for fp in tiles:
        with (gzip.open(fp) if str(fp).endswith(".gz") else open(fp, "rb")) as f:
            for _, el in ET.iterparse(f, events=("end",)):
                if el.tag == "way" and el.get("id") in wanted:
                    tags[el.get("id")] = {t.get("k"): t.get("v") for t in el.findall("tag")}
                if el.tag in ("node", "way", "relation"):
                    el.clear()
    return tags


def expected_lanes(edge, t):
    """Lane count OSM implies for this edge's direction ("-" if OSM gives none)."""
    lanes = t.get("lanes", "-")
    if t.get("oneway") == "yes":
        return lanes
    if "lanes:forward" in t or "lanes:backward" in t:
        return t.get("lanes:backward") if edge.getID().startswith("-") else t.get("lanes:forward")
    if lanes.isdigit():
        return str(int(lanes) // 2)
    return lanes


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", required=True)
    ap.add_argument("--osm-dir", default=None, help="default [network] osm_dir")
    ap.add_argument("--rows", type=int, default=18)
    args = ap.parse_args()
    cfg = config.load(args.config)
    name = cfg["name"]
    osm_dir = Path(args.osm_dir or ROOT / cfg["network"]["osm_dir"])
    tiles = [osm_dir / f for f in cfg["network"]["osm_files"]]
    net = sumolib.net.readNet(str(ROOT / "scenarios" / "city" / f"{name}.net.xml"))
    picks = pick_edges(net, args.rows)
    tags = read_way_tags(tiles, {way_id(e) for e in picks})
    rows = []
    for i, e in enumerate(picks, 1):
        way = way_id(e)
        t = tags.get(way, {})
        ms = t.get("maxspeed", "-")
        exp = expected_lanes(e, t)
        nl, sp = e.getLaneNumber(), round(e.getSpeed() * 3.6)
        shape = e.getShape()
        lon, lat = net.convertXY2LonLat(*shape[len(shape) // 2])
        rows.append({
            "rank": i, "road": e.getName(), "osm_highway": e.getType().split(".")[1], "sumo_edge": e.getID(),
            "edge_length_m": round(e.getLength(), 1), "osm_way": way, "osm_lanes": t.get("lanes", "-"),
            "osm_lanes_forward": t.get("lanes:forward", "-"), "osm_lanes_backward": t.get("lanes:backward", "-"),
            "osm_oneway": t.get("oneway", "-"), "osm_maxspeed": ms, "expected_lanes": exp,
            "net_lanes": nl, "net_speed_kmh": sp, "lanes_ok": exp == str(nl),
            "speed_ok": (ms == "-" and sp == DEFAULT_KMH) or (ms.isdigit() and int(ms) == sp),
            "lat": f"{lat:.5f}", "lon": f"{lon:.5f}",
            "streetview_url": f"https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={lat:.5f},{lon:.5f}",
        })
    out = ROOT / "scenarios" / "city" / f"{name}.spotcheck.csv"
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    ok = sum(r["lanes_ok"] and r["speed_ok"] for r in rows)
    for r in rows:
        print(f"{r['rank']:>2} {r['road']:<28} {r['osm_highway']:<10} lanes {r['net_lanes']} (OSM {r['expected_lanes']})"
              f" speed {r['net_speed_kmh']} (OSM {r['osm_maxspeed']}) {'ok' if r['lanes_ok'] and r['speed_ok'] else 'MISMATCH'}")
    print(f"spot-check {name}: {ok}/{len(rows)} rows match; wrote {out.relative_to(ROOT)}")
    sys.exit(0 if ok == len(rows) else 1)


if __name__ == "__main__":
    main()
