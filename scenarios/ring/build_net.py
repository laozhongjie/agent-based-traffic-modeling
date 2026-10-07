"""Build a single-lane closed ring road for SUMO.

The ring is split into four curved edges (an edge cannot start and end at the
same node). Internal junction lanes are disabled so the drivable length equals
the sum of the edge lengths, which keeps density = vehicles / length exact.

Usage:
    python build_net.py --length 1000 --speed 30 --out ring_1000
Writes <out>.nod.xml, <out>.edg.xml and <out>.net.xml next to this script.
"""
import argparse
import math
import subprocess
from pathlib import Path

N_EDGES = 4
ARC_POINTS = 12  # shape points per edge, only for a round look in sumo-gui


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--length", type=float, default=1000.0, help="ring length in m")
    ap.add_argument("--speed", type=float, default=30.0, help="lane speed limit in m/s")
    ap.add_argument("--out", default=None, help="file stem, default ring_<length>")
    args = ap.parse_args()

    here = Path(__file__).resolve().parent
    stem = here / (args.out or f"ring_{int(args.length)}")
    radius = args.length / (2 * math.pi)
    edge_len = args.length / N_EDGES

    def point(angle):
        return f"{radius * math.cos(angle):.3f},{radius * math.sin(angle):.3f}"

    nodes = [f'    <node id="n{i}" x="{radius * math.cos(2 * math.pi * i / N_EDGES):.3f}" '
             f'y="{radius * math.sin(2 * math.pi * i / N_EDGES):.3f}" type="priority"/>'
             for i in range(N_EDGES)]
    edges = []
    for i in range(N_EDGES):
        a0, a1 = 2 * math.pi * i / N_EDGES, 2 * math.pi * (i + 1) / N_EDGES
        shape = " ".join(point(a0 + (a1 - a0) * k / ARC_POINTS) for k in range(ARC_POINTS + 1))
        # `length` overrides the geometric length so every edge is exactly L/4.
        edges.append(f'    <edge id="e{i}" from="n{i}" to="n{(i + 1) % N_EDGES}" numLanes="1" '
                     f'speed="{args.speed}" length="{edge_len:.3f}" shape="{shape}"/>')

    Path(f"{stem}.nod.xml").write_text("<nodes>\n" + "\n".join(nodes) + "\n</nodes>\n")
    Path(f"{stem}.edg.xml").write_text("<edges>\n" + "\n".join(edges) + "\n</edges>\n")
    subprocess.run(["netconvert",
                    "--node-files", f"{stem}.nod.xml",
                    "--edge-files", f"{stem}.edg.xml",
                    "--no-internal-links", "true",
                    "--output-file", f"{stem}.net.xml"], check=True)
    print(f"wrote {stem}.net.xml  (L = {args.length} m, radius = {radius:.2f} m)")


if __name__ == "__main__":
    main()
