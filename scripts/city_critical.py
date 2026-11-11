"""Network critical point and capacity of a city sweep, for the site: docs/data/<page>/critical_<name>.js.

Writes the entry CRITICAL["<page>/<name>"] of GUIDE section 6 ("Website files") for one sweep of
scripts/city_sweep.py; the network page shows it in its critical density summary. Member E's estimator
(src/traffic_project/analysis/, planned) will write these entries; until it exists C fills the city
network with E's method (GUIDE section 6), as the group agreed it on 30-31 Oct 2026. The settings are
in the [critical] table of this script's config (configs/city/bugis_all_critical.toml):

  near-empty speed  v0: the seed-mean network speed (mean_speed_mps) at near_empty_density_veh_km,
                    the lowest swept density, 2.5 veh/km (member D's rule)
  critical density  k_c: the density at which the seed-mean speed falls to speed_ratio x v0, half of it
                    (member E's definition, the half-speed density), read linearly between the two
                    neighbouring swept densities (city_k_target) around the first crossing
  its range         k_c_low, k_c_high: the middle `interval` (95 %) of k_c over bootstrap_draws
                    resamples, in which the valid runs at each density are drawn with replacement, each
                    run's distance from its density's mean first stretched by sqrt(n / (n - 1)) for n
                    runs; v0 is held at its seed mean
  capacity          q_max: the maximum network flow, a measure of its own and not a second critical
                    point (member E): the top of a quadratic fitted to every valid run whose density lies
                    in capacity_window_veh_km (20-40 veh/km, fixed before the data; member E), searched
                    over the window
  its range         q_max_low, q_max_high: q_max -+ t x the standard error of the window maximum over
                    the same kind of resamples, t the 97.5 % point (for a 95 % interval) of Student's t
                    with (runs - densities) degrees of freedom (C's rule of 30 Oct, sent to member E)
Beside them the entry gives v0, the two densities around the crossing, the highest seed-mean flow and its
density, the settings and the run IDs. Only valid runs count. The two bootstraps use fixed random seeds,
and the k_c bootstrap draws its random numbers in the order of C's half-speed script of 31 Oct, so the
same tables give the same numbers (13.34 veh/km, 95 % 12.97-13.62, on the frozen sweep's table).

Inputs: the sweep of [critical] sweep_config, its summary table results/city/<name>.csv and the run record
runs/<run_id>/manifest.json of every valid run; [critical] extra_configs add sweeps with more seeds or
densities on the same settings (for example configs/city/bugis_all_controller_seeds4to6.toml).
Checks, as scripts/export_web.py makes them: the script stops when a run record is missing, when a sweep's
config changed after its runs (its hash), when the runs do not share one SUMO version and one git commit,
and when the runs came from uncommitted code (a git commit ending in -dirty), unless --allow-dirty is given;
the entry is then marked draft: true. Two checks export_web.py lacks: it stops when a run is a smoke run,
and when a valid run has no summary.json (it did not finish) or its summary.json gives another speed or flow
than the table's row (the table comes from other runs). It also stops when the sweeps differ
in their run settings or net, when a density and seed appear twice, when the speed never falls to half of
v0, and when the capacity window holds fewer than three densities. A planning variant with its own
baseline net is refused: it is judged against its baseline's v0, which scripts/planning_figures.py does.
The output has no timestamp: the same inputs give the same file.

Usage (from the repository root, on the computer that ran the sweep, after it finished from a clean commit):
    python scripts/city_critical.py --config configs/city/bugis_all_critical.toml
Preview: --preview reports the checks instead of stopping on them and writes runs/critical_preview_<name>.js
(git-ignored; --out to choose), never docs/. Only with --preview:
    --from DIR       read results/ and runs/ of another checkout, e.g. runs made from an older commit
    --sweep CONFIG   read this sweep instead of [critical] sweep_config
    --extra CONFIG   read this sweep with it instead of [critical] extra_configs (repeatable)
    --table CSV      read the main sweep's table from CSV, e.g. a smoke sweep's
                     runs/<prefix>_results/<name>.csv (scripts/city_sweep.py --prefix/--name)
    python scripts/city_critical.py --config configs/city/bugis_all_critical.toml --preview \\
        --from ../atm-network-freeze --extra configs/city/bugis_all_controller_seeds4to6.toml
"""
import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from traffic_project import ROOT, config
from traffic_project.export_web import _number, page_of

TEXT = {"run_id": str, "scenario": str, "model": str, "variant": str}
SETTINGS = ("sweep_config", "near_empty_density_veh_km", "speed_ratio", "capacity_window_veh_km",
            "interval", "bootstrap_draws", "bootstrap_seed_k_c", "bootstrap_seed_q_max")
# Config tables that must agree between the main sweep and its extra sweeps
SAME = ("run", "vehicle", "controller", "rerouting", "settle")
GRID_POINTS = 401   # points on which the quadratic's maximum is searched over the capacity window
UNITS = {"k_c": "veh/km", "k_c_low": "veh/km", "k_c_high": "veh/km", "q_max": "veh/h", "q_max_low": "veh/h",
         "q_max_high": "veh/h", "q_max_seed_mean": "veh/h"}


# ---------------------------------------------------------------- the method

def by_density(runs, column):
    """{swept density: the column's values in table order}, densities ascending. Runs are grouped by
    city_k_target, the density the sweep set, rounded to 0.01 veh/km."""
    out = {}
    for k, x in zip(runs["city_k_target"], runs[column]):
        out.setdefault(round(float(k), 2), []).append(float(x))
    return dict(sorted(out.items()))


def first_fall(means, target):
    """Index i of the first pair of neighbouring densities with means[i] >= target > means[i + 1], or None."""
    for i in range(len(means) - 1):
        if means[i] >= target > means[i + 1]:
            return i
    return None


def crossing(ks, means, target):
    """Density at which the curve means(ks) first falls through target, linear between the two
    neighbouring densities; NaN if it never does."""
    i = first_fall(means, target)
    if i is None:
        return math.nan
    return ks[i] + (means[i] - target) / (means[i] - means[i + 1]) * (ks[i + 1] - ks[i])


def stretched(values):
    """(mean, each value's distance from the mean stretched by sqrt(n / (n - 1)), n). A density with a
    single run has no spread to resample: its distances are 0."""
    v = np.asarray(values, float)
    n = len(v)
    return v.mean(), (v - v.mean()) * (np.sqrt(n / (n - 1)) if n > 1 else 0.0), n


def _alpha(level):
    return round((1 - level) / 2, 12)


def percentile_range(draws, level):
    """(low, high): the middle `level` of the draws, NaN draws left out; NaN, NaN if every draw is NaN."""
    draws = np.asarray(draws, float)
    if np.isnan(draws).all():
        return math.nan, math.nan
    a = 100 * _alpha(level)
    lo, hi = np.nanpercentile(draws, [a, 100 - a])
    return float(lo), float(hi)


def critical_density(speeds, v0, ratio, draws, seed, level):
    """k_c, its bootstrap range and the densities around the crossing, from {density: speeds}.
    The resampling draws, for each resample in turn, the runs of each density in ascending order, as C's
    half-speed script of 31 Oct does, so the same speeds and seed give the same draws."""
    ks = list(speeds)
    target = ratio * v0
    means = [np.mean(v) for v in speeds.values()]
    i = first_fall(means, target)
    parts = [stretched(v) for v in speeds.values()]
    rng = np.random.default_rng(seed)
    out = np.empty(draws)
    for b in range(draws):
        out[b] = crossing(ks, [m + dev[rng.integers(0, n, n)].mean() for m, dev, n in parts], target)
    lo, hi = percentile_range(out, level)
    return dict(k_c=crossing(ks, means, target), k_c_low=lo, k_c_high=hi,
                bracket=None if i is None else [ks[i], ks[i + 1]], draws_without_crossing=int(np.isnan(out).sum()))


def capacity(k, q, window, draws, seed, level):
    """q_max: the top of a quadratic fitted to every run with density k in window (inclusive), and
    q_max -+ t x the bootstrap standard error of the window maximum, t with (runs - densities) degrees of
    freedom. The resampling stretches each run's distance from its density's mean as above, then draws the
    runs of every density at once, as C's capacity estimate of 30 Oct does. NaN where the window holds
    fewer than three densities (no quadratic) or as many runs as densities (no spread)."""
    k_lo, k_hi = (float(x) for x in window)
    k, q = np.asarray(k, float), np.asarray(q, float)
    w = (k >= k_lo) & (k <= k_hi)
    kw, qw = k[w], q[w]
    dens = np.unique(kw)
    out = dict(q_max=math.nan, q_max_low=math.nan, q_max_high=math.nan, density=math.nan, runs=int(len(kw)),
               dof=int(len(kw) - len(dens)), densities=[float(x) for x in dens], t=math.nan,
               draws_at_window_edge=math.nan)
    if len(dens) < 3:
        return out
    grid = np.linspace(k_lo, k_hi, GRID_POINTS)
    p = np.polyfit(kw, qw, 2)
    fit = np.polyval(p, grid)
    out.update(q_max=float(fit.max()), density=float(grid[fit.argmax()]))
    groups = [np.flatnonzero(kw == x) for x in dens]
    qs = qw.copy()
    for g in groups:
        m, dev, _ = stretched(qw[g])
        qs[g] = m + dev
    rng = np.random.default_rng(seed)
    idx = np.concatenate([g[rng.integers(0, len(g), size=(draws, len(g)))] for g in groups], axis=1)
    kk = kw[np.concatenate(groups)]
    coef = np.linalg.lstsq(np.vstack([np.ones_like(kk), kk, kk * kk]).T, qs[idx].T, rcond=None)[0]
    curves = coef[0][:, None] + coef[1][:, None] * grid + coef[2][:, None] * grid ** 2
    top = curves.argmax(axis=1)
    out["draws_at_window_edge"] = float(np.mean((top == 0) | (top == len(grid) - 1)))
    if out["dof"] >= 1:
        t = float(stats.t.ppf(1 - _alpha(level), out["dof"]))
        se = float(curves.max(axis=1).std(ddof=1))
        out.update(q_max_low=out["q_max"] - t * se, q_max_high=out["q_max"] + t * se, t=t)
    return out


def settings_of(cfg):
    """The [critical] table of the script's config, every key checked."""
    s = cfg.get("critical")
    if s is None:
        raise SystemExit(f"{cfg['_path']} has no [critical] table")
    missing = [key for key in SETTINGS if key not in s]
    if missing:
        raise SystemExit(f"{cfg['_path']}: [critical] lacks {', '.join(missing)}")
    if not 0 < s["interval"] < 1 or not 0 < s["speed_ratio"] < 1 or s["bootstrap_draws"] < 2:
        raise SystemExit(f"{cfg['_path']}: [critical] interval and speed_ratio must lie between 0 and 1, "
                         "and bootstrap_draws must be at least 2")
    return s


def estimate(runs, s):
    """Everything the entry reports, from the valid runs (one table, all sweeps joined) and settings s."""
    if runs.empty:
        raise ValueError("no valid runs")
    speeds = by_density(runs, "mean_speed_mps")
    k0 = round(float(s["near_empty_density_veh_km"]), 2)
    if k0 not in speeds:
        raise ValueError(f"no valid run at the near-empty density {k0:g} veh/km")
    if k0 != min(speeds):
        raise ValueError(f"the near-empty density {k0:g} veh/km is not the lowest swept density ({min(speeds):g})")
    v0 = float(np.mean(speeds[k0]))
    kc = critical_density(speeds, v0, s["speed_ratio"], s["bootstrap_draws"], s["bootstrap_seed_k_c"],
                          s["interval"])
    cap = capacity(runs["city_k_target"], runs["flow_veh_h"], s["capacity_window_veh_km"], s["bootstrap_draws"],
                   s["bootstrap_seed_q_max"], s["interval"])
    flows = {k: float(np.mean(v)) for k, v in by_density(runs, "flow_veh_h").items()}
    k_peak = max(flows, key=flows.get)
    return dict(kc, v0=v0, cap=cap, q_seed_mean=flows[k_peak], k_seed_mean=k_peak, densities=list(speeds),
                n_runs=len(runs), seeds=sorted({int(x) for x in runs["seed"]}))


def method_text(s):
    lo, hi = s["capacity_window_veh_km"]
    pct = f"{100 * s['interval']:g} %"
    return (f"k_c: half-speed density (member E's definition, agreed 31 Oct 2026): the density at which the "
            f"seed-mean network speed falls to {s['speed_ratio']:g} of the near-empty speed v0, the seed-mean "
            f"speed at {s['near_empty_density_veh_km']:g} veh/km, read linearly between neighbouring swept "
            f"densities; range: the middle {pct} of {s['bootstrap_draws']} bootstrap resamples of the runs at "
            f"each density, each run's distance from its density's mean stretched by sqrt(n/(n-1)), v0 held "
            f"fixed. q_max: capacity, the top of a quadratic fitted to every valid run at {lo:g}-{hi:g} veh/km "
            f"(a window fixed in advance, member E); range: q_max -+ t(runs - densities) x the bootstrap "
            f"standard error of the window maximum")


# ---------------------------------------------------------------- inputs and checks

def read_table(path):
    """(valid runs, every run) of a summary table, in file order."""
    path = Path(path)
    if not path.exists():
        raise SystemExit(f"missing {path}: run the sweep first (scripts/city_sweep.py)")
    df = pd.read_csv(path, dtype=TEXT)
    ok = df["valid"].astype(str).str.strip().str.lower() == "true"
    return df[ok].reset_index(drop=True), df


def load_sweeps(paths, table=None, src=None):
    """[{cfg, table, runs, all}] for the sweep configs in paths (the main sweep first); table replaces the
    main sweep's table. Stops on a planning variant with its own baseline, on sweeps whose run settings or
    net differ, and on a density and seed found twice."""
    src = Path(src or ROOT)
    sweeps = []
    for i, p in enumerate(paths):
        cfg = config.load(ROOT / p)
        if cfg["scenario"] != "city":
            raise SystemExit(f"{p}: scenario {cfg['scenario']!r}; this script reads city sweeps")
        nw = cfg.get("network", {})
        if nw.get("baseline_net_file") and nw["baseline_net_file"] != nw["net_file"]:
            raise SystemExit(f"{p} is a planning variant of {nw['baseline_net_file']}: its critical point halves "
                             "the baseline's near-empty speed (scripts/planning_figures.py), which this script does not")
        path = Path(table) if (table and i == 0) else src / "results" / cfg["scenario"] / f"{cfg['name']}.csv"
        runs, everything = read_table(path)
        sweeps.append(dict(cfg=cfg, table=path, runs=runs, all=everything))
    main = sweeps[0]["cfg"]
    for s in sweeps[1:]:
        cfg = s["cfg"]
        differ = [t for t in SAME if cfg.get(t) != main.get(t)]
        if cfg["network"]["net_file"] != main["network"]["net_file"]:
            differ.append("network.net_file")
        if differ:
            raise SystemExit(f"{cfg['_path']} differs from {main['_path']} in {', '.join(differ)}: "
                             "only sweeps on the same settings can be read together")
    keys = pd.concat([s["all"][["city_k_target", "seed"]] for s in sweeps], ignore_index=True)
    dup = keys[keys.duplicated(keep=False)]
    if len(dup):
        k, seed = dup.iloc[0]
        raise SystemExit(f"{k:g} veh/km, seed {seed} is in two tables: extra sweeps must add new seeds or densities")
    return sweeps


def provenance(sweeps, src=None, allow_dirty=False):
    """(fields for the entry, problems): the run records' config hash per sweep, SUMO version, git commit
    and draft flag, and every check that fails (see the module docstring)."""
    src = Path(src or ROOT)
    problems, sumo, commits = [], set(), set()
    for s in sweeps:
        cfg, hashes = s["cfg"], set()
        for run_id in s["runs"]["run_id"]:
            path = src / "runs" / run_id / "manifest.json"
            if not path.exists():
                problems.append(f"missing run record {path}; read the runs on the computer that ran the sweep")
                continue
            m = json.loads(path.read_text())
            hashes.add(m["config_sha256"])
            sumo.add(m["sumo_version"])
            commits.add(m["git_commit"])
            if (m.get("parameters", {}).get("overrides") or {}).get("smoke_run"):
                problems.append(f"{run_id} is a smoke run (city_sweep.py overrides): not a result")
            # city_sweep.py writes every manifest before the first run starts, and summary.json only once
            # the run is measured: a table beside records of unfinished or other runs must not pass
            done = path.with_name("summary.json")
            row = s["runs"].loc[s["runs"]["run_id"] == run_id].iloc[0]
            if not done.exists():
                problems.append(f"{run_id} has no summary.json: the run did not finish; rerun the sweep")
            elif not all(math.isclose(float(row[c]), float(json.loads(done.read_text())[c]), rel_tol=1e-9)
                         for c in ("mean_speed_mps", "flow_veh_h")):
                problems.append(f"{run_id}: the table's row is not the run's summary.json; the table comes from "
                                "other runs (rerun the sweep, or measure it again with city_sweep.py --measure-only)")
        s["config_sha256"] = ", ".join(sorted(hashes))
        if len(hashes) > 1:
            problems.append(f"the runs of {cfg['_path']} differ in config hash ({s['config_sha256']}); rerun the sweep")
        elif hashes and hashes != {cfg["_sha256"]}:
            problems.append(f"{cfg['_path']} changed after the runs (runs {s['config_sha256']}, file now "
                            f"{cfg['_sha256']}); rerun the sweep")
    if len(sumo) > 1:
        problems.append(f"the runs differ in SUMO version ({'; '.join(sorted(sumo))}); rerun the sweeps together")
    if len(commits) > 1:
        problems.append(f"the runs differ in git commit ({', '.join(sorted(commits))}); rerun the sweeps together")
    draft = any(c.endswith("-dirty") for c in commits)
    if draft and not allow_dirty:
        problems.append(f"the runs came from uncommitted code ({', '.join(sorted(commits))}); commit, rerun the "
                        "sweep and write again, or pass --allow-dirty for a draft")
    return dict(sumo_version="; ".join(sorted(sumo)), git_commit=", ".join(sorted(commits)), draft=draft), problems


# ---------------------------------------------------------------- output

def _num(x):
    """A number for the site: 6 significant digits, an integer where it is one, null for NaN or None."""
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return None
    return _number(x)


def entry(cfg, s, sweeps, est, prov, name, page):
    """The CRITICAL entry as a dict, in a fixed key order."""
    main, cap = sweeps[0], est["cap"]
    excluded = [rid for sw in sweeps for rid, ok in zip(sw["all"]["run_id"], sw["all"]["valid"].astype(str))
                if ok.strip().lower() != "true"]
    return {
        "scenario": main["cfg"]["scenario"], "page": page, "name": name, "model": main["cfg"]["model"],
        "config": main["cfg"]["_path"], "config_sha256": main["config_sha256"],
        "sumo_version": prov["sumo_version"], "git_commit": prov["git_commit"], "draft": prov["draft"],
        "method": method_text(s), "units": UNITS,
        "k_c": _num(est["k_c"]), "k_c_low": _num(est["k_c_low"]), "k_c_high": _num(est["k_c_high"]),
        "q_max": _num(cap["q_max"]), "q_max_low": _num(cap["q_max_low"]), "q_max_high": _num(cap["q_max_high"]),
        "interval": _num(s["interval"]),
        "near_empty_density_veh_km": _num(s["near_empty_density_veh_km"]), "near_empty_speed_mps": _num(est["v0"]),
        "speed_ratio": _num(s["speed_ratio"]),
        "k_c_bracket_veh_km": None if est["bracket"] is None else [_num(x) for x in est["bracket"]],
        "k_c_draws_without_crossing": est["draws_without_crossing"],
        "q_max_density_veh_km": _num(cap["density"]),
        "q_max_window_veh_km": [_num(x) for x in s["capacity_window_veh_km"]],
        "q_max_runs": cap["runs"], "q_max_dof": cap["dof"], "q_max_draws_at_window_edge": _num(cap["draws_at_window_edge"]),
        "q_max_seed_mean": _num(est["q_seed_mean"]), "q_max_seed_mean_density_veh_km": _num(est["k_seed_mean"]),
        "bootstrap_draws": s["bootstrap_draws"], "bootstrap_seeds": [s["bootstrap_seed_k_c"], s["bootstrap_seed_q_max"]],
        "critical_config": cfg["_path"], "critical_config_sha256": cfg["_sha256"],
        "extra_configs": [{"config": sw["cfg"]["_path"], "config_sha256": sw["config_sha256"]} for sw in sweeps[1:]],
        "densities_veh_km": [_num(x) for x in est["densities"]], "seeds": est["seeds"],
        "run_ids": [rid for sw in sweeps for rid in sw["runs"]["run_id"]],
        "excluded_invalid": len(excluded), "excluded_run_ids": excluded,
    }


def js_text(data, sources, preview=False):
    """The file: a comment naming the script and its source, the object, and the one entry."""
    key = f'{data["page"]}/{data["name"]}'
    head = (f"// Preview by scripts/city_critical.py from {sources}; not for the site; do not edit.\n" if preview
            else f"// Generated by scripts/city_critical.py from {sources}; do not edit.\n")
    return (head + "window.CRITICAL = window.CRITICAL || {};\n"
            + f'window.CRITICAL["{key}"] = {json.dumps(data, ensure_ascii=False, separators=(",", ":"))};\n')


def report(name, est, s, data, log=print):
    cap, pct = est["cap"], f"{100 * s['interval']:g} %"
    log(f"{name}: {est['n_runs']} valid runs at {len(est['densities'])} densities, seeds "
        f"{', '.join(map(str, est['seeds']))}; left out (invalid): {', '.join(data['excluded_run_ids']) or 'none'}")
    log(f"  near-empty speed v0 {est['v0']:.4f} m/s = {est['v0'] * 3.6:.2f} km/h at {s['near_empty_density_veh_km']:g} "
        f"veh/km; {s['speed_ratio']:g} of it {s['speed_ratio'] * est['v0']:.4f} m/s = {s['speed_ratio'] * est['v0'] * 3.6:.2f} km/h")
    bracket = "no crossing" if est["bracket"] is None else f"between {est['bracket'][0]:g} and {est['bracket'][1]:g} veh/km"
    log(f"  k_c {est['k_c']:.4f} veh/km ({pct}: {est['k_c_low']:.4f}-{est['k_c_high']:.4f}), {bracket}; "
        f"{est['draws_without_crossing']} of {s['bootstrap_draws']} resamples without a crossing")
    lo, hi = s["capacity_window_veh_km"]
    log(f"  q_max {cap['q_max']:.3f} veh/h ({pct}: {cap['q_max_low']:.3f}-{cap['q_max_high']:.3f}), top at "
        f"{cap['density']:.1f} veh/km; quadratic over {lo:g}-{hi:g} veh/km on {cap['runs']} runs at "
        f"{len(cap['densities'])} densities, t({cap['dof']}) = {cap['t']:.3f}; share of resamples with their "
        f"maximum at a window edge {cap['draws_at_window_edge']:.4f}")
    log(f"  highest seed-mean flow {est['q_seed_mean']:.2f} veh/h at {est['k_seed_mean']:g} veh/km")


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", required=True, help="configs/city/<name>_critical.toml, with a [critical] table")
    ap.add_argument("--allow-dirty", action="store_true", help="write runs from uncommitted code as a draft")
    ap.add_argument("--preview", action="store_true",
                    help="report the checks instead of stopping on them; write runs/critical_preview_<name>.js")
    ap.add_argument("--from", dest="src", help="preview: read results/ and runs/ of this checkout")
    ap.add_argument("--sweep", help="preview: read this sweep config instead of [critical] sweep_config")
    ap.add_argument("--extra", action="append", help="preview: read this sweep config with it (repeatable)")
    ap.add_argument("--table", help="preview: the main sweep's summary table, e.g. a smoke sweep's")
    ap.add_argument("--out", help="preview: the file to write")
    a = ap.parse_args(argv)
    if not a.preview and any(x is not None for x in (a.src, a.sweep, a.extra, a.table, a.out)):
        ap.error("--from, --sweep, --extra, --table and --out need --preview")
    return a


def main(argv=None):
    a = parse_args(argv)
    cfg = config.load(a.config)
    s = settings_of(cfg)
    paths = [a.sweep or s["sweep_config"]] + (a.extra if a.extra is not None else list(s.get("extra_configs", [])))
    src = Path(a.src).resolve() if a.src else ROOT
    sweeps = load_sweeps(paths, table=a.table, src=src)
    prov, problems = provenance(sweeps, src, allow_dirty=a.allow_dirty)
    if problems and not a.preview:
        raise SystemExit("not written:\n  " + "\n  ".join(problems))
    runs = pd.concat([sw["runs"] for sw in sweeps], ignore_index=True)
    try:
        est = estimate(runs, s)
    except ValueError as e:
        raise SystemExit(f"not written: {e}")
    main_cfg = sweeps[0]["cfg"]
    name = Path(a.table).stem if a.table else main_cfg["name"]
    page = page_of(main_cfg)
    if not a.preview:
        failed = [what for what, x in (("k_c (the speed never falls to the half-speed level)", est["k_c"]),
                                       ("q_max (fewer than three densities in the window)", est["cap"]["q_max"]),
                                       ("the range of q_max (no more runs than densities in the window)",
                                        est["cap"]["q_max_low"])) if math.isnan(x)]
        if failed:
            raise SystemExit("not written: no " + "; no ".join(failed))
    data = entry(cfg, s, sweeps, est, prov, name, page)
    if a.preview:
        data["preview_problems"] = problems
        out = Path(a.out) if a.out else ROOT / "runs" / f"critical_preview_{name}.js"
        sources = " and ".join(str(sw["table"]) for sw in sweeps)
    else:
        out = ROOT / "docs" / "data" / page / f"critical_{name}.js"
        sources = " and ".join(str(sw["table"].relative_to(ROOT)) for sw in sweeps)
    report(name, est, s, data)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(js_text(data, sources, preview=a.preview))
    if a.preview:
        print("preview: " + ("every check passes" if not problems else
                             "not exportable as it stands:\n  " + "\n  ".join(problems)))
    print(f"wrote {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")
    return out


if __name__ == "__main__":
    main()
