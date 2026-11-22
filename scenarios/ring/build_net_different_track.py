"""Build configurable SUMO ring, oval or open freeway networks.

Usage (from repository root):
    python scenarios/ring/build_net_different_track.py --type ring --length 4800 --lanes 2
    python scenarios/ring/build_net_different_track.py --type freeway --length 4800 --lanes 1
    python scenarios/ring/build_net_different_track.py --type oval --length 4800 --straight-length 1800
    1800 + 1800 + 600 + 600

"""
import argparse
import math
import subprocess
from pathlib import Path
from xml.sax.saxutils import escape

N_EDGES = 4
ARC_POINTS = 36

def network_stem(kind, length, lanes):
    return f"{kind}_{int(length)}_lanes{lanes}"

def geometry(kind, length, straight_length):
    """Return 4 edge polylines and prescribed reference lengths."""

    # For ring road... 
    if kind == "ring":
        radius = length / (2 * math.pi)
        angles = [2 * math.pi * k / N_EDGES for k in range(N_EDGES + 1)]
        curves = [
            [(radius * math.cos(a0 + (a1-a0)*j/ARC_POINTS),
              radius * math.sin(a0 + (a1-a0)*j/ARC_POINTS))
             for j in range(ARC_POINTS + 1)]
            for a0, a1 in zip(angles[:-1], angles[1:])
        ]
        return curves, [length / 4] * 4

    # For continuous freeway, straight road
    if kind == "freeway":
        return [[(length*k/4, 0), (length*(k+1)/4, 0)] for k in range(4)], [length / 4]*4

    # Then is for oval road.
    if not 0 < straight_length < length / 2:
        raise ValueError("oval: --straight-length must be > 0 and < length/2")
    
    radius = (length - 2*straight_length)/(2*math.pi)
    half = straight_length / 2
    bottom = [(-half, -radius), (half, -radius)]
    right = [(half + radius*math.cos(-math.pi/2 + math.pi*j/ARC_POINTS),
              radius*math.sin(-math.pi/2 + math.pi*j/ARC_POINTS)) for j in range(ARC_POINTS+1)]
    top = [(half, radius), (-half, radius)]
    left = [(-half + radius*math.cos(math.pi/2 + math.pi*j/ARC_POINTS),
             radius*math.sin(math.pi/2 + math.pi*j/ARC_POINTS)) for j in range(ARC_POINTS+1)]
    return [bottom, right, top, left], [straight_length, math.pi*radius, straight_length, math.pi*radius]


def build(kind="ring", length=4800, lanes=1, speed=30, out=None, straight_length=1800,
          directory=None):
    if kind not in {"ring", "freeway", "oval"}:
        raise ValueError("type must be ring, freeway, or oval")
    if length <= 0 or lanes < 1 or speed <= 0:
        raise ValueError("length, lanes and speed must be positive")
    here = Path(directory) if directory else Path(__file__).resolve().parent
    here.mkdir(parents=True, exist_ok=True)
    stem = here / (out or network_stem(kind, length, lanes))
    curves, lengths = geometry(kind, length, straight_length)
    closed = kind != "freeway"
    nodes = []
    starts = [c[0] for c in curves]
    endpoints = starts if closed else starts + [curves[-1][-1]]
    for i, (x, y) in enumerate(endpoints):
        nodes.append(f'    <node id="n{i}" x="{x:.6f}" y="{y:.6f}" type="priority"/>')
    edges = []
    for k, (points, edge_length) in enumerate(zip(curves, lengths)):
        shape = " ".join(f"{x:.6f},{y:.6f}" for x, y in points)
        destination = (k+1) % N_EDGES if closed else k+1
        edges.append(f'    <edge id="e{k}" from="n{k}" to="n{destination}" '
                     f'numLanes="{lanes}" speed="{speed:g}" length="{edge_length:.6f}" '
                     f'shape="{escape(shape)}"/>')
    stem.with_suffix(".nod.xml").write_text("<nodes>\n"+"\n".join(nodes)+"\n</nodes>\n")
    stem.with_suffix(".edg.xml").write_text("<edges>\n"+"\n".join(edges)+"\n</edges>\n")
    subprocess.run(["netconvert", "--node-files", str(stem.with_suffix(".nod.xml")),
                    "--edge-files", str(stem.with_suffix(".edg.xml")),
                    "--no-internal-links", "true", "--output-file", str(stem.with_suffix(".net.xml"))], check=True)
    print(f"Wrote {stem}.net.xml | type={kind} length={length:g}m lanes={lanes}")
    return stem.with_suffix(".net.xml")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--type", choices=["ring", "freeway", "oval"], default="ring")
    p.add_argument("--length", type=float, default=4800)
    p.add_argument("--lanes", type=int, default=1)
    p.add_argument("--speed", type=float, default=30)
    p.add_argument("--straight-length", type=float, default=1800)
    p.add_argument("--out", default=None)
    args = p.parse_args()
    build(args.type, args.length, args.lanes, args.speed, args.out, args.straight_length)


if __name__ == "__main__":
    main()
