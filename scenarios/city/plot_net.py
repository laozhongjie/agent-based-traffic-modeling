"""Map a built city network and trace what the strong-component pass removed.

Reads the committed net scenarios/city/<name>.net.xml and the stage-1 net kept in
the build's run folder (runs/city-build-<name>-*/stage1.net.xml, newest by
default). Draws kept roads, removed roads, signals and the study box, one panel
per config. For the edges removed *inside* the study box (not in the clip
margin) it prints the lane length of those more than --inset-m inside (default 600 m, as in the pilot), by road and by why they were removed:
  sink    reachable from the kept network but no way back out (a dead pocket),
  source  can reach the kept network but cannot be entered from it,
  apart   neither (a separate piece).

Usage (from the repository root, SUMO_HOME set):
    python -I scenarios/city/plot_net.py --config configs/city/bugis_all.toml \
        configs/city/bugis_art.toml --out runs/city-maps.png
"""
import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import networkx as nx  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

from traffic_project import ROOT, config  # noqa: E402

sys.path.append(os.path.join(os.environ["SUMO_HOME"], "tools"))
import sumolib  # noqa: E402

KEPT, REMOVED, SIGNAL, INK = "#2a78d6", "#b5b4ae", "#eb6834", "#1a1a19"


def lonlat_shape(net, edge):
    xs, ys = zip(*(net.convertXY2LonLat(x, y) for x, y in edge.getShape()))
    return xs, ys


def trace(stage1, kept_ids, box, inset_m):
    """Lane-km of removed edges whose midpoint lies more than inset_m inside the study box, by road and reason."""
    edges = [e for e in stage1.getEdges() if e.allows("passenger")]
    g = nx.DiGraph()
    g.add_nodes_from(e.getID() for e in edges)
    for e in edges:
        g.add_edges_from((e.getID(), f.getID()) for f in e.getOutgoing() if f.allows("passenger"))
    anchor = next(iter(kept_ids & set(g)))
    down, up = nx.descendants(g, anchor), nx.ancestors(g, anchor)
    w, s, e_, n = box
    by_reason, by_road = Counter(), Counter()
    for e in edges:
        if e.getID() in kept_ids:
            continue
        shape = e.getShape()
        lon, lat = stage1.convertXY2LonLat(*shape[len(shape) // 2])
        if min(lon - w, e_ - lon, lat - s, n - lat) * 111320 < inset_m:  # m inside the box (1 deg ~ 111.32 km)
            continue
        km = sum(lane.getLength() for lane in e.getLanes() if lane.allows("passenger")) / 1000
        reason = "sink" if e.getID() in down else "source" if e.getID() in up else "apart"
        by_reason[reason] += km
        by_road[(e.getName() or "(unnamed)", e.getType().split(".")[-1], reason)] += km
    return by_reason, by_road


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", nargs="+", required=True)
    ap.add_argument("--out", required=True, help="PNG path")
    ap.add_argument("--inset-m", type=float, default=600.0,
                    help="trace only removed edges this far inside the study box (pilot: 600 m; 0 = whole box)")
    args = ap.parse_args()
    fig, axes = plt.subplots(1, len(args.config), figsize=(5.2 * len(args.config), 5.6), squeeze=False)
    for ax, path in zip(axes[0], args.config):
        cfg = config.load(path)
        name, box = cfg["name"], cfg["network"]["study_box"]
        net = sumolib.net.readNet(str(ROOT / "scenarios" / "city" / f"{name}.net.xml"))
        run = sorted((ROOT / "runs").glob(f"city-build-{name}-*"))[-1]
        stage1 = sumolib.net.readNet(str(run / "stage1.net.xml"))
        kept = {e.getID() for e in net.getEdges()}
        for e in stage1.getEdges():
            if e.allows("passenger") and e.getID() not in kept:
                ax.plot(*lonlat_shape(stage1, e), color=REMOVED, lw=0.8, solid_capstyle="round")
        for e in net.getEdges():
            ax.plot(*lonlat_shape(net, e), color=KEPT, lw=0.5 + 0.35 * e.getLaneNumber(), solid_capstyle="round")
        tls = [net.convertXY2LonLat(*t.getConnections()[0][0].getEdge().getToNode().getCoord())
               for t in net.getTrafficLights()]
        ax.scatter(*zip(*tls), s=14, color=SIGNAL, edgecolor="white", linewidth=0.6, zorder=3)
        w, s, e_, n = box
        ax.plot([w, e_, e_, w, w], [s, s, n, n, s], color=INK, lw=0.9, ls="--")
        m = json.loads((ROOT / "scenarios" / "city" / f"{name}.meta.json").read_text())
        ax.set_title(f"{name}: {m['edges_normal']} edges, {m['lane_length_m'] / 1000:.2f} lane-km, "
                     f"{m['tls_count']} signals", fontsize=9.5, color=INK)
        ax.set_aspect("equal")
        ax.ticklabel_format(useOffset=False)
        ax.set_xlabel("longitude (deg)", fontsize=8.5)
        ax.set_ylabel("latitude (deg)", fontsize=8.5)
        ax.tick_params(labelsize=7.5, colors="#55544f")
        for sp in ax.spines.values():
            sp.set_color("#d8d7d1")
        by_reason, by_road = trace(stage1, kept, box, args.inset_m)
        print(f"{name}: removed > {args.inset_m:.0f} m inside study box {sum(by_reason.values()):.2f} lane-km; by reason "
              + ", ".join(f"{k} {v:.2f}" for k, v in by_reason.most_common()))
        for (road, typ, reason), km in by_road.most_common(10):
            print(f"  {km:6.2f} lane-km  {road} ({typ}, {reason})")
    handles = [Line2D([], [], color=KEPT, lw=1.6, label="kept road (width ~ lanes)"),
               Line2D([], [], color=REMOVED, lw=1.2, label="removed: not in the strong component"),
               Line2D([], [], color=SIGNAL, marker="o", ls="", markersize=5, label="signal (fixed-time)"),
               Line2D([], [], color=INK, lw=0.9, ls="--", label="study box")]
    fig.legend(handles=handles, loc="lower center", ncol=4, fontsize=8, frameon=False)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, dpi=140)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
