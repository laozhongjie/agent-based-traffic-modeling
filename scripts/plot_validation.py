"""Figures for the model validation: NaSch at p = 0 and OVM stability, both run in SUMO.

Usage (from the repository root, with sumo and SUMO_HOME pointing at the OVM build, see sumo/version.txt):
    python scripts/plot_validation.py
Reuses the runs of sumo/check_nasch.py and sumo/ovm/check_ovm.py (same rings and vTypes) and writes
results/validation/nasch_p0_fd.png and results/validation/ovm_stability_spacetime.png.
"""
import importlib.util
import tempfile
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.colors import LinearSegmentedColormap, Normalize
from scipy.optimize import brentq

from traffic_project import ROOT, nasch, ovm

INK, MUTED, GRID = "#1f2328", "#5a6577", "#e3e6eb"
SERIES, BAND = "#2a78d6", "#fde7cf"
SLOW_DARK = LinearSegmentedColormap.from_list(
    "slow_dark", ["#0d366b", "#1c5cab", "#3987e5", "#86b6ef", "#cde2fb"])
OUT = ROOT / "results" / "validation"


def load(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def style(ax):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelsize=10)
    ax.grid(color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def nasch_figure(tmp, end_s=300, warmup_s=200):
    """Flow vs density from SUMO (sigma = 0) against J = min(rho vmax, 1 - rho)."""
    cn = load(ROOT / "sumo" / "check_nasch.py")
    net = cn.build_ring(tmp)
    km_per_cell = cn.CELL_M / 1000
    ks, qs, worst = [], [], 0.0
    for n in range(5, 100, 5):
        states, checks = cn.run(tmp / f"nasch_n{n}", net, n, end_s)
        assert all(checks.values()), (n, checks)
        speeds = [sum(v for _, v in s.values()) / n for t, s in states.items() if t >= warmup_s]
        rho = n / cn.N_CELLS
        j = rho * sum(speeds) / len(speeds)                 # veh per step = veh per s
        worst = max(worst, abs(j - nasch.flow(rho, cn.VMAX)))
        ks.append(rho / km_per_cell)
        qs.append(j * 3600)
    rr = [i / 1000 for i in range(1001)]
    fig, ax = plt.subplots(figsize=(5.9, 3.7), constrained_layout=True)
    style(ax)
    ax.plot([r / km_per_cell for r in rr], [nasch.flow(r, cn.VMAX) * 3600 for r in rr],
            color=MUTED, linewidth=1.5, linestyle="--", label="Exact: J = min(ρ vmax, 1 − ρ)")
    ax.plot(ks, qs, linestyle="none", marker="o", markersize=7, color=SERIES,
            markeredgecolor="white", markeredgewidth=1.5, label="SUMO NaSch, p = 0")
    ax.set_xlabel("Density k (veh/km)", color=INK, fontsize=11)
    ax.set_ylabel("Flow q (veh/h)", color=INK, fontsize=11)
    ax.set_xlim(0, 1 / km_per_cell)
    ax.set_ylim(0, None)
    ax.legend(frameon=False, fontsize=10, labelcolor=INK, loc="upper right")
    fig.savefig(OUT / "nasch_p0_fd.png", dpi=300, facecolor="white")
    plt.close(fig)
    peak = 1 / (cn.VMAX + 1) / km_per_cell
    print(f"NaSch: {len(ks)} densities, max |SUMO - exact| = {worst:.1e} veh/s; "
          f"peak at k = {peak:.1f} veh/km, q = {cn.VMAX / (cn.VMAX + 1) * 3600:.0f} veh/h")


def unstable_band(p, length):
    """Densities (veh/km) where V'(s0) > alpha/2, the long-ring instability criterion."""
    f = lambda s: ovm.optimal_speed_slope(s, p) - p["alpha"] / 2
    lo, hi = brentq(f, 0, p["sc"]), brentq(f, p["sc"], 10 * p["sc"])
    return 1000 / (hi + length), 1000 / (lo + length)


def ovm_figure(tmp, counts=(20, 50, 100), end_s=600):
    """Space-time diagrams with a 0.5 m perturbation below, inside and above the unstable band."""
    co = load(ROOT / "sumo" / "ovm" / "check_ovm.py")
    vt, ring = co.VTYPE, co.RING_M
    k_lo, k_hi = unstable_band(vt, vt["length"])
    fig, axes = plt.subplots(1, len(counts), figsize=(5.9, 3.7), sharey=True, constrained_layout=True)
    for ax, n in zip(axes, counts):
        states, checks = co.run(tmp / f"ovm_n{n}", n, co.JITTER_M, 1, end_s)
        assert checks["sumo_exit_ok"], (n, checks)
        last, segs, vs = {}, [], []
        for t in sorted(states):
            for vid, (x, v) in states[t].items():
                prev = last.get(vid)
                if prev and x >= prev[1]:                    # skip the jump when wrapping past 0 m
                    segs.append([prev, (t, x)])
                    vs.append(v)
                last[vid] = (t, x)
        lines = LineCollection(segs, cmap=SLOW_DARK, norm=Normalize(0, vt["maxSpeed"]), linewidths=0.6)
        lines.set_array(vs)
        ax.add_collection(lines)
        style(ax)
        ax.grid(False)
        k = 1000 * n / ring
        unstable = k_lo < k < k_hi
        ax.set_title(f"k = {k:g} veh/km\n{'unstable: jam grows' if unstable else 'stable: decays'}",
                     color="#b45309" if unstable else INK, fontsize=10)
        ax.set_xlabel("Time (s)", color=INK, fontsize=10)
        ax.set_xlim(0, end_s)
        ax.set_ylim(0, ring)
        rate = ovm.growth_rate(n, ovm.uniform_gap(n, ring, vt), vt, dt=co.STEP_S)
        print(f"OVM: N = {n}, k = {k:g} veh/km, predicted growth rate {rate:+.4f}/s")
    axes[0].set_ylabel("Position on ring (m)", color=INK, fontsize=10)
    cb = fig.colorbar(lines, ax=list(axes), shrink=0.85, pad=0.02)
    cb.set_label("Speed (m/s)", color=INK, fontsize=10)
    cb.ax.tick_params(colors=MUTED, labelsize=9)
    fig.savefig(OUT / "ovm_stability_spacetime.png", dpi=300, facecolor="white")
    plt.close(fig)
    print(f"OVM: predicted unstable band V'(s0) > alpha/2: {k_lo:.1f}-{k_hi:.1f} veh/km")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        nasch_figure(Path(tmp))
        ovm_figure(Path(tmp))
    print(f"wrote {OUT.relative_to(ROOT)}/nasch_p0_fd.png and ovm_stability_spacetime.png")


if __name__ == "__main__":
    main()
