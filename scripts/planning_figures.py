"""Planning figures (member D, RQ3): MFD overlay, critical density and maximum flow per variant,
and maps of where congestion gets worse or better, from the planning sweeps of the city network.

Inputs: one scripts/city_sweep.py sweep per variant (configs/city/bugis_all_<variant>_controller.toml)
  results/city/<name>.csv          summary table, one row per run (all figures and tables)
  runs/<run_id>/edge90.xml.gz      per-road speeds of every run, the reference runs included
                                   (only for the maps; runs/ is not in git, see "Maps" below)

Rules for the critical point (agreed with E, 2026-10-31):
  near-empty speed  v0 = the baseline network's mean speed at its lowest sweep density
                    (2.5 veh/km), averaged over the seeds
  threshold         v* = v0 / 2, the same for every variant (one baseline for all variants)
  critical density  k_half = the density at which a variant's seed-mean speed curve falls to v*:
                    the first sweep density with speed below v*, interpolated linearly in (k, v)
                    with the density before it (C's method, 2026-11-01; robust to a missing run).
                    The same crossing per seed gives the seed range
  capacity          the variant's maximum flow, a separate number (not a second critical point):
                    the highest seed-mean flow over the sweep densities (C's definition, 2026-11-01)
Each variant is compared with the baseline on paired runs: same density and seed, and a run left
out on one side (invalid) leaves out its partner too, as in C's comparison of 31 Oct. The table
gives the change of k_half (curve minus the baseline's curve) with the range of the per-seed paired
changes and whether every seed moves the same way, the change of capacity with the paired flow difference at the capacity density (mean and
standard error), and planning_speed_change.csv the paired change of mean speed at every density
(in %, which at the same car count is also the change of network flow). These are descriptive;
how to state their uncertainty with few seeds is E's call (planning_seeds.csv has the per-seed values).

Density is per km of the BASELINE's car lanes (T4-D2: N = round(k L_base / 1000) on every
variant), so runs with the same N sit at the same density on every variant. Flow is the summary's
flow_veh_h, veh/h per lane of the variant, as in C's results.

Maps: per road, the share of the measurement window (warmup_s-end_s) in which the road is
congested by the city criterion (T3-D1, configs' [measure]: speed below r_on x v_ref for persist_m
intervals, congestion.classify), averaged over the seeds. v_ref is each road's near-empty speed: its
mean speed in the variant's OWN 2 veh/km reference run, red-light waits included, for every road of
that variant, old or new, as scripts/city_sweep.py does (C's rule, 2026-11-02). (The network's
critical point, above, uses the baseline's speed for every variant instead.)
Reading runs/ is the slow part, so the per-road shares go into planning_edges.csv (small, for git);
with --skip-edges the maps are drawn from that file, so the maps can be redrawn without runs/.
The maps show, for each variant, the change in congested share from the baseline at a density:
by default the baseline's critical density and its density of maximum flow, each rounded to the
nearest sweep density (--map-densities to choose). Changes smaller than --change-min (5 percentage
points) are drawn grey as noise; closed roads are dashed, new roads drawn in black.

Outputs (in --out, default results/city/planning/):
  planning_summary.csv   one row per variant: k_half and capacity, and their change from the baseline
  planning_seeds.csv     one row per variant and seed: k_half and the seed's own highest flow
  planning_speed_change.csv  one row per variant and density: paired change of mean speed (%)
  planning_mfd.csv       one row per variant and density: speed and flow, mean, min and max over seeds
  planning_edges.csv     one row per variant, density and road: congested share (mean, min, max over
                         seeds) and mean speed
  figures/planning_mfd.png (three panels) and each panel alone (planning_mfd_flow.png,
                         planning_mfd_speed.png, planning_speed_change.png), figures/planning_map_k<k>.png
and the site export --site/planning.js (default docs/data/city/), in the layout of A's
traffic_project.export_web (see export_site). Export the four sweeps themselves with
scripts/export_web.py first (on the computer that ran them), so planning.js can name their
provenance; the maps stay figures (PNG) for the report.

Extra seeds: --extra VARIANT=NAME joins another sweep table of a variant (e.g. more seeds at some
densities) to its main sweep; repeatable. Its config, if present in the config folder, must match
the main config in [run], [vehicle], [controller], [rerouting] and the nets (so a teleport
sensitivity set is refused), and a density and seed in both tables stops the script. Means and
ranges then run over all seeds a density has, and paired comparisons over the seeds both sides have.

Usage (from the repository root), after the four planning sweeps:
    python scripts/planning_figures.py
    python scripts/planning_figures.py --extra base=<base extra seeds> --extra newlink=<new link extra seeds>
On a smoke sweep (city_sweep.py --prefix/--name, tables in runs/<prefix>_results/):
    python scripts/planning_figures.py --name-pattern figtest_{variant} \\
        --results-dir runs/figtest_{variant}_results --out runs/figtest_planning --no-site
"""
import argparse
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pandas as pd

from traffic_project import ROOT, config

VARIANTS = ("base", "closure", "newlink", "lanecut")
LABELS = {"base": "Baseline", "closure": "Victoria St closed", "lanecut": "Victoria St lane cut",
          "newlink": "Java Road connection"}
# Baseline in ink as the reference; variants in categorical slots 1-3 of the dataviz reference
# palette, which pass the colour-blind checks pairwise, with the colours and markers of C's
# planning figure of 2026-11-01. Line styles add a second cue.
STYLE = {"base": dict(color="#52514e", marker="o", ls="-"),
         "closure": dict(color="#2a78d6", marker="s", ls="--"),
         "newlink": dict(color="#eb6834", marker="^", ls="-."),
         "lanecut": dict(color="#1baf7a", marker="D", ls=":")}
INK, MUTED, GRID = "#0b0b0b", "#898781", "#e1e0d9"
BETTER, WORSE, NEUTRAL = "#2a78d6", "#e34948", "#f0efec"   # diverging pair, grey midpoint


# ---------------------------------------------------------------- inputs

def _names(x):
    return [x] if isinstance(x, str) else list(x)


def load_sweeps(names, results_dirs, include_invalid=False):
    """One table of every swept run of every variant, with k per km of baseline lane.

    names, results_dirs: {variant: table name, or a list of table names}, {variant: folder holding
    <name>.csv}. Several tables of one variant (the main sweep and extra seeds) are joined; the
    same density and seed in two of them stops the script.
    Returns (runs, notes): runs has variant, seed, k_target, k, v, q, run_id, valid, the teleport
    rate and table (the table each run came from); notes lists what was left out.
    """
    frames, notes = [], []
    for variant, vnames in names.items():
        for name in _names(vnames):
            path = Path(results_dirs[variant]) / f"{name}.csv"
            if not path.exists():
                raise SystemExit(f"missing {path}: run the {variant} sweep first (scripts/city_sweep.py)")
            d = pd.read_csv(path, dtype={"run_id": str, "variant": str})
            given = set(d["variant"].dropna()) - {""}
            if given and given != {variant}:
                raise SystemExit(f"{path} holds variant {sorted(given)}, not {variant!r}")
            d["variant"], d["table"] = variant, name
            frames.append(d)
    d = pd.concat(frames, ignore_index=True)
    dup = d[d.duplicated(["variant", "city_k_target", "seed"], keep=False)]
    if len(dup):
        r = dup.iloc[0]
        raise SystemExit(f"{r.variant} at {r.city_k_target:g} veh/km, seed {r.seed} is in two tables "
                         f"({', '.join(sorted(set(dup.table)))}): extra tables must add new seeds or densities")
    if "city_baseline_lane_length_m" in d:
        base_len = d["city_baseline_lane_length_m"].fillna(d["city_lane_length_m"])
    else:
        base_len = d["city_lane_length_m"]
    if base_len.max() - base_len.min() > 1.0:   # m
        raise SystemExit(f"the sweeps use different baseline lane lengths ({base_len.min():.1f}-"
                         f"{base_len.max():.1f} m): set the same [network] baseline_net_file in every config")
    d["k"] = 1000 * d["city_n_vehicles"] / base_len
    d["v"] = d["mean_speed_mps"]
    d["q"] = d["flow_veh_h"]   # veh/h per lane of the variant, as in C's results
    d["k_target"] = d["city_k_target"]
    bad = d[~d["valid"].astype(bool)]
    if len(bad):
        notes.append(f"{len(bad)} invalid runs " + ("kept" if include_invalid else "left out") + ": "
                     + ", ".join(bad["run_id"].head(8)) + (" ..." if len(bad) > 8 else ""))
        if not include_invalid:
            d = d[d["valid"].astype(bool)]
    keep = ["variant", "seed", "k_target", "k", "v", "q", "run_id", "valid",
            "city_teleports_per_car_h_window", "table"]
    out = d[[c for c in keep if c in d]].sort_values(["variant", "seed", "k"]).reset_index(drop=True)
    out.attrs["excluded_invalid"] = 0 if include_invalid else len(bad)
    return out, notes


# ---------------------------------------------------------------- critical point and capacity

SAME_SETTINGS = ("run", "vehicle", "controller", "rerouting")


def check_same_settings(main_cfg, extra_cfg):
    """Differences between an extra sweep's config and its variant's main config in the settings
    that must match for its runs to join the main ones ([run], [vehicle], [controller],
    [rerouting], and the nets), as {key: (main, extra)}; empty when they match. Run length,
    teleport time and the like must be the same, or the runs measure something else (e.g. a
    teleport-sensitivity set must not be joined)."""
    diff = {}
    for table in SAME_SETTINGS:
        a, b = main_cfg.get(table, {}), extra_cfg.get(table, {})
        for key in sorted(set(a) | set(b)):
            if a.get(key) != b.get(key):
                diff[f"{table}.{key}"] = (a.get(key), b.get(key))
    for key in ("net_file", "baseline_net_file"):
        a, b = main_cfg.get("network", {}).get(key), extra_cfg.get("network", {}).get(key)
        if a != b:
            diff[f"network.{key}"] = (a, b)
    return diff


def near_empty_speed(runs, base="base"):
    """(v0, lowest density): the baseline's mean speed at its lowest sweep density, mean over seeds."""
    b = runs[runs.variant == base]
    if b.empty:
        raise SystemExit(f"no runs of the baseline {base!r}")
    k_low = b.k_target.min()
    return float(b[b.k_target == k_low].v.mean()), float(k_low)


def half_speed_density(k, v, v_star):
    """Density at which speed first falls below v_star, linear in (k, v) between the two sweep
    points around the crossing. NaN when the lowest density is already below v_star or speed
    never falls below it. k must be sorted ascending."""
    k, v = np.asarray(k, float), np.asarray(v, float)
    below = np.flatnonzero(v < v_star)
    if len(below) == 0 or below[0] == 0:
        return math.nan
    i = below[0]
    return float(k[i - 1] + (v_star - v[i - 1]) * (k[i] - k[i - 1]) / (v[i] - v[i - 1]))


def per_seed(runs, v_star):
    """One row per variant and seed, on all the variant's valid runs: k_half and the seed's own
    highest flow (q_peak, k_at_q_peak; for E's uncertainty methods)."""
    rows = []
    for (variant, seed), g in runs.groupby(["variant", "seed"]):
        g = g.sort_values("k")
        i = int(np.argmax(g.q.to_numpy()))
        rows.append(dict(variant=variant, seed=int(seed), k_half=half_speed_density(g.k, g.v, v_star),
                         q_peak=float(g.q.iloc[i]), k_at_q_peak=float(g.k_target.iloc[i]), n_densities=len(g)))
    return pd.DataFrame(rows)


def paired(runs, variant, base="base"):
    """Runs of variant and baseline at the (density, seed) pairs both have (an invalid run left
    out of one leaves out its partner too, as in C's comparison of 31 Oct)."""
    v, b = runs[runs.variant == variant], runs[runs.variant == base]
    keys = set(zip(v.k_target, v.seed)) & set(zip(b.k_target, b.seed))
    keep = lambda d: d[[kv in keys for kv in zip(d.k_target, d.seed)]]
    return keep(v), keep(b)


def speed_change(runs, variants, base="base"):
    """Per variant and density: the paired change of mean speed from the baseline (same density
    and seed), in %, as mean, standard error, min and max over seeds. At the same car count it is
    also the change of network flow (production)."""
    rows = []
    for variant in variants:
        if variant == base:
            continue
        v, b = paired(runs, variant, base)
        m = v.merge(b, on=["k_target", "seed"], suffixes=("", "_b"))
        m["pct"] = 100 * (m.v / m.v_b - 1)
        for k, g in m.groupby("k_target"):
            n = len(g)
            rows.append(dict(variant=variant, k_target=k, pct_mean=g.pct.mean(),
                             pct_se=g.pct.std(ddof=1) / math.sqrt(n) if n > 1 else math.nan,
                             pct_min=g.pct.min(), pct_max=g.pct.max(), n_pairs=n))
    return pd.DataFrame(rows)


def capacity(runs, variant):
    """(capacity, density): the highest seed-mean flow over the sweep densities (C's definition),
    and whether it lies at the highest density (flow may still rise: a lower bound)."""
    curve = runs[runs.variant == variant].groupby("k_target").q.mean()
    k = float(curve.idxmax())
    return float(curve.max()), k, k == float(curve.index.max())


def curve_k_half(runs, variant, v_star):
    """k_half of the variant's seed-mean speed curve (mean speed over seeds at each sweep density)."""
    c = runs[runs.variant == variant].groupby("k_target").agg(k=("k", "mean"), v=("v", "mean")).sort_values("k")
    return half_speed_density(c.k, c.v, v_star)


def compare(runs, v_star, variants, base="base"):
    """One row per variant.

    Own values, on all the variant's valid runs: k_half of the seed-mean curve, with the range of
    the per-seed k_half (k_half_seed_min, k_half_seed_max); the capacity (highest seed-mean flow)
    with its density and the flag capacity_at_top.
    Change from the baseline: d_k_half = k_half minus the baseline's k_half (and in %), with the
    per-seed paired changes (same density and seed; a run missing on one side drops its partner):
    their range and same_sign_k_half (every seed moves the same way); d_capacity = capacity minus
    the baseline's capacity, with the paired flow differences at the variant's capacity density
    (d_q_at_cap mean and standard error, same_sign_q_at_cap)."""
    seeds = per_seed(runs, v_star)
    b_cap, _, _ = capacity(runs, base)
    b_k = curve_k_half(runs, base, v_star)
    rows = []
    for variant in variants:
        s = seeds[seeds.variant == variant]
        cap, k_cap, at_top = capacity(runs, variant)
        k_half = curve_k_half(runs, variant, v_star)
        row = dict(variant=variant, label=LABELS.get(variant, variant), n_seeds=len(s), k_half=k_half,
                   k_half_seed_min=s.k_half.min(), k_half_seed_max=s.k_half.max(),
                   capacity=cap, k_at_capacity=k_cap, capacity_at_top=at_top)
        if variant != base:
            v, b = paired(runs, variant, base)
            kv = per_seed(v, v_star).set_index("seed").k_half
            kb = per_seed(b, v_star).set_index("seed").k_half
            d = (kv - kb).dropna()
            m = v.merge(b, on=["k_target", "seed"], suffixes=("", "_b"))
            dq = (m.q - m.q_b)[np.isclose(m.k_target, k_cap)]
            row.update(n_pairs=len(m), n_seeds_paired=len(d),
                       d_k_half=k_half - b_k, d_k_half_pct=100 * (k_half - b_k) / b_k,
                       d_k_half_seed_min=d.min(), d_k_half_seed_max=d.max(),
                       same_sign_k_half=bool(len(d) and ((d > 0).all() or (d < 0).all())),
                       d_capacity=cap - b_cap, d_capacity_pct=100 * (cap - b_cap) / b_cap,
                       d_q_at_cap_mean=dq.mean(),
                       d_q_at_cap_se=dq.std(ddof=1) / math.sqrt(len(dq)) if len(dq) > 1 else math.nan,
                       same_sign_q_at_cap=bool(len(dq) and ((dq > 0).all() or (dq < 0).all())))
        rows.append(row)
    return pd.DataFrame(rows), seeds


def mfd_table(runs):
    """One row per variant and sweep density: mean, min and max over seeds of v and q."""
    g = runs.groupby(["variant", "k_target"])
    out = g.agg(k=("k", "mean"), v_mean=("v", "mean"), v_min=("v", "min"), v_max=("v", "max"),
                q_mean=("q", "mean"), q_min=("q", "min"), q_max=("q", "max"), n_seeds=("seed", "nunique"))
    return out.reset_index()


# ---------------------------------------------------------------- per-road congestion (maps)

def _prefix(run_ids):
    prefixes = {r.rsplit("_k", 1)[0] for r in run_ids}
    if len(prefixes) != 1:
        raise SystemExit(f"runs of one variant have several run prefixes: {sorted(prefixes)}")
    return prefixes.pop()


def _cg():
    """traffic_project.congestion (C's city code), needed only for the maps."""
    from traffic_project import congestion
    return congestion


def _edgedata(path, mult):
    cg = _cg()
    if not path.exists():
        raise FileNotFoundError(path)
    return cg.merge_intervals(cg.read_edgedata(path), mult)


def edge_shares(runs, cfgs, runs_dir, base="base", log=print, main=None):
    """One row per variant, density, seed and road: congested share over warmup_s-end_s and the
    sampledSeconds-weighted mean speed. v_ref: each road's mean speed in the variant's own reference
    run, as in city_sweep.py (see the module doc). main: {variant: name of its main sweep table};
    the reference run is looked up under that table's run prefix, since an extra table (e.g. more
    seeds, run under another prefix) has its own reference run with the same road data (C's fix,
    2026-11-02)."""
    cg = _cg()
    def params(run_dir, cfg):
        """The run's own [run] and [measure] (its manifest holds them with any smoke-run overrides)."""
        manifest = Path(run_dir) / "manifest.json"
        p = json.loads(manifest.read_text())["parameters"] if manifest.exists() else {}
        return p.get("run", cfg["run"]), p.get("measure", cfg["measure"])

    def setup(variant):
        cfg = cfgs[variant]
        net = cg.read_net(ROOT / cfg["network"]["net_file"])
        m = cfg["measure"]
        period = cg.cycle_period(net, m["period_s"])
        edfile = cfg["inputs"]["edgedata_file"].format(period=period)
        own = runs[runs.variant == variant]
        if main:
            own = own[own.table == main[variant]]
        prefix = _prefix(own.run_id)
        ref_dir = Path(runs_dir) / f"{prefix}_k{float(m['reference_density_veh_km']):g}_s{m['reference_seed']}"
        r, m = params(ref_dir, cfg)
        vref, _ = cg.free_flow_reference(_edgedata(ref_dir / edfile, m.get("period_mult", 1)), net.edges,
                                         r["warmup_s"], m["vref_min_sampled_s"], m["vref_fallback"])
        return net, edfile, vref

    rows = []
    for variant in runs.variant.unique():
        net, edfile, vref = setup(variant)
        cfg = cfgs[variant]
        sub = runs[runs.variant == variant]
        log(f"  {variant}: {len(sub)} runs, v_ref from its own reference run")
        for _, run in sub.iterrows():
            run_dir = Path(runs_dir) / run.run_id
            r, m = params(run_dir, cfg)
            warm = r["warmup_s"]
            df = _edgedata(run_dir / edfile, m.get("period_mult", 1))
            state = cg.classify(cg.relative_speed(df, vref), m["r_on"], m["persist_m"])
            share = state[state.index >= warm].mean(axis=0)
            w = df[(df.begin >= warm) & (df.sampledSeconds > 0)]
            speed = ((w.speed * w.sampledSeconds).groupby(w.edge).sum()
                     / w.sampledSeconds.groupby(w.edge).sum()).reindex(net.edges.index)
            rows.append(pd.DataFrame(dict(variant=variant, k_target=run.k_target, seed=int(run.seed),
                                          edge=net.edges.index, congested_share=share.to_numpy(),
                                          mean_speed_mps=speed.to_numpy())))
    return pd.concat(rows, ignore_index=True)


def edge_table(per_run, base="base"):
    """Per variant, density and road: mean, min and max over seeds of the congested share, the mean
    speed, and the change from the baseline paired by seed (d_share: mean of variant minus baseline
    on the same seed; d_same_sign: every paired seed changes in the same direction). Roads the
    baseline lacks have no change."""
    g = per_run.groupby(["variant", "k_target", "edge"])
    out = g.agg(congested_share=("congested_share", "mean"), congested_share_min=("congested_share", "min"),
                congested_share_max=("congested_share", "max"), mean_speed_mps=("mean_speed_mps", "mean"),
                n_seeds=("seed", "nunique")).reset_index()
    b = per_run[per_run.variant == base][["k_target", "seed", "edge", "congested_share"]]
    p = per_run.merge(b, on=["k_target", "seed", "edge"], suffixes=("", "_base"))
    p["d"] = p.congested_share - p.congested_share_base
    d = p.groupby(["variant", "k_target", "edge"]).d.agg(
        d_share="mean", d_same_sign=lambda x: bool(len(x) and ((x > 0).all() or (x < 0).all()))).reset_index()
    return out.merge(d, on=["variant", "k_target", "edge"], how="left")


def edge_shapes(net_path):
    """{edge id: (n, 2) array} of the middle lane's shape of every normal edge, and lane counts."""
    shapes, lanes = {}, {}
    for _, el in ET.iterparse(str(net_path)):
        if el.tag == "edge" and el.get("function") != "internal":
            ls = el.findall("lane")
            if ls:
                shp = ls[len(ls) // 2].get("shape")
                shapes[el.get("id")] = np.array([[float(c) for c in p.split(",")[:2]] for p in shp.split()])
                lanes[el.get("id")] = len(ls)
            el.clear()
        elif el.tag in ("junction", "connection", "tlLogic"):
            el.clear()
    return shapes, lanes


def map_densities(summary, sweep_k, base="base"):
    """The sweep densities nearest to the baseline's critical density, and its capacity density."""
    b = summary.set_index("variant").loc[base]
    ks = sorted(set(float(x) for x in sweep_k))
    out = []
    for target in (b.k_half, b.k_at_capacity):
        if not math.isnan(target):
            k = min(ks, key=lambda x: abs(x - target))
            if k not in out:
                out.append(k)
    return out


# ---------------------------------------------------------------- figures

def _style_axes(ax):
    ax.grid(True, color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#c3c2b7")
    ax.tick_params(colors=MUTED, labelcolor="#52514e")


def _ranges(ks):
    """'25-35' for consecutive sweep densities given as a sorted list, joined with commas."""
    return ", ".join(f"{k:g}" for k in ks)


def pair_note(change, min_pairs=3):
    """How many seed pairs the speed-change points rest on, for a caption: the usual count, the
    densities of each variant with more (extra seeds) and the points with fewer than min_pairs."""
    if not len(change):
        return ""
    usual = int(change.n_pairs.mode().iloc[0])
    parts = [f"{usual} seed pairs per point"]
    for variant, g in change.groupby("variant", sort=False):
        more = g[g.n_pairs > usual].sort_values("k_target")
        if len(more):
            parts.append(f"{LABELS.get(variant, variant)} {more.n_pairs.min()}-{more.n_pairs.max()} at "
                         f"{_ranges(more.k_target)} veh/km")
    few = change[change.n_pairs < min_pairs]
    if len(few):
        groups = [f"{LABELS.get(v, v)} at {_ranges(sorted(g.k_target))}"
                  for v, g in few.groupby("variant", sort=False)]
        parts.append(f"hollow: fewer than {min_pairs} pairs (an invalid run drops its pair): " + "; ".join(groups))
    return "; ".join(parts)


def _panel_flow(ax, mfd, variants):
    for variant in variants:
        d = mfd[mfd.variant == variant].sort_values("k")
        st = STYLE.get(variant, dict(color=INK, marker="o", ls="-"))
        ax.fill_between(d.k, d.q_min, d.q_max, color=st["color"], alpha=0.15, lw=0)
        ax.plot(d.k, d.q_mean, color=st["color"], lw=2, ls=st["ls"], marker=st["marker"], ms=5,
                label=LABELS.get(variant, variant), zorder=3 if variant == "base" else 4)
    ax.set_ylabel("Flow (veh/h per lane)")
    ax.set_title("Macroscopic fundamental diagram", fontsize=11, loc="left", color=INK)
    ax.set_xlabel("Density (veh/km of baseline lane)")
    ax.set_ylim(bottom=0)
    ax.set_xlim(left=0)
    _style_axes(ax)
    ax.legend(frameon=False, fontsize=9, loc="lower right")


def _panel_speed(ax, mfd, summary, v_star, variants):
    from matplotlib.lines import Line2D
    s = summary.set_index("variant")
    for variant in variants:
        d = mfd[mfd.variant == variant].sort_values("k")
        st = STYLE.get(variant, dict(color=INK, marker="o", ls="-"))
        ax.fill_between(d.k, d.v_min, d.v_max, color=st["color"], alpha=0.15, lw=0)
        ax.plot(d.k, d.v_mean, color=st["color"], lw=2, ls=st["ls"], marker=st["marker"], ms=5,
                zorder=3 if variant == "base" else 4)
        kh = s.loc[variant, "k_half"] if variant in s.index else math.nan
        if not math.isnan(kh):
            ax.plot([kh], [v_star], marker="|", ms=16, mew=2, color=st["color"], zorder=5)
    ax.axhline(v_star, color=INK, lw=1, ls=(0, (4, 3)), zorder=2)
    ax.set_ylim(bottom=0)
    ax.set_xlim(left=0)
    ax.annotate(f"half of near-empty speed ({v_star:.2f} m/s)", (ax.get_xlim()[1], v_star),
                xytext=(-4, 5), textcoords="offset points", ha="right", va="bottom", fontsize=8.5, color="#52514e")
    ax.set_ylabel("Mean speed (m/s)")
    ax.set_title("Speed and critical density (ticks)", fontsize=11, loc="left", color=INK)
    ax.set_xlabel("Density (veh/km of baseline lane)")
    _style_axes(ax)
    # the ticks of close critical densities overlap, so list the values as well
    handles = [Line2D([], [], color=STYLE.get(v, {}).get("color", INK), marker="|", ms=12, mew=2, ls="none",
                      label=f"{LABELS.get(v, v)}: {s.loc[v, 'k_half']:.2f} veh/km")
               for v in variants if v in s.index and not math.isnan(s.loc[v, "k_half"])]
    if handles:
        ax.legend(handles=handles, title="Critical density (seed-mean curve)", title_fontsize=8.5,
                  frameon=False, fontsize=8.5, loc="upper right")


def _panel_change(ax, change, variants, min_pairs=3):
    """Paired speed change per density; points resting on fewer than min_pairs seed pairs hollow."""
    others = [v for v in variants if v in set(change.variant)] if len(change) else []
    off = {v: (i - (len(others) - 1) / 2) * 0.5 for i, v in enumerate(others)}   # veh/km, for legibility
    for variant in others:
        d = change[change.variant == variant].sort_values("k_target")
        st = STYLE.get(variant, dict(color=INK, marker="o", ls="-"))
        x = d.k_target + off[variant]
        ax.errorbar(x, d.pct_mean, yerr=d.pct_se, color=st["color"], marker="none", lw=1.6, ls=st["ls"],
                    capsize=2.5)
        solid = d.n_pairs >= min_pairs
        ax.plot(x[solid], d.pct_mean[solid], ls="none", marker=st["marker"], ms=5, color=st["color"],
                label=LABELS.get(variant, variant))
        ax.plot(x[~solid], d.pct_mean[~solid], ls="none", marker=st["marker"], ms=6, mfc="white",
                mec=st["color"], mew=1.5)
    ax.axhline(0, color="#52514e", lw=1)
    ax.set_ylabel("Change in mean speed vs baseline (%)")
    ax.set_title("Paired change at the same car count", fontsize=11, loc="left", color=INK)
    ax.set_xlabel("Density (veh/km of baseline lane)")
    _style_axes(ax)
    if others:
        ax.legend(frameon=False, fontsize=8.5, loc="best")


def plot_mfd(mfd, summary, change, v0, v_star, variants, path):
    """Flow-density (left), speed-density with the threshold v* and each variant's critical density
    (middle), and the paired change of mean speed from the baseline (right; bars: 1 standard error;
    hollow points rest on fewer than 3 seed pairs). Lines: mean over seeds; bands: range over seeds.
    Writes the three panels together at path, and each alone beside it (planning_mfd_flow.png,
    planning_mfd_speed.png, planning_speed_change.png), so a report can combine panels of two runs
    (e.g. the 3-seed MFD with the 10-seed speed change)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    path = Path(path)
    common = (f"Lines: mean over seeds; bands: range over seeds (wider with more seeds). "
              f"Near-empty speed v0 = {v0:.2f} m/s (baseline, lowest density).")
    change_note = ("Mean of paired differences (same density and seed), bars 1 standard error, variants offset "
                   "by 0.5 veh/km for legibility; " + pair_note(change) + ".")

    def save(fig, out, note):
        import textwrap
        w = fig.get_size_inches()[0]
        lines = textwrap.wrap(note, int(w * 15))
        fig.text(0.01, 0.005, "\n".join(lines), fontsize=8, color=MUTED, va="bottom")
        fig.tight_layout(rect=(0, 0.035 * len(lines) * 4.6 / fig.get_size_inches()[1], 1, 1))
        fig.savefig(out, dpi=200)
        plt.close(fig)

    fig, (axq, axv, axd) = plt.subplots(1, 3, figsize=(16, 4.8))
    _panel_flow(axq, mfd, variants)
    _panel_speed(axv, mfd, summary, v_star, variants)
    _panel_change(axd, change, variants)
    save(fig, path, common + " Right: m" + change_note[1:])
    for name, draw, note in (
            ("planning_mfd_flow.png", lambda ax: _panel_flow(ax, mfd, variants), common),
            ("planning_mfd_speed.png", lambda ax: _panel_speed(ax, mfd, summary, v_star, variants), common),
            ("planning_speed_change.png", lambda ax: _panel_change(ax, change, variants), change_note)):
        fig, ax = plt.subplots(figsize=(6.4, 4.8))
        draw(ax)
        save(fig, path.with_name(name), note)


def plot_map(edges, geo, variants, k, path, base="base", change_min=0.05):
    """Baseline congested share (top left) and, per variant, its change from the baseline at density
    k. A change is coloured only when its mean over seeds is at least change_min and every seed
    changes in the same direction (with one seed, the size alone decides)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm, Normalize

    seq = LinearSegmentedColormap.from_list("seq", ["#fbe3d6", "#f2a27f", "#eb6834", "#b8461b", "#7a2a0c"])
    div = LinearSegmentedColormap.from_list("div", [BETTER, NEUTRAL, WORSE])
    e = edges[np.isclose(edges.k_target, k)]
    if e.empty:
        raise SystemExit(f"no per-road data at {k:g} veh/km (sweep densities: {sorted(edges.k_target.unique())})")
    b = e[e.variant == base].set_index("edge").congested_share
    others = [v for v in variants if v != base]
    deltas, shown = {}, {}
    for v in others:
        ev = e[e.variant == v].set_index("edge")
        deltas[v] = ev.d_share
        one_seed = ev.n_seeds <= 1
        shown[v] = (ev.d_share.abs() >= change_min) & (ev.d_same_sign.fillna(False).astype(bool) | one_seed)
    lim = max([0.2] + [float(deltas[v][shown[v]].abs().max()) for v in others if shown[v].any()])
    lim = math.ceil(lim * 10) / 10
    ncol = 2
    nrow = math.ceil((len(others) + 1) / ncol)
    fig, axes = plt.subplots(nrow, ncol, figsize=(5.6 * ncol, 5.0 * nrow), layout="constrained")
    axes = np.atleast_1d(axes).ravel()
    allxy = np.vstack(list(geo[base][0].values()))
    pad = 0.02 * (allxy.max(0) - allxy.min(0))
    xlim, ylim = (allxy[:, 0].min() - pad[0], allxy[:, 0].max() + pad[0]), (allxy[:, 1].min() - pad[1], allxy[:, 1].max() + pad[1])

    def draw(ax, variant, values, cmap, norm, title, show=None):
        shapes, lanes = geo[variant]
        base_shapes, _ = geo[base]
        grey, coloured = [], []
        for eid, shp in shapes.items():
            val = values.get(eid, np.nan)
            lw = 0.5 + 0.45 * lanes[eid]
            if eid not in base_shapes:
                continue   # new roads are drawn last
            if variant != base and (np.isnan(val) or not show.get(eid, False)):
                grey.append((shp, lw))
            else:
                coloured.append((abs(val) if variant != base else val, shp, lw, val))
        ax.add_collection(LineCollection([s for s, _ in grey], colors="#d7d6d0", linewidths=[w for _, w in grey]))
        coloured.sort(key=lambda t: t[0])   # biggest changes on top
        if coloured:
            ax.add_collection(LineCollection([c[1] for c in coloured], linewidths=[c[2] for c in coloured],
                                             colors=cmap(norm(np.array([c[3] for c in coloured])))))
        closed = [s for eid, s in base_shapes.items() if eid not in shapes]
        if closed:
            ax.add_collection(LineCollection(closed, colors=INK, linewidths=1.6, linestyles=(0, (2, 1.5))))
        new = [s for eid, s in shapes.items() if eid not in base_shapes]
        if new:
            ax.add_collection(LineCollection(new, colors=INK, linewidths=3.0))
        ax.set_title(title, fontsize=10.5, loc="left", color=INK)
        ax.set_aspect("equal")
        ax.set_xlim(*xlim)
        ax.set_ylim(*ylim)
        ax.set_xticks([])
        ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_visible(False)
        return closed, new

    nb = Normalize(0, 1)
    draw(axes[0], base, b.to_dict(), seq, nb, f"{LABELS[base]}: congested share of time")
    sm = plt.cm.ScalarMappable(norm=nb, cmap=seq)
    fig.colorbar(sm, ax=axes[0], fraction=0.035, pad=0.01).set_label("share of time congested", fontsize=8.5)
    nd = TwoSlopeNorm(vcenter=0, vmin=-lim, vmax=lim)
    for ax, v in zip(axes[1:], others):
        closed, new = draw(ax, v, deltas[v].to_dict(), div, nd, f"{LABELS.get(v, v)}: change from baseline",
                           show=shown[v].to_dict())
        notes = (["dashed: closed road"] if closed else []) + (["black: new road"] if new else [])
        if notes:
            ax.text(0.01, 0.01, "; ".join(notes), transform=ax.transAxes, fontsize=8, color="#52514e")
    for ax in axes[len(others) + 1:]:
        ax.axis("off")
    sm = plt.cm.ScalarMappable(norm=nd, cmap=div)
    cb = fig.colorbar(sm, ax=axes[1:len(others) + 1].tolist(), fraction=0.03, pad=0.01)
    cb.set_label("change in share of time congested (blue: better, red: worse)", fontsize=8.5)
    # 500 m scale bar on the baseline panel
    ax = axes[0]
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    xs, ys = x0 + 0.04 * (x1 - x0), y0 + 0.04 * (y1 - y0)
    ax.plot([xs, xs + 500], [ys, ys], color=INK, lw=2)
    ax.text(xs + 250, ys + 0.015 * (y1 - y0), "500 m", ha="center", fontsize=8, color=INK)
    fig.suptitle(f"Where congestion changes at {k:g} veh/km (mean over seeds; grey: change under "
                 f"{100 * change_min:.0f} percentage points or not on every seed)", fontsize=11, x=0.01,
                 ha="left", color=INK)
    fig.savefig(path, dpi=200)
    plt.close(fig)


# ---------------------------------------------------------------- site export

def _value(x):
    """A table cell for the site: numbers with 6 significant digits as in export_web, NaN -> null."""
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    if isinstance(x, str):
        return x
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return None
    v = float(x)
    if v.is_integer() and abs(v) < 2 ** 53:
        return int(v)
    return float(f"{v:.6g}")


def _table(df, units):
    cols = list(df.columns)
    return dict(columns=cols, units={c: u for c, u in units.items() if c in cols},
                rows=[[_value(x) for x in row] for row in df.itertuples(index=False)])


def _source(site_dir, name):
    """Provenance of one sweep from its site export docs/data/city/<name>.js (scripts/export_web.py),
    or None when that sweep has not been exported."""
    path = Path(site_dir) / f"{name}.js"
    if not path.exists():
        return None
    text = path.read_text()
    d = json.loads(text[text.index("= ", text.index("window.RESULTS[")) + 2:].strip().rstrip(";"))
    return {k: d.get(k) for k in ("name", "config", "config_sha256", "sumo_version", "git_commit", "draft")}


SUMMARY_UNITS = {"k_half": "veh/km", "k_half_seed_min": "veh/km", "k_half_seed_max": "veh/km", "capacity": "veh/h",
                 "k_at_capacity": "veh/km", "d_k_half": "veh/km", "d_k_half_seed_min": "veh/km",
                 "d_k_half_seed_max": "veh/km", "d_k_half_pct": "%", "d_capacity": "veh/h", "d_capacity_pct": "%",
                 "d_q_at_cap_mean": "veh/h", "d_q_at_cap_se": "veh/h"}


def export_site(site_dir, summary, mfd, change, v0, v_star, k_low, names, model, excluded_invalid):
    """Write docs/data/city/planning.js in the layout of traffic_project.export_web:

        window.RESULTS["city/planning"] = {
            scenario, name, model, sources: [provenance of each sweep, or null], draft,
            rule: {near-empty speed, its density, threshold speed},
            columns, units, rows                  the per-variant table (planning_summary.csv)
            speed_change: {columns, units, rows}  paired speed change per variant and density
            mfd: {columns, units, rows}           per variant and density, mean/min/max over seeds
            excluded_invalid
        }

    The top-level columns/units/rows are the summary table, so a page can read it like any
    experiment. Provenance comes from each sweep's own export docs/data/city/<name>.js (run
    scripts/export_web.py for the four configs first, on the computer that ran them); draft is
    true when a sweep is not exported or its export is a draft. No timestamp, as in export_web,
    so the same results give the same file."""
    flat = [n for v in names.values() for n in _names(v)]
    sources = [_source(site_dir, n) for n in flat]
    data = dict(
        scenario="city", name="planning", model=model, sources=sources,
        draft=any(s is None or s.get("draft") for s in sources),
        rule=dict(near_empty_speed_mps=_value(v0), near_empty_density_veh_km=_value(k_low),
                  threshold_speed_mps=_value(v_star),
                  text="critical density: where mean speed falls to half the baseline's mean speed at its "
                       "lowest density, the same threshold for every variant; capacity: highest seed-mean flow"),
        **_table(summary, SUMMARY_UNITS),
        speed_change=_table(change, {"k_target": "veh/km", "pct_mean": "%", "pct_se": "%", "pct_min": "%",
                                     "pct_max": "%"}),
        mfd=_table(mfd, {"k_target": "veh/km", "k": "veh/km", "v_mean": "m/s", "v_min": "m/s", "v_max": "m/s",
                         "q_mean": "veh/h", "q_min": "veh/h", "q_max": "veh/h"}),
        excluded_invalid=int(excluded_invalid))
    out = Path(site_dir) / "planning.js"
    out.parent.mkdir(parents=True, exist_ok=True)
    srcs = ", ".join(f"results/city/{n}.csv" for n in flat)
    out.write_text(f"// Generated by scripts/planning_figures.py from {srcs}; do not edit.\n"
                   "window.RESULTS = window.RESULTS || {};\n"
                   f'window.RESULTS["city/planning"] = {json.dumps(data, ensure_ascii=False, separators=(",", ":"))};\n')
    return out


# ---------------------------------------------------------------- main

def parse_args():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--variants", default=",".join(VARIANTS), help="comma-separated, the baseline first")
    ap.add_argument("--config-pattern", default="configs/city/bugis_all_{variant}_controller.toml")
    ap.add_argument("--name-pattern", help="result table name per variant (default: the config's name)")
    ap.add_argument("--results-dir", default="results/city", help="folder of <name>.csv; may hold {variant}")
    ap.add_argument("--runs-dir", default="runs", help="folder of the run folders (for the maps)")
    ap.add_argument("--out", default="results/city/planning")
    ap.add_argument("--site", default="docs/data/city", help="folder of the site export planning.js")
    ap.add_argument("--no-site", action="store_true", help="write no site export")
    ap.add_argument("--map-densities", help="comma-separated sweep densities (veh/km) for the maps")
    ap.add_argument("--change-min", type=float, default=0.05, help="smallest change in congested share drawn in colour")
    ap.add_argument("--skip-edges", action="store_true", help="draw the maps from <out>/planning_edges.csv, read no runs/")
    ap.add_argument("--include-invalid", action="store_true", help="keep runs whose checks failed")
    ap.add_argument("--extra", action="append", default=[], metavar="VARIANT=NAME",
                    help="another table of the same variant and settings (e.g. extra seeds), "
                         "results-dir/NAME.csv; repeatable, e.g. --extra base=bugis_all_base_braess_controller")
    return ap.parse_args()


def main():
    a = parse_args()
    variants = a.variants.split(",")
    base = variants[0]
    cfgs = {v: config.load(ROOT / a.config_pattern.format(variant=v)) for v in variants}
    names = {v: [a.name_pattern.format(variant=v) if a.name_pattern else cfgs[v]["name"]] for v in variants}
    for item in a.extra:
        variant, _, name = item.partition("=")
        if variant not in names or not name:
            raise SystemExit(f"--extra {item!r}: expected VARIANT=NAME with VARIANT one of {variants}")
        extra_cfg = ROOT / Path(a.config_pattern).parent / f"{name}.toml"
        if extra_cfg.exists():
            diff = check_same_settings(cfgs[variant], config.load(extra_cfg))
            if diff:
                raise SystemExit(f"{extra_cfg.name} differs from the {variant} config in "
                                 + "; ".join(f"{k}: {m!r} vs {e!r}" for k, (m, e) in diff.items())
                                 + ": its runs cannot join the main sweep")
        else:
            print(f"note: {extra_cfg.relative_to(ROOT)} not found, so its settings are not checked "
                  f"against the {variant} config; join only tables with the same settings")
        names[variant].append(name)
    dirs = {v: ROOT / a.results_dir.format(variant=v) for v in variants}
    out = ROOT / a.out
    figs = out / "figures"
    figs.mkdir(parents=True, exist_ok=True)

    runs, notes = load_sweeps(names, dirs, a.include_invalid)
    for v, vn in names.items():
        if len(vn) > 1:
            print(f"{v}: " + "; ".join(f"{n} ({(runs.table == n).sum()} runs, seeds "
                                         f"{sorted(int(x) for x in runs[runs.table == n].seed.unique())})" for n in vn))
    for n in notes:
        print("note:", n)
    v0, k_low = near_empty_speed(runs, base)
    v_star = v0 / 2
    summary, seeds = compare(runs, v_star, variants, base)
    change = speed_change(runs, variants, base)
    mfd = mfd_table(runs)
    seeds.to_csv(out / "planning_seeds.csv", index=False)
    summary.to_csv(out / "planning_summary.csv", index=False)
    change.to_csv(out / "planning_speed_change.csv", index=False)
    mfd.to_csv(out / "planning_mfd.csv", index=False)
    print(f"near-empty speed {v0:.3f} m/s = {3.6 * v0:.1f} km/h (baseline at {k_low:g} veh/km), "
          f"threshold {v_star:.3f} m/s")
    for _, r in summary.iterrows():
        line = (f"{r.variant:<9} k_half {r.k_half:6.2f} veh/km (seeds {r.k_half_seed_min:.2f}-{r.k_half_seed_max:.2f})  "
                f"capacity {r.capacity:6.1f} veh/h per lane at {r.k_at_capacity:g} veh/km")
        if r.variant != base:
            flag = "" if r.same_sign_k_half or math.isnan(r.d_k_half) else " [seeds disagree]"
            line += (f"  change: k_half {r.d_k_half:+.2f} ({r.d_k_half_pct:+.1f} %){flag}, capacity "
                     f"{r.d_capacity:+.1f} ({r.d_capacity_pct:+.1f} %; paired at {r.k_at_capacity:g}: "
                     f"{r.d_q_at_cap_mean:+.1f} +- {r.d_q_at_cap_se:.1f} SE)")
        print(line)
    top = summary[summary.capacity_at_top]
    if len(top):
        print("WARNING: capacity at the highest sweep density for " + ", ".join(top.variant)
              + ": flow may still rise, so it is a lower bound there (add a higher density to the sweep)")
    plot_mfd(mfd, summary, change, v0, v_star, variants, figs / "planning_mfd.png")

    edges_csv = out / "planning_edges.csv"
    map_files = []
    edges = None
    if a.skip_edges:
        if edges_csv.exists():
            edges = pd.read_csv(edges_csv)
        else:
            print(f"no {edges_csv.relative_to(ROOT)}: maps skipped")
    else:
        print("reading per-road speeds from runs/ ...")
        try:
            edges = edge_table(edge_shares(runs, cfgs, ROOT / a.runs_dir, base,
                                           main={v: n[0] for v, n in names.items()}), base)
            edges.to_csv(edges_csv, index=False, float_format="%.4g")
        except FileNotFoundError as err:
            print(f"maps skipped: {err} is missing (runs/ is not in git; use --skip-edges with planning_edges.csv)")
    if edges is not None:
        ks = ([float(x) for x in a.map_densities.split(",")] if a.map_densities
              else map_densities(summary, runs.k_target.unique(), base))
        geo = {v: edge_shapes(ROOT / cfgs[v]["network"]["net_file"]) for v in variants}
        for k in ks:
            name = f"planning_map_k{k:g}.png"
            plot_map(edges, geo, variants, k, figs / name, base, a.change_min)
            map_files.append(name)
    if not a.no_site:
        model = "/".join(sorted({cfgs[v]["model"] for v in variants}))
        print("wrote", export_site(ROOT / a.site, summary, mfd, change, v0, v_star, k_low, names, model,
                                   runs.attrs.get("excluded_invalid", 0)).relative_to(ROOT))
    print("wrote", ", ".join(str(p.relative_to(ROOT)) for p in sorted(out.rglob("*")) if p.is_file()))


if __name__ == "__main__":
    main()
