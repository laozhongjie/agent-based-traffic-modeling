"""Plot the ring-road sweep: fundamental diagram and space-time diagrams.

Usage:
    python scripts/plot_ring.py --name idm_sweep --spacetime 20 50 100
Reads results/ring/<name>.csv and runs/ring_idm_L1000_n<N>_s1/fcd.xml,
writes results/ring/<name>_fd.png and <name>_spacetime.png.
"""
import argparse
import csv
import xml.etree.ElementTree as ET
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.colors import LinearSegmentedColormap, Normalize
from scipy.optimize import brentq

ROOT = Path(__file__).resolve().parents[1]
EDGE_LEN = 250.0
# IDM parameters used by scenarios/ring/build_run.py, for the equilibrium reference curve.
S0, T, V0, VEH_LEN = 2.0, 1.5, 30.0, 5.0

INK, MUTED, GRID = "#1f2328", "#5a6577", "#e3e6eb"
SERIES = "#2a78d6"                       # blue 450 from the reference palette
# Sequential blue ramp (100 -> 700); reversed so that slow (jammed) vehicles are darkest.
SLOW_DARK = LinearSegmentedColormap.from_list(
    "slow_dark", ["#0d366b", "#1c5cab", "#3987e5", "#86b6ef", "#cde2fb"])


def style(ax):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.grid(color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def v_eq(k):
    gap = 1000 / k - VEH_LEN
    return brentq(lambda v: gap * (1 - (v / V0) ** 4) ** 0.5 - (S0 + v * T), 0, V0 - 1e-9)


def fundamental_diagram(rows, out):
    k = [float(r["density_veh_km"]) for r in rows]
    v = [float(r["mean_speed_mps"]) for r in rows]
    q = [float(r["flow_veh_h"]) for r in rows]
    kk = [x / 2 for x in range(10, 2 * int(max(k)) + 1)]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 4), constrained_layout=True)
    for ax, y, y_eq, label in [(a1, q, [x * v_eq(x) * 3.6 for x in kk], "Flow q (veh/h)"),
                               (a2, v, [v_eq(x) for x in kk], "Mean speed v (m/s)")]:
        style(ax)
        ax.plot(kk, y_eq, color=MUTED, linewidth=1.5, linestyle="--", label="IDM equilibrium")
        ax.plot(k, y, color=SERIES, linewidth=2, marker="o", markersize=6,
                markeredgecolor="white", markeredgewidth=1.5, label="SUMO, seed 1")
        ax.set_xlabel("Density k (veh/km)", color=INK)
        ax.set_ylabel(label, color=INK)
        ax.set_xlim(0, max(k) + 5)
        ax.set_ylim(0, None)
    a1.legend(frameon=False, fontsize=9, labelcolor=INK)
    fig.suptitle("Ring road, L = 1000 m, IDM: fundamental diagram (t = 600–1800 s)", color=INK, fontsize=11)
    fig.savefig(out, dpi=150)


def spacetime(vehicle_counts, out, t0=1500, t1=1800):
    fig, axes = plt.subplots(1, len(vehicle_counts), figsize=(4 * len(vehicle_counts), 4),
                             sharey=True, constrained_layout=True)
    for ax, n in zip(axes, vehicle_counts):
        last, segs, vs = {}, [], []   # one line segment per vehicle per time step
        for _, el in ET.iterparse(ROOT / "runs" / f"ring_idm_L1000_n{n}_s1" / "fcd.xml"):
            if el.tag == "timestep":
                t = float(el.get("time"))
                if t0 <= t <= t1:
                    for veh in el:
                        edge = int(veh.get("lane")[1:].split("_")[0])
                        x, v = edge * EDGE_LEN + float(veh.get("pos")), float(veh.get("speed"))
                        prev = last.get(veh.get("id"))
                        if prev and x >= prev[1]:          # skip the jump when wrapping past 0 m
                            segs.append([prev, (t, x)])
                            vs.append(v)
                        last[veh.get("id")] = (t, x)
                el.clear()
        sc = LineCollection(segs, cmap=SLOW_DARK, norm=Normalize(0, V0), linewidths=0.7)
        sc.set_array(vs)
        ax.add_collection(sc)
        style(ax)
        ax.grid(False)
        ax.set_title(f"k = {n} veh/km", color=INK, fontsize=10)
        ax.set_xlabel("Time (s)", color=INK)
        ax.set_xlim(t0, t1)
        ax.set_ylim(0, 1000)
    axes[0].set_ylabel("Position on the ring (m)", color=INK)
    cb = fig.colorbar(sc, ax=axes, shrink=0.85)
    cb.set_label("Speed (m/s), darker = slower", color=INK)
    cb.ax.tick_params(colors=MUTED, labelsize=9)
    fig.suptitle("Ring road, IDM: vehicle trajectories", color=INK, fontsize=11)
    fig.savefig(out, dpi=150)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="idm_sweep")
    ap.add_argument("--spacetime", type=int, nargs="+", default=[20, 50, 100])
    args = ap.parse_args()
    res = ROOT / "results" / "ring"
    with (res / f"{args.name}.csv").open() as f:
        rows = [r for r in csv.DictReader(f) if r["valid"] == "True"]
    fundamental_diagram(rows, res / f"{args.name}_fd.png")
    spacetime(args.spacetime, res / f"{args.name}_spacetime.png")
    print(f"wrote results/ring/{args.name}_fd.png and {args.name}_spacetime.png")


if __name__ == "__main__":
    main()
