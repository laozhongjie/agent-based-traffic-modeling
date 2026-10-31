"""Build the planning variants of a city net: road closure, lane cut and new link.

Each variant is the base net plus one small patch file, compiled by netconvert:
  closure  the chosen segment deleted in both directions (<delete> in the patch)
  lanecut  the same segment with --lanes-removed lanes taken away in each direction
  newlink  one new two-way road between two existing junctions
Rebuilding the base net with no patch reproduces it exactly (checked), so every
difference between a variant and the base comes from its patch. The script checks
this: it reports every edge, connection, junction and signal program that changed.

Selection rules (deterministic, so they can be rerun when the base net changes):
  segment  a road between two junctions: one edge, plus its reverse edge if two-way
  closure  the segment with the largest summed edge betweenness of shortest paths by
           free-flow travel time (length / speed limit) between all junction pairs, among
           segments whose removal leaves every car edge reachable from every other (the
           constant-density controller needs that); ties go to the smallest edge ids
  lanecut  the closure's segment, so closure and lane cut are two severities of one change
  newlink  among junction pairs with no road between them, both unsignalised (a new leg at
           a signal would change its signal program), --newlink-min-m to --newlink-max-m
           apart in a straight line: the pair whose two-way link most reduces the sum of
           all-pairs free-flow travel times; ties go to the smallest ids
On the 4x4 grid every speed limit is equal, so these rules reduce to the length-based
ones in scenarios/grid/build_net.py.

If netconvert rebuilds the inside of some junctions differently from the base net (roads,
road-to-road turns and signal programs identical), the script stops; with
--allow-internal-rebuild it writes that rebuilt base as <stem>_base.net.xml, builds the variants
from it and compares them with it, so it must also be the planning baseline.

Usage (from the repository root):
    python scenarios/city/build_planning.py --net scenarios/city/bugis_all.net.xml
Writes, next to the base net, <stem>_<variant>.patch.xml (plus .con.xml, the new link's turns),
.net.xml and .meta.json
(lane lengths of the variant and the base, the change, the ranked candidates and
the build check), and prints a summary. Needs networkx, numpy, scipy and SUMO.
"""
import argparse
import json
import math
import re
import subprocess
from pathlib import Path

import networkx as nx
import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra

try:
    import sumolib
except ImportError:  # SUMO's tools folder, as in traffic_project.runner
    import os
    import sys
    sys.path.append(os.path.join(os.environ["SUMO_HOME"], "tools"))
    import sumolib

VARIANTS = ("closure", "lanecut", "newlink")
NETCONVERT_OPTIONS = ["--offset.disable-normalization", "true"]


# --- network graphs ----------------------------------------------------------------------------

def car_successors(net):
    """{car edge: edges a passenger car can turn into from it}."""
    out = {}
    for e in net.getEdges():
        if any(ln.allows("passenger") for ln in e.getLanes()):
            out[e.getID()] = {to.getID() for to, conns in e.getOutgoing().items()
                              if any(c.getFromLane().allows("passenger") and c.getToLane().allows("passenger")
                                     for c in conns)}
    return out


def unreachable(succ, removed=()):
    """Car edges outside the largest strongly connected component once `removed` is gone."""
    g = nx.DiGraph()
    for e, ws in succ.items():
        if e in removed:
            continue
        g.add_node(e)
        g.add_edges_from((e, w) for w in ws if w not in removed)
    largest = max(nx.strongly_connected_components(g), key=len, default=set())
    return sorted(set(g) - largest)


def junction_graph(net):
    """Directed junction graph weighted by free-flow time t (s); parallel edges keep the fastest."""
    g = nx.DiGraph()
    for e in net.getEdges():
        u, v, t = e.getFromNode().getID(), e.getToNode().getID(), e.getLength() / e.getSpeed()
        if not g.has_edge(u, v) or g[u][v]["t"] > t:
            g.add_edge(u, v, t=t, eid=e.getID())
    return g


def segments(net):
    """{segment id: sorted edge ids}: each edge with its reverse edge(s), if any."""
    by_pair = {}
    for e in net.getEdges():
        by_pair.setdefault((e.getFromNode().getID(), e.getToNode().getID()), []).append(e.getID())
    out = {}
    for (u, v), ids in by_pair.items():
        seg = tuple(sorted(ids + by_pair.get((v, u), [])))
        out["~".join(seg)] = seg
    return out


# --- selection rules ---------------------------------------------------------------------------

def rank_closures(net, g, succ):
    bc = nx.edge_betweenness_centrality(g, weight="t", normalized=False)
    edge_bc = {g[u][v]["eid"]: b for (u, v), b in bc.items()}
    ranked = []
    for sid, seg in segments(net).items():
        score = round(sum(edge_bc.get(e, 0.0) for e in seg), 3)
        ranked.append((score, sid, seg))
    ranked.sort(key=lambda t: (-t[0], t[1]))
    out = []
    for score, sid, seg in ranked:
        cut = unreachable(succ, set(seg)) if len(out) < 40 or not any(o["keeps_connected"] for o in out) else None
        out.append({"segment": sid, "edges": list(seg), "betweenness": score,
                    "keeps_connected": cut == [] if cut is not None else None,
                    "cut_off_edges": len(cut) if cut is not None else None})
        if any(o["keeps_connected"] for o in out) and len(out) >= 12:
            break
    return out


def rank_newlinks(net, g, min_m, max_m, speed, top=12, assume=()):
    """Rank new-link candidates. `assume`: junction pairs (a, b) of real roads missing from the
    net; they count as existing two-way roads while ranking, so candidates that only bridge the
    same gap lose their gain, and the pairs themselves are never chosen."""
    g = g.copy()
    for a, b in assume:
        t = math.dist(net.getNode(a).getCoord(), net.getNode(b).getCoord()) / speed
        g.add_edge(a, b, t=t, eid=None)
        g.add_edge(b, a, t=t, eid=None)
    nodes = sorted(g.nodes)
    idx = {n: i for i, n in enumerate(nodes)}
    r, c, w = zip(*[(idx[u], idx[v], d["t"]) for u, v, d in g.edges(data=True)])
    D = dijkstra(csr_matrix((w, (r, c)), shape=(len(nodes), len(nodes))), directed=True)
    finite = np.isfinite(D)
    total = float(D[finite].sum())
    signalised = {n.getID() for n in net.getNodes() if n.getType().startswith("traffic_light")}
    ok = [n for n in nodes if n not in signalised and net.getNode(n).getType() not in ("internal", "dead_end")]
    xy = {n: net.getNode(n).getCoord() for n in ok}
    ranked = []
    for i, a in enumerate(ok):
        for b in ok[i + 1:]:
            if g.has_edge(a, b) or g.has_edge(b, a):
                continue
            length = math.dist(xy[a], xy[b])
            if not min_m <= length <= max_m:
                continue
            t, ia, ib = length / speed, idx[a], idx[b]
            via = np.minimum(D[:, ia][:, None] + t + D[ib][None, :], D[:, ib][:, None] + t + D[ia][None, :])
            gain = float((D - np.minimum(D, via))[finite].sum())
            ranked.append((round(gain, 3), a, b, round(length, 3), float(D[ia, ib]), float(D[ib, ia])))
    ranked.sort(key=lambda x: (-x[0], x[1], x[2]))
    def where(n):
        x, y = net.getNode(n).getCoord()
        try:
            lon, lat = net.convertXY2LonLat(x, y)
            ll = [round(lat, 5), round(lon, 5)]
        except Exception:   # no pyproj: skip coordinates
            ll = None
        names = sorted({e.getName() for e in net.getNode(n).getIncoming() + net.getNode(n).getOutgoing()
                        if e.getName()})
        return {"streets": names, "lat_lon": ll}

    return total, [{"from": a, "to": b, "from_at": where(a), "to_at": where(b),
                    "length_m": length, "gain_s": gain,
                    "gain_share": round(gain / total, 6),
                    "free_flow_time_now_s": [round(dab, 1), round(dba, 1)]}
                   for gain, a, b, length, dab, dba in ranked[:top]]


# --- building and checking ---------------------------------------------------------------------

def elements(path):
    """{tag: {id: xml text}} for the parts of a net that a patch can change."""
    text = Path(path).read_text()
    body = text[text.index("<net "):]
    out = {}
    for tag in ("edge", "junction", "tlLogic"):
        items = re.findall(rf"<{tag}\b.*?(?:/>|</{tag}>)", body, re.S)
        out[tag] = {re.search(r'id="([^"]+)"', x).group(1): x for x in items}
    conns = re.findall(r"<connection\b[^>]*/>", body)
    out["connection"] = {re.sub(r'\s(?:linkIndex|tl|state|dir|via)="[^"]*"', "", x): x for x in conns}
    return out


def diff(base, variant):
    out = {}
    for tag in base:
        b, v = base[tag], variant[tag]
        out[tag] = {"removed": sorted(set(b) - set(v)), "added": sorted(set(v) - set(b)),
                    "changed": sorted(k for k in set(b) & set(v) if b[k] != v[k])}
    return out


def is_lefthand(path):
    """True for a left-hand-traffic net (lefthand="true" on its <net> element)."""
    with open(path) as f:
        for line in f:
            if line.lstrip().startswith("<net "):
                return 'lefthand="true"' in line
    return False


def lane_length_m(net):
    """Total length of the normal lanes that allow passenger cars (the controller's lanes)."""
    return sum(e.getLength() * sum(ln.allows("passenger") for ln in e.getLanes()) for e in net.getEdges())


def netconvert(base, out, patch=None, connections=None):
    cmd = ["netconvert", "-s", str(base), "-o", str(out), *NETCONVERT_OPTIONS]
    if patch:
        cmd += ["-e", str(patch)]
    if connections:
        cmd += ["-x", str(connections)]
    subprocess.run(cmd, check=True, capture_output=True, text=True)


def _heading(p, q):
    return math.atan2(q[1] - p[1], q[0] - p[0])


def _turn(h_in, h_out):
    """Signed turn angle in degrees, positive to the left."""
    return (math.degrees(h_out - h_in) + 180) % 360 - 180


def newlink_connections(net, a, b, ids, lanes, lefthand):
    """Connection lines for a new two-way link a <-> b (ids: [a->b, b->a]).

    netconvert keeps the connections it loads with the base net and builds none for new
    edges, so they are written here: every car approach into the link, and from the link
    into every car exit, except U-turns. A turn towards the kerb uses the kerb lane (lane 0),
    a turn towards the centre the centre lane, straight on lane 0; lane 0 is the kerb lane
    on both left- and right-hand nets, and the net's handedness decides which side that is.
    """
    xy = {n: net.getNode(n).getCoord() for n in (a, b)}
    head = {ids[0]: _heading(xy[a], xy[b]), ids[1]: _heading(xy[b], xy[a])}
    out = []

    def kerb_side(turn):            # True when the turn goes towards the kerb
        return turn > 30 if lefthand else turn < -30

    def centre_side(turn):
        return turn < -30 if lefthand else turn > 30

    for node, link_out, link_in, other in ((a, ids[0], ids[1], b), (b, ids[1], ids[0], a)):
        nd = net.getNode(node)
        for e in nd.getIncoming():          # approaches into the new link
            car = [ln.getIndex() for ln in e.getLanes() if ln.allows("passenger")]
            if not car or e.getFromNode().getID() == other:
                continue
            shape = e.getShape()
            t = _turn(_heading(shape[-2], shape[-1]), head[link_out])
            if abs(t) > 150:
                continue                    # U-turn
            from_lane = min(car) if kerb_side(t) else max(car) if centre_side(t) else min(car)
            out.append(f'    <connection from="{e.getID()}" to="{link_out}" fromLane="{from_lane}" toLane="0"/>')
        for e in nd.getOutgoing():          # from the new link into exits
            car = [ln.getIndex() for ln in e.getLanes() if ln.allows("passenger")]
            if not car or e.getToNode().getID() == other:
                continue
            shape = e.getShape()
            t = _turn(head[link_in], _heading(shape[0], shape[1]))
            if abs(t) > 150:
                continue
            to_lane = min(car) if not centre_side(t) else max(car)
            from_lane = 0 if not centre_side(t) else lanes - 1
            out.append(f'    <connection from="{link_in}" to="{e.getID()}" fromLane="{from_lane}" toLane="{to_lane}"/>')
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--net", required=True, help="base net, e.g. scenarios/city/bugis_all.net.xml")
    ap.add_argument("--lanes-removed", type=int, default=1, help="lanes taken away per direction in lanecut")
    ap.add_argument("--newlink-min-m", type=float, default=20.0)
    ap.add_argument("--newlink-max-m", type=float, default=200.0)
    ap.add_argument("--newlink-speed", type=float, default=13.89, help="m/s, the net's most common limit")
    ap.add_argument("--newlink-lanes", type=int, default=1, help="lanes per direction")
    ap.add_argument("--allow-internal-rebuild", action="store_true",
                    help="if netconvert rebuilds only the inside of some junctions differently, build the "
                         "variants from that rebuilt base (<stem>_base.net.xml) instead of stopping")
    ap.add_argument("--assume-existing", action="append", default=[], metavar="A:B",
                    help="junction ids A:B of a real road missing from the net; ranked as if it "
                         "existed (repeatable)")
    args = ap.parse_args()

    base_path = Path(args.net).resolve()
    stem = base_path.with_name(base_path.name.removesuffix(".net.xml"))
    net = sumolib.net.readNet(str(base_path), withInternal=False)
    succ = car_successors(net)
    if unreachable(succ):
        raise SystemExit(f"{base_path.name}: some car edges are unreachable before any change")

    # The rebuild must reproduce the base exactly, or patch effects cannot be isolated.
    check = Path(f"{stem}_rebuild_check.net.xml")
    netconvert(base_path, check)
    base_el, source, rebuilt_base = elements(base_path), base_path, None
    rd = diff(base_el, elements(check))
    if any(d["removed"] or d["added"] or d["changed"] for d in rd.values()):
        # What a rebuild changes outside junction internals would change the network itself.
        real = {"normal edges": [k for v in rd["edge"].values() for k in v if not k.startswith(":")],
                "road-to-road turns": [c for k in ("removed", "added") for c in rd["connection"][k]
                                       if 'from=":' not in c],
                "signal programs": [k for v in rd["tlLogic"].values() for k in v]}
        where = sorted(k for k in rd["junction"]["changed"] if not k.startswith(":"))
        if any(real.values()):
            raise SystemExit("netconvert does not reproduce the base net unchanged, and the differences "
                             f"go beyond junction internals: {real}; patches cannot be isolated")
        if not args.allow_internal_rebuild:
            raise SystemExit(
                "netconvert rebuilds the inside of these junctions differently from the base net: "
                f"{where}. Roads, road-to-road turns and signal programs are identical. Rerun with "
                "--allow-internal-rebuild to build the variants from the rebuilt base "
                f"({stem.name}_base.net.xml), and use that file as the planning baseline.")
        rebuilt_base = Path(f"{stem}_base.net.xml")
        check.replace(rebuilt_base)
        base_el, source = elements(rebuilt_base), rebuilt_base
        if any(d["removed"] or d["added"] or d["changed"] for d in diff(base_el, elements(
                (netconvert(rebuilt_base, check), check)[1])).values()):
            raise SystemExit(f"{rebuilt_base.name} is not stable under a second rebuild")
        Path(f"{stem}_base.meta.json").write_text(json.dumps({
            "variant": "base", "source_net": base_path.name, "net": rebuilt_base.name,
            "why": "netconvert rebuilds the inside of some junctions differently from the source net; "
                   "roads, road-to-road turns and signal programs are identical. Use this file as the "
                   "planning baseline so that variants differ from it only by their patch.",
            "junctions_rebuilt": where,
            "internal_edges_changed": sum(len(v) for v in rd["edge"].values()),
        }, indent=2) + "\n")
        print(f"note: netconvert rebuilds the inside of {where} differently; variants are built from "
              f"{rebuilt_base.name}, which is the planning baseline")
    check.unlink()

    g = junction_graph(net)
    closures = rank_closures(net, g, succ)
    chosen = next(c for c in closures if c["keeps_connected"])
    seg = [net.getEdge(e) for e in chosen["edges"]]
    if min(e.getLaneNumber() for e in seg) <= args.lanes_removed:
        raise SystemExit(f"segment {chosen['segment']} has too few lanes for --lanes-removed {args.lanes_removed}")
    assume = [tuple(x.split(":", 1)) for x in args.assume_existing]
    for a, b in assume:
        if not (net.hasNode(a) and net.hasNode(b)):
            raise SystemExit(f"--assume-existing {a}:{b}: unknown junction id")
    total_time, newlinks = rank_newlinks(net, g, args.newlink_min_m, args.newlink_max_m,
                                         args.newlink_speed, assume=assume)
    if not newlinks:
        raise SystemExit("no new-link candidates; widen --newlink-min-m/--newlink-max-m")
    link = newlinks[0]
    link_ids = [f"newlink_{link['from']}_{link['to']}", f"newlink_{link['to']}_{link['from']}"]

    patches = {
        "closure": [f'    <delete id="{e.getID()}"/>' for e in seg],
        "lanecut": [f'    <edge id="{e.getID()}" numLanes="{e.getLaneNumber() - args.lanes_removed}"/>'
                    for e in seg],
        "newlink": [f'    <edge id="{eid}" from="{u}" to="{v}" numLanes="{args.newlink_lanes}" '
                    f'speed="{args.newlink_speed}" length="{link["length_m"]:.3f}"/>'
                    for eid, u, v in ((link_ids[0], link["from"], link["to"]),
                                      (link_ids[1], link["to"], link["from"]))],
    }
    changes = {
        "closure": {"type": "remove", "segment": chosen["segment"], "edges": chosen["edges"],
                    "street": seg[0].getName(), "road_type": seg[0].getType(),
                    "lanes": [e.getLaneNumber() for e in seg]},
        "lanecut": {"type": "lanecut", "segment": chosen["segment"], "edges": chosen["edges"],
                    "street": seg[0].getName(), "lanes_before": [e.getLaneNumber() for e in seg],
                    "lanes_after": [e.getLaneNumber() - args.lanes_removed for e in seg]},
        "newlink": {"type": "add", "edges": link_ids, "from": link["from"], "to": link["to"],
                    "length_m": link["length_m"], "speed_mps": args.newlink_speed,
                    "lanes": args.newlink_lanes},
    }
    rules = {
        "closure": "largest summed edge betweenness by free-flow time, among segments whose removal keeps "
                   "every car edge reachable; ties to smallest ids",
        "lanecut": f"the closure's segment, {args.lanes_removed} lane(s) removed per direction",
        "newlink": f"largest cut in summed all-pairs free-flow time; both ends unsignalised; "
                   f"{args.newlink_min_m:g}-{args.newlink_max_m:g} m straight line; ties to smallest ids"
                   + (f"; ranked as if these missing real roads existed: {args.assume_existing}"
                      if assume else ""),
    }
    base_len = lane_length_m(net)
    print(f"base: {len(net.getEdges())} edges, car lane length {base_len / 1000:.3f} km")
    for name in VARIANTS:
        patch = Path(f"{stem}_{name}.patch.xml")
        patch.write_text("<edges>\n" + "\n".join(patches[name]) + "\n</edges>\n")
        out = Path(f"{stem}_{name}.net.xml")
        conns = None
        if name == "newlink":
            conns = Path(f"{stem}_{name}.con.xml")
            conns.write_text("<connections>\n" + "\n".join(newlink_connections(
                net, link["from"], link["to"], link_ids, args.newlink_lanes, is_lefthand(source)))
                + "\n</connections>\n")
        netconvert(source, out, patch, conns)
        vnet = sumolib.net.readNet(str(out), withInternal=False)
        cut = unreachable(car_successors(vnet))
        if cut:
            raise SystemExit(f"{out.name}: {len(cut)} car edges unreachable, e.g. {cut[:5]}")
        d = diff(base_el, elements(out))
        normal = {k: [x for x in v if not x.startswith(":")] for k, v in d["edge"].items()}
        meta = {
            "variant": name, "base_net": source.name, "net": out.name,
            "patch": [patch.name] + ([conns.name] if conns else []),
            "lane_length_m": round(lane_length_m(vnet), 3), "baseline_lane_length_m": round(base_len, 3),
            "change": dict(changes[name], rule=rules[name]),
            "build_check": {
                "all_car_edges_reachable": True,
                "normal_edges": normal,
                "junctions_changed": d["junction"]["changed"] + d["junction"]["added"],
                "signal_programs_changed": d["tlLogic"]["changed"] + d["tlLogic"]["added"]
                                           + d["tlLogic"]["removed"],
                # between normal edges; junction-internal ones are renumbered, not real changes
                "connections_removed": [c for c in d["connection"]["removed"] if 'from=":' not in c],
                "connections_added": [c for c in d["connection"]["added"] if 'from=":' not in c],
            },
            "ranking": closures[:12] if name != "newlink" else newlinks,
        }
        if name == "newlink":
            meta["baseline_all_pairs_free_flow_time_s"] = round(total_time, 1)
        Path(f"{stem}_{name}.meta.json").write_text(json.dumps(meta, indent=2) + "\n")
        bc = meta["build_check"]
        print(f"{name:8s} lane length {meta['lane_length_m'] / 1000:.3f} km; normal edges "
              f"-{len(normal['removed'])} +{len(normal['added'])} ~{len(normal['changed'])}; "
              f"junctions changed {len(bc['junctions_changed'])}; signal programs changed "
              f"{len(bc['signal_programs_changed'])}; road-to-road turns -{len(bc['connections_removed'])} "
              f"+{len(bc['connections_added'])}")
    print(f"closure/lanecut: {chosen['segment']} ({seg[0].getName() or 'unnamed'}, {seg[0].getType()}); "
          f"higher-ranked segments that would cut the network: "
          f"{sum(1 for c in closures[:closures.index(chosen)])}")
    print(f"newlink: {link['from']} <-> {link['to']} ({link['length_m']:g} m, "
          f"{link['gain_share'] * 100:.2f}% less all-pairs free-flow time)")


if __name__ == "__main__":
    main()
