"""Build the n x n test grid for SUMO in three planning variants.

All variants share one node file and differ only in their edge files:
  base     every block of the grid, two-way
  closure  the highest-betweenness segment removed in both directions, or with
           --closure lanecut one lane taken away in both directions (needs --lanes >= 2)
  newlink  one extra two-way link chosen by the new-link rule below
As on the ring, edge lengths are set explicitly and internal junction lanes are
disabled, so total lane length is exact and density = vehicles / lane length.

Both selection rules are deterministic, so the same rules can pick the changes
on C's district network later:
  closure  the segment (both directions together) with the largest edge
           betweenness of length-weighted shortest paths; ties go to the
           smallest segment id
  newlink  among node pairs that are not yet linked and at most
           --newlink-max-len apart, the pair whose two-way link most reduces the
           sum of all-pairs shortest-path lengths; ties go to the smallest ids
On a grid the default maximum length (one block diagonal) limits candidates to
the diagonals of single blocks, which cross no existing road.

Each variant also gets <stem>.meta.json with its lane length, the baseline lane
length, what was changed and the ranked candidates, so density can be quoted
against either length and the choice can be checked.

Usage:
    python build_net.py --n 4 --block 200 --speed 13.89 --lanes 1 --junction traffic_light
Writes grid<n>x<n>_L<block>.nod.xml (shared) and, per variant,
grid<n>x<n>_L<block>_<variant>.edg.xml, .net.xml and .meta.json next to this script.
Needs networkx and SUMO's netconvert.
"""
import argparse
import itertools
import json
import math
import subprocess
from pathlib import Path

import networkx as nx

VARIANTS = ("base", "closure", "newlink")


def node_id(r, c):
    return f"n{r}_{c}"


def edge_id(a, b):
    return f"{a}-{b}"


def segment_id(a, b):
    """Name of the two-way road between a and b, independent of direction."""
    return "~".join(sorted((a, b)))


def grid_nodes(n, block):
    return {node_id(r, c): (c * block, r * block) for r in range(n) for c in range(n)}


def grid_segments(n, block):
    """Two-way blocks of the grid as (a, b, length)."""
    segs = []
    for r in range(n):
        for c in range(n):
            if c + 1 < n:
                segs.append((node_id(r, c), node_id(r, c + 1), block))
            if r + 1 < n:
                segs.append((node_id(r, c), node_id(r + 1, c), block))
    return segs


def digraph(segs):
    g = nx.DiGraph()
    for a, b, length in segs:
        g.add_edge(a, b, length=length)
        g.add_edge(b, a, length=length)
    return g


def rank_closures(segs):
    """Segments ranked by summed edge betweenness of both directions."""
    bc = nx.edge_betweenness_centrality(digraph(segs), weight="length", normalized=False)
    score = {}
    for (u, v), b in bc.items():
        score[segment_id(u, v)] = score.get(segment_id(u, v), 0.0) + b
    # Round so float noise cannot break symmetric ties differently on another machine.
    return sorted(((round(s, 6), sid) for sid, s in score.items()), key=lambda t: (-t[0], t[1]))


def total_path_length(g):
    return sum(d for _, dist in nx.all_pairs_dijkstra_path_length(g, weight="length")
               for d in dist.values())


def rank_newlinks(nodes, segs, max_len):
    """Candidate links ranked by the reduction in summed all-pairs shortest-path length."""
    g = digraph(segs)
    base_total = total_path_length(g)
    ranked = []
    for a, b in itertools.combinations(sorted(nodes), 2):
        if g.has_edge(a, b):
            continue
        length = math.dist(nodes[a], nodes[b])
        if length > max_len + 1e-9:
            continue
        h = g.copy()
        h.add_edge(a, b, length=length)
        h.add_edge(b, a, length=length)
        ranked.append((round(base_total - total_path_length(h), 6), a, b, round(length, 3)))
    return sorted(ranked, key=lambda t: (-t[0], t[1], t[2]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=4, help="junctions per side")
    ap.add_argument("--block", type=float, default=200.0, help="block length in m")
    ap.add_argument("--speed", type=float, default=13.89, help="lane speed limit in m/s")
    ap.add_argument("--lanes", type=int, default=1, help="lanes per direction")
    ap.add_argument("--junction", default="traffic_light",
                    choices=["traffic_light", "priority", "right_before_left"],
                    help="control at junctions with 3 or more neighbours")
    ap.add_argument("--closure", default="remove", choices=["remove", "lanecut"])
    ap.add_argument("--newlink-max-len", type=float, default=None,
                    help="longest allowed new link in m, default one block diagonal")
    ap.add_argument("--out", default=None, help="file stem, default grid<n>x<n>_L<block>")
    args = ap.parse_args()
    if args.closure == "lanecut" and args.lanes < 2:
        raise SystemExit("--closure lanecut needs --lanes 2 or more")

    here = Path(__file__).resolve().parent
    stem = here / (args.out or f"grid{args.n}x{args.n}_L{int(args.block)}")
    nodes = grid_nodes(args.n, args.block)
    segs = grid_segments(args.n, args.block)
    max_len = args.newlink_max_len or args.block * math.sqrt(2)

    closures = rank_closures(segs)
    closed = closures[0][1]
    newlinks = rank_newlinks(nodes, segs, max_len)
    if not newlinks:
        raise SystemExit(f"no new-link candidates within {max_len:g} m")
    _, link_a, link_b, link_len = newlinks[0]

    # Corners are only bends, so a signal there would add stops without any conflict.
    degree = {k: 0 for k in nodes}
    for a, b, _ in segs:
        degree[a] += 1
        degree[b] += 1
    node_lines = [f'    <node id="{k}" x="{x:.3f}" y="{y:.3f}" '
                  f'type="{args.junction if degree[k] >= 3 else "priority"}"/>'
                  for k, (x, y) in nodes.items()]
    Path(f"{stem}.nod.xml").write_text("<nodes>\n" + "\n".join(node_lines) + "\n</nodes>\n")

    def lane_length(variant_segs):
        return sum(2 * length * lanes for _, _, length, lanes in variant_segs)

    base = [(a, b, length, args.lanes) for a, b, length in segs]
    variants = {"base": (base, {"type": "none"})}
    if args.closure == "remove":
        closure_segs = [s for s in base if segment_id(s[0], s[1]) != closed]
    else:
        closure_segs = [(a, b, length, lanes - 1 if segment_id(a, b) == closed else lanes)
                        for a, b, length, lanes in base]
    variants["closure"] = (closure_segs, {
        "type": args.closure, "segment": closed,
        "edges": [edge_id(*closed.split("~")), edge_id(*reversed(closed.split("~")))],
        "rule": "largest summed edge betweenness, length-weighted; ties to smallest id",
        "ranking": [{"segment": sid, "betweenness": b} for b, sid in closures[:8]],
    })
    variants["newlink"] = (base + [(link_a, link_b, link_len, args.lanes)], {
        "type": "add", "segment": segment_id(link_a, link_b),
        "edges": [edge_id(link_a, link_b), edge_id(link_b, link_a)], "length_m": link_len,
        "rule": f"largest cut in summed all-pairs shortest paths, length <= {max_len:.3f} m; "
                "ties to smallest ids",
        "ranking": [{"segment": segment_id(a, b), "reduction_m": red, "length_m": ln}
                    for red, a, b, ln in newlinks[:8]],
    })

    base_lane_length = lane_length(base)
    for name, (vsegs, change) in variants.items():
        g = digraph([(a, b, length) for a, b, length, lanes in vsegs if lanes > 0])
        if not nx.is_strongly_connected(g):
            raise SystemExit(f"variant {name} is not strongly connected")
        edge_lines = []
        for a, b, length, lanes in vsegs:
            for u, v in ((a, b), (b, a)):
                edge_lines.append(f'    <edge id="{edge_id(u, v)}" from="{u}" to="{v}" '
                                  f'numLanes="{lanes}" speed="{args.speed}" '
                                  f'length="{length:.3f}"/>')
        vstem = f"{stem}_{name}"
        Path(f"{vstem}.edg.xml").write_text("<edges>\n" + "\n".join(edge_lines) + "\n</edges>\n")
        subprocess.run(["netconvert",
                        "--node-files", f"{stem}.nod.xml",
                        "--edge-files", f"{vstem}.edg.xml",
                        "--no-internal-links", "true",
                        "--offset.disable-normalization", "true",
                        "--output-file", f"{vstem}.net.xml"], check=True)
        meta = {
            "variant": name, "n": args.n, "block_m": args.block, "speed_mps": args.speed,
            "lanes": args.lanes, "junction": args.junction,
            "edges": len(edge_lines),
            "lane_length_m": round(lane_length(vsegs), 3),
            "baseline_lane_length_m": round(base_lane_length, 3),
            "change": change,
        }
        Path(f"{vstem}.meta.json").write_text(json.dumps(meta, indent=2) + "\n")
        print(f"wrote {Path(vstem).name}.net.xml  ({len(edge_lines)} edges, "
              f"lane length {meta['lane_length_m']:g} m)")
    print(f"closure: {closed} ({args.closure});  new link: {segment_id(link_a, link_b)} "
          f"({link_len:g} m)")


if __name__ == "__main__":
    main()
