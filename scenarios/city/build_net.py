"""Build a SUMO city network from raw OpenStreetMap tiles (two netconvert passes).

Stage 1 runs netconvert on the raw OSM XML with the Singapore settings in the
config (left-hand traffic, Singapore type map, road classes, OSM signal tags,
fixed-time signals). The strong-component pass then keeps only the largest
strongly connected component of the passenger lane-connection graph (node =
edge that allows passenger cars, arc e -> f if some lane of e connects to f),
so every kept road can reach every other kept road and get back; this respects
turn restrictions and missing U-turns. Stage 2 reloads the stage-1 net with only
those edges. With `tls_rebuild = true` (T1-D10), stage 2 also rebuilds every signal
plan for the roads that remain, so no phase gives green only to a removed road.

OSM lane arrows (turn:lanes) follow `osm_turn_lanes` (T1-D13). netconvert 1.28.0
applies them as their mirror image in a --lefthand net (lane order reversed, left
and right swapped), so with "mirror" stage 1 reads a temporary copy of the tiles
in which every turn:lanes, turn:lanes:forward and turn:lanes:backward value is
already mirrored; the two mirrors cancel and, where netconvert can apply the arrows, the lanes come out as
OSM tags them.
The raw tiles are never changed, so the net still builds from raw OSM.

Writes, next to this script (or in --out-dir):
    <name>.net.xml    the network (committed)
    <name>.meta.json  counts, lane lengths, signal cycles, netconvert commands
                      and version, sha256 of every OSM tile (committed)
and the stage-1 net, the kept edge ids and the netconvert logs to runs/<run-id>/
(git-ignored).

Density uses `lane_length_m` from the meta file: the summed length of every lane
on normal (non-internal) edges. `internal_lane_length_m` (lanes inside
junctions) is recorded separately, so either denominator is exact.

Usage (from the repository root, SUMO_HOME set):
    python -I scenarios/city/build_net.py --config configs/city/bugis_all.toml \
        --osm-dir data/raw/osm/bugis_api
"""
import argparse
import datetime as dt
import gzip
import hashlib
import json
import os
import re
import shutil
import shlex
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from traffic_project import ROOT, config

sys.path.append(os.path.join(os.environ["SUMO_HOME"], "tools"))
import networkx as nx  # noqa: E402
import sumolib  # noqa: E402

# OSM highway classes removed before import, per road-class set (T1-D2).
# Expressways (motorway) are a different flow regime; service roads are driveways and car parks.
ROAD_CLASSES = {
    "all": ["highway.motorway", "highway.motorway_link", "highway.service"],
    "art": ["highway.motorway", "highway.motorway_link", "highway.service",
            "highway.residential", "highway.unclassified", "highway.living_street"],
    "allx": ["highway.service"],
}
TURNAROUNDS = {"deadend": ["--no-turnarounds.except-deadend"], "default": [], "none": ["--no-turnarounds"]}

# OSM turn:lanes handling (T1-D13), [network] osm_turn_lanes:
#   "mirror"  import a copy of the tiles with every turn:lanes value mirrored, which undoes
#             netconvert's mirroring in a --lefthand net (verified on netconvert 1.28.0 only);
#   "off"     no turn-lane import: netconvert guesses every lane's turns;
#   "as_is"   import the tags unchanged: in a --lefthand net this builds their mirror image
#             (the provisional nets of 2026-10-20); right only for a right-hand net.
TURN_LANE_MODES = ("mirror", "off", "as_is")
MIRROR_CHECKED_ON = "1.28.0"   # netconvert version whose left-hand mirroring "mirror" undoes
TURN_SWAP = {"left": "right", "right": "left", "slight_left": "slight_right", "slight_right": "slight_left",
             "sharp_left": "sharp_right", "sharp_right": "sharp_left",
             "merge_to_left": "merge_to_right", "merge_to_right": "merge_to_left"}
TURN_LANES_VALUE = re.compile(rb'(<tag k="turn:lanes(?::forward|:backward)?" v=")([^"]*)(")')
TURN_LANES_KEY = re.compile(rb"""k=["']turn:lanes(?::forward|:backward)?["']""")
MIRROR_DIR = "osm_turn_lanes_mirrored"   # inside the build's temporary directory


def sha256(path):
    """Hex sha256 of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def logic_opts(net):
    """netconvert options that shape junction logic; applied in both stages."""
    opts = list(TURNAROUNDS[net["turnarounds"]])
    if not net["internal_links"]:
        opts.append("--no-internal-links")
    if net["left_before_right"]:
        opts.append("--junctions.left-before-right")
    return opts


def mirror_turn_lanes(value):
    """Mirror one OSM turn:lanes value: lanes in reverse order, left and right swapped in every token.

    'left;through|through|through;right|right' -> 'left|through;left|through|right;through'.
    through, reverse, none and empty lanes keep their token; the mirror is its own inverse.
    """
    return "|".join(";".join(TURN_SWAP.get(t.strip(), t.strip()) for t in lane.split(";"))
                    for lane in reversed(value.split("|")))


def turn_lane_opts(net, lefthand=True):
    """["--osm.turn-lanes"] or [], per the required [network] osm_turn_lanes (TURN_LANE_MODES).

    "mirror" corrects netconvert's left-hand reading only: a right-hand net reads turn:lanes
    correctly, so there the mirror would build every arrow reversed. It is refused; use "as_is".
    """
    mode = net["osm_turn_lanes"]
    if mode not in TURN_LANE_MODES:
        raise ValueError(f"[network] osm_turn_lanes = {mode!r}: expected one of {TURN_LANE_MODES}")
    if mode == "mirror" and not lefthand:
        raise ValueError('osm_turn_lanes = "mirror" undoes netconvert\'s left-hand mirroring; '
                         'a right-hand net reads turn:lanes correctly: use "as_is"')
    return [] if mode == "off" else ["--osm.turn-lanes"]


def osm_inputs(net, tiles, workdir):
    """Stage-1 --osm-files entries and the number of turn:lanes values mirrored.

    With osm_turn_lanes = "mirror", writes a copy of each tile to <workdir>/osm_turn_lanes_mirrored/
    with every turn:lanes, turn:lanes:forward and turn:lanes:backward value mirrored
    (mirror_turn_lanes) and returns those copies relative to workdir, where netconvert runs.
    Otherwise returns the raw tiles. Raises if a tile holds a turn:lanes key this rewrite cannot reach.
    """
    if net["osm_turn_lanes"] != "mirror":
        return [str(t) for t in tiles], 0
    out = Path(workdir, MIRROR_DIR)
    out.mkdir()
    files, total = [], 0
    for tile in tiles:
        tile = Path(tile)
        with (gzip.open(tile) if tile.suffix == ".gz" else open(tile, "rb")) as f:
            raw = f.read()
        text, n = TURN_LANES_VALUE.subn(
            lambda m: m[1] + mirror_turn_lanes(m[2].decode("utf-8")).encode("utf-8") + m[3], raw)
        keys = len(TURN_LANES_KEY.findall(raw))
        if n != keys:
            raise ValueError(f"{tile.name}: {keys} turn:lanes keys but {n} values in the form "
                             '<tag k="turn:lanes..." v="...">; cannot mirror the rest')
        with (gzip.open(out / tile.name, "wb", compresslevel=1) if tile.suffix == ".gz"
              else open(out / tile.name, "wb")) as f:
            f.write(text)
        files.append(f"{MIRROR_DIR}/{tile.name}")
        total += n
    return files, total


def stage1_args(net, tiles, workdir):
    """Full stage-1 netconvert arguments (run in workdir) and the number of turn:lanes values mirrored."""
    files, mirrored = osm_inputs(net, tiles, workdir)
    return ["--osm-files", ",".join(files), *stage1_opts(net), "-o", "stage1.net.xml"], mirrored


def stage1_opts(net):
    """netconvert options for the raw-OSM pass, in the pilot's order. Every net is left-hand."""
    w, s, e, n = net["study_box"]
    m = net["clip_margin_deg"]
    clip = ",".join(f"{v:.5f}" for v in (w - m, s - m, e + m, n + m))
    tls = []
    if net["tls_guess_signals"]:
        tls.append("--tls.guess-signals")
    if net["tls_discard_simple"]:
        tls.append("--tls.discard-simple")
    if net["tls_join"]:
        tls.append("--tls.join")
    return (["--type-files", str(ROOT / net["type_file"]), "--lefthand",
             "--keep-edges.in-geo-boundary", clip, "--keep-edges.by-vclass", "passenger",
             "--remove-edges.by-type", ",".join(ROAD_CLASSES[net["road_classes"]]),
             "--remove-edges.isolated", "--geometry.remove", "--roundabouts.guess", "--ramps.guess",
             "--junctions.join", *tls, "--tls.default-type", "static",
             "--tls.cycle.time", str(int(net["tls_cycle_s"])),
             *turn_lane_opts(net, lefthand=True), "--output.street-names", "--output.original-names"]
            + logic_opts(net) + [str(o) for o in net["extra_netconvert_opts"]])


def stage2_tls_opts(net):
    """netconvert options that rebuild signal plans in stage 2 (T1-D10).

    Stage 2 otherwise keeps the stage-1 plans, whose phases still serve approaches the
    strong-component pass removed ("dead phases"). Rebuilding changes timings only:
    no edge, lane or connection.
    """
    if not net["tls_rebuild"]:
        return []
    return ["--tls.rebuild", "--tls.default-type", "static", "--tls.cycle.time", str(int(net["tls_cycle_s"]))]


def largest_scc(net):
    """Edge ids of the largest strongly connected component, and all component sizes."""
    edges = [e for e in net.getEdges() if e.allows("passenger")]
    g = nx.DiGraph()
    g.add_nodes_from(e.getID() for e in edges)
    for e in edges:
        for f in e.getOutgoing():
            if f.allows("passenger"):
                g.add_edge(e.getID(), f.getID())
    sccs = sorted(nx.strongly_connected_components(g), key=len, reverse=True)
    return sccs[0], [len(c) for c in sccs], edges


def passenger_lane_m(edge):
    """Length of the lanes of a sumolib edge that allow passenger cars, in m."""
    return sum(lane.getLength() for lane in edge.getLanes() if lane.allows("passenger"))


def xml_counts(net_path):
    """Edge, lane and lane-length counts split into normal and internal, read with ElementTree."""
    out = {k: Counter() for k in ("edges", "lanes", "length_m")}
    lefthand = None
    for ev, el in ET.iterparse(net_path, events=("start", "end")):
        if ev == "start":
            if el.tag == "net":
                lefthand = el.get("lefthand") == "true"
        elif el.tag == "edge":
            kind = "internal" if el.get("function") == "internal" else "normal"
            out["edges"][kind] += 1
            for lane in el.findall("lane"):
                out["lanes"][kind] += 1
                out["length_m"][kind] += float(lane.get("length"))
    return out, lefthand


def net_stats(net_path):
    """Port of the pilot's net_stats.py: counts, signal cycles, strong components."""
    net = sumolib.net.readNet(str(net_path), withPrograms=True)
    big, sizes, edges = largest_scc(net)
    by_id = {e.getID(): e for e in edges}
    lane_m = sum(passenger_lane_m(e) for e in edges)
    scc_m = sum(passenger_lane_m(by_id[i]) for i in big)
    lk_type = Counter()
    for i in big:
        lk_type[by_id[i].getType()] += passenger_lane_m(by_id[i]) / 1000
    cycles, types = Counter(), Counter()
    for t in net.getTrafficLights():
        for p in t.getPrograms().values():
            cycles[round(sum(ph.duration for ph in p.getPhases()), 3)] += 1
            types[getattr(p, "_type", "unknown")] += 1
    return {
        "junctions": len(net.getNodes()),
        "junction_types": dict(Counter(n.getType() for n in net.getNodes())),
        "edges_passenger": len(edges),
        "lane_km_passenger": round(lane_m / 1000, 2),
        "lane_m_passenger": round(lane_m, 2),
        "tls_count": len(net.getTrafficLights()),
        "tls_cycle_lengths_s": {str(k): v for k, v in sorted(cycles.items())},
        "tls_types": dict(types),
        "n_scc": len(sizes),
        "scc_sizes_top5": sizes[:5],
        "largest_scc_lane_km_share": round(scc_m / lane_m, 3) if lane_m else None,
        "largest_scc_lane_km_by_type": {k: round(v, 2) for k, v in lk_type.most_common()},
    }, big


def netconvert(args, cwd, log):
    """Run netconvert in cwd, write its log, return the error lines (empty if none)."""
    r = subprocess.run(["netconvert", *args, "--log", log, "--aggregate-warnings", "5"],
                       cwd=cwd, capture_output=True, text=True)
    text = Path(cwd, log).read_text()
    errors = [ln for ln in text.splitlines() if ln.startswith("Error")]
    if r.returncode != 0:
        raise RuntimeError(f"netconvert failed ({r.returncode}): {r.stderr[-2000:]}")
    return errors, sum(ln.startswith("Warning") for ln in text.splitlines())


def build(cfg, osm_dir, out_dir, run_dir):
    """Run both stages and write <name>.net.xml and <name>.meta.json; return the meta dict."""
    net_cfg = cfg["network"]
    name = cfg["name"]
    tiles = [Path(osm_dir) / f for f in net_cfg["osm_files"]]
    missing = [str(t) for t in tiles if not t.exists()]
    if missing:
        raise FileNotFoundError(f"OSM tiles missing (run scenarios/city/fetch_osm.py): {missing}")
    version = subprocess.run(["netconvert", "--version"], capture_output=True, text=True).stdout.splitlines()[0]
    turn_lanes = net_cfg["osm_turn_lanes"]
    if turn_lanes == "mirror" and MIRROR_CHECKED_ON not in version.split():
        raise RuntimeError(f'osm_turn_lanes = "mirror" undoes the left-hand turn:lanes mirroring of netconvert '
                           f"{MIRROR_CHECKED_ON}; this is {version!r}. Check that it still mirrors before building.")
    if turn_lanes == "as_is":
        print('warning: osm_turn_lanes = "as_is" builds OSM lane arrows mirrored in this left-hand net',
              file=sys.stderr)
    run_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    s2 = ["-s", "stage1.net.xml", "--keep-edges.input-file", "scc_edges.txt", *logic_opts(net_cfg),
          *stage2_tls_opts(net_cfg), "-o", f"{name}.net.xml"]
    with tempfile.TemporaryDirectory(prefix=f"city-{name}-") as tmp:
        s1, mirrored = stage1_args(net_cfg, tiles, tmp)   # mirrored tiles, if any, die with tmp
        err1, warn1 = netconvert(s1, tmp, "stage1.log")
        stats1, big = net_stats(Path(tmp, "stage1.net.xml"))
        Path(tmp, "scc_edges.txt").write_text("\n".join(sorted(big)) + "\n")
        err2, warn2 = netconvert(s2, tmp, "stage2.log")
        for f in ("stage1.net.xml", "stage1.log", "stage2.log", "scc_edges.txt"):
            Path(run_dir, f).write_bytes(Path(tmp, f).read_bytes())
        final = out_dir / f"{name}.net.xml"
        shutil.move(Path(tmp, f"{name}.net.xml"), final)
    stats, _ = net_stats(final)
    counts, lefthand = xml_counts(final)
    lane_m, int_m = counts["length_m"]["normal"], counts["length_m"]["internal"]
    show = lambda args: shlex.join(["netconvert", *args]).replace(str(osm_dir), "<osm_dir>").replace(str(ROOT) + "/", "")  # noqa: E731
    meta = {
        "name": name,
        "config": cfg["_path"],
        "config_sha256": cfg["_sha256"],
        "built_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "build_run_dir": str(run_dir.relative_to(ROOT)) if run_dir.is_relative_to(ROOT) else str(run_dir),
        "netconvert_version": version,
        "netconvert_stage1": show(s1),
        "netconvert_stage2": show(s2),
        "osm_sha256": {t.name: sha256(t) for t in tiles},
        "osm_turn_lanes": turn_lanes,
        "osm_turn_lanes_mirrored_values": mirrored,   # stage 1 reads osm_turn_lanes_mirrored/ copies if > 0
        "lefthand": lefthand,
        "lane_length_m": round(lane_m, 2),
        "internal_lane_length_m": round(int_m, 2),
        "internal_lane_share": round(int_m / (lane_m + int_m), 4),
        "edges_normal": counts["edges"]["normal"],
        "lanes_normal": counts["lanes"]["normal"],
        "edges_internal": counts["edges"]["internal"],
        "lanes_internal": counts["lanes"]["internal"],
        "passenger_lane_length_m": stats["lane_m_passenger"],
        **{k: stats[k] for k in ("junctions", "junction_types", "edges_passenger", "lane_km_passenger",
                                 "tls_count", "tls_cycle_lengths_s", "tls_types", "n_scc",
                                 "largest_scc_lane_km_by_type")},
        "tls_cycle_s": net_cfg["tls_cycle_s"],
        "tls_rebuild": net_cfg["tls_rebuild"],
        "stage1": {k: stats1[k] for k in ("junctions", "edges_passenger", "lane_km_passenger", "tls_count",
                                          "n_scc", "scc_sizes_top5", "largest_scc_lane_km_share")},
        "netconvert_warnings": {"stage1": warn1, "stage2": warn2},
        "netconvert_errors": err1 + err2,
        "provisional_on": net_cfg.get("provisional_on", []),
    }
    (out_dir / f"{name}.meta.json").write_text(json.dumps(meta, indent=1) + "\n")
    return meta


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", required=True, help="configs/city/<name>.toml")
    ap.add_argument("--osm-dir", default=None, help="folder of OSM tiles; default [network] osm_dir")
    ap.add_argument("--out-dir", default=None, help="default scenarios/city")
    args = ap.parse_args()
    cfg = config.load(args.config)
    osm_dir = Path(args.osm_dir or ROOT / cfg["network"]["osm_dir"]).resolve()
    out_dir = Path(args.out_dir or ROOT / "scenarios" / "city").resolve()
    run_id = f"city-build-{cfg['name']}-{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}"
    meta = build(cfg, osm_dir, out_dir, ROOT / "runs" / run_id)
    keys = ("junctions", "edges_normal", "lane_length_m", "internal_lane_length_m", "tls_count",
            "tls_cycle_lengths_s", "n_scc", "lefthand", "junction_types", "netconvert_errors")
    print(json.dumps({"net": str(out_dir / f"{cfg['name']}.net.xml"), "run_id": run_id,
                      **{k: meta[k] for k in keys}, "stage1": meta["stage1"]}, indent=1))


if __name__ == "__main__":
    main()
