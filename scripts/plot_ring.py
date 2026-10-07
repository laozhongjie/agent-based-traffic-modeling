"""Plot a ring-road sweep: fundamental diagram and space-time diagrams.

Usage (from the repository root, after scripts/ring_sweep.py):
    python scripts/plot_ring.py --config configs/ring/idm_sweep.toml
Reads results/ring/<name>.csv and the FCD of the runs listed under [plot],
writes results/ring/<name>_fd.png and <name>_spacetime.png.
"""
import argparse

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.colors import LinearSegmentedColormap, Normalize
from scipy.optimize import brentq

from traffic_project import ROOT, config, io

N_EDGES = 4
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


def idm_equilibrium_speed(k, vt):
    """Speed at which IDM vehicles with uniform spacing 1000/k m neither accelerate nor brake."""
    gap = 1000 / k - vt["length"]
    v0, s0, T, d = vt["maxSpeed"], vt["minGap"], vt["tau"], vt["delta"]
    return brentq(lambda v: gap * (1 - (v / v0) ** d) ** 0.5 - (s0 + v * T), 0, v0 - 1e-9)


def fundamental_diagram(cfg, rows, out):
    k = [float(r["density_veh_km"]) for r in rows]
    v = [float(r["mean_speed_mps"]) for r in rows]
    q = [float(r["flow_veh_h"]) for r in rows]
    vt = cfg["vtype"]
    show_eq = cfg["model"].upper() == "IDM"
    kk = [x / 2 for x in range(10, 2 * int(max(k)) + 1)]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 4), constrained_layout=True)
    for ax, y, label, to_y in [(a1, q, "Flow q (veh/h)", lambda x, s: x * s * 3.6),
                               (a2, v, "Mean speed v (m/s)", lambda x, s: s)]:
        style(ax)
        if show_eq:
            ax.plot(kk, [to_y(x, idm_equilibrium_speed(x, vt)) for x in kk], color=MUTED,
                    linewidth=1.5, linestyle="--", label="IDM equilibrium")
        ax.plot(k, y, color=SERIES, linewidth=2, marker="o", markersize=6,
                markeredgecolor="white", markeredgewidth=1.5, label="SUMO")
        ax.set_xlabel("Density k (veh/km)", color=INK)
        ax.set_ylabel(label, color=INK)
        ax.set_xlim(0, max(k) + 5)
        ax.set_ylim(0, None)
    if show_eq:
        a1.legend(frameon=False, fontsize=9, labelcolor=INK)
    run = cfg["run"]
    fig.suptitle(f"Ring road, L = {cfg['ring']['length_m']:g} m, {cfg['model']}: fundamental diagram "
                 f"(t = {run['warmup_s']:g}–{run['end_s']:g} s)", color=INK, fontsize=11)
    fig.savefig(out, dpi=150)


def spacetime(cfg, out, window_s=300):
    length = cfg["ring"]["length_m"]
    edge_len = length / N_EDGES
    t1 = cfg["run"]["end_s"]
    t0 = t1 - window_s
    counts, seed = cfg["plot"]["spacetime"], cfg["sweep"]["seeds"][0]
    fig, axes = plt.subplots(1, len(counts), figsize=(4 * len(counts), 4),
                             sharey=True, constrained_layout=True, squeeze=False)
    for ax, n in zip(axes[0], counts):
        run_id = f"ring_{cfg['model'].lower()}_L{int(length)}_n{n}_s{seed}"
        last, segs, vs = {}, [], []   # one line segment per vehicle per time step
        for t, vehicles in io.iter_fcd(ROOT / "runs" / run_id / "fcd.xml"):
            if not t0 <= t <= t1:
                continue
            for veh in vehicles:
                x = int(veh["lane"][1:].split("_")[0]) * edge_len + veh["pos"]
                prev = last.get(veh["id"])
                if prev and x >= prev[1]:          # skip the jump when wrapping past 0 m
                    segs.append([prev, (t, x)])
                    vs.append(veh["speed"])
                last[veh["id"]] = (t, x)
        lines = LineCollection(segs, cmap=SLOW_DARK, norm=Normalize(0, cfg["vtype"]["maxSpeed"]),
                               linewidths=0.7)
        lines.set_array(vs)
        ax.add_collection(lines)
        style(ax)
        ax.grid(False)
        ax.set_title(f"k = {1000 * n / length:g} veh/km", color=INK, fontsize=10)
        ax.set_xlabel("Time (s)", color=INK)
        ax.set_xlim(t0, t1)
        ax.set_ylim(0, length)
    axes[0][0].set_ylabel("Position on the ring (m)", color=INK)
    cb = fig.colorbar(lines, ax=axes[0].tolist(), shrink=0.85)
    cb.set_label("Speed (m/s), darker = slower", color=INK)
    cb.ax.tick_params(colors=MUTED, labelsize=9)
    fig.suptitle(f"Ring road, {cfg['model']}: vehicle trajectories, seed {seed}", color=INK, fontsize=11)
    fig.savefig(out, dpi=150)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, help="configs/ring/<name>.toml")
    args = ap.parse_args()
    cfg = config.load(args.config)
    res = ROOT / "results" / "ring"
    rows = [r for r in io.read_csv(res / f"{cfg['name']}.csv") if r["valid"] == "True"]
    fundamental_diagram(cfg, rows, res / f"{cfg['name']}_fd.png")
    spacetime(cfg, res / f"{cfg['name']}_spacetime.png")
    print(f"wrote results/ring/{cfg['name']}_fd.png and {cfg['name']}_spacetime.png")


if __name__ == "__main__":
    main()
