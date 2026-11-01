"""Task 6: queues, spillback, largest cluster and betweenness-vs-onset on a finished city sweep.

Reads a sweep's results table and run folders read-only (edge<P>.xml.gz) and the
reference run's edgeData; classifies every edge with the config's [measure] congestion criterion;
writes tables (CSV) and figures. Nothing is re-simulated. checks.json compares G1, phi_len
and the spillback count with the sweep's own columns; both come from the same criterion
code, so that comparison checks the files and windows read, not the criterion.

    python scripts/city_measures.py --config configs/city/bugis_all_controller.toml

writes results/<scenario>/<name>_measures/ in this checkout (tables, checks.json and figures
01-05). The analysis settings (onset share and its checks, censoring, the flow plateau, the
heat-map density) are keys of the config's [measure] table; the flags below override them
for a one-off look. --root is the checkout that holds runs/ and results/ (default: this one).
"""
import argparse
import json
import sys
import time
import tomllib
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

from traffic_project import congestion as cg
from traffic_project import mfd_measures as mm

G = {}   # shared with the worker processes (fork)
MEASURE_KEYS = ("onset_share", "onset_share_checks", "onset_censor_factor", "flow_plateau_veh_km",
                "heatmap_density_veh_km")
BLUE, ORANGE, AQUA, GREY, INK = "#2a78d6", "#eb6834", "#1baf7a", "#8a8984", "#0b0b0b"


def parse_args():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", required=True)
    ap.add_argument("--root", default=".", help="checkout holding runs/ and results/ (read only)")
    ap.add_argument("--tables-dir", help="default results/<scenario>/<name>_measures in this checkout")
    ap.add_argument("--figures-dir", help="default the same folder as the tables")
    ap.add_argument("--onset-threshold", type=float,
                    help="override [measure] onset_share: share of measured cycles congested that marks onset")
    ap.add_argument("--peak-density", type=float,
                    help="veh/km: mark one flow peak with a line instead of shading [measure] flow_plateau_veh_km")
    ap.add_argument("--peak-range", type=float, nargs=2, metavar=("LO", "HI"),
                    help="veh/km: override [measure] flow_plateau_veh_km, the flat top shaded in the figures")
    ap.add_argument("--include-invalid", action="store_true",
                    help="also measure runs whose results row has valid = False (default: skip them)")
    ap.add_argument("--heatmap-run", default=None, help="run_id for the per-edge queue heat map")
    ap.add_argument("--results-csv", help="override the results table (default results/<scenario>/<name>.csv)")
    ap.add_argument("--prefix", help="override [sweep] run_prefix (smoke sweeps)")
    ap.add_argument("--warmup-s", type=float, help="override [run] warmup_s (smoke sweeps)")
    ap.add_argument("--jobs", type=int, default=8)
    return ap.parse_args()


def select_runs(res, include_invalid=False):
    """The results rows to measure and the run_ids left out: rows with valid = False are left
    out unless include_invalid (valid is read as text, so "True"/"False" strings work too)."""
    if include_invalid or "valid" not in res:
        return res, []
    ok = res["valid"].astype(str).str.lower() == "true"
    return res[ok], list(res.loc[~ok, "run_id"])


def measure_one(job):
    run_id, k, seed, n = job
    net, m, vref, adj = G["net"], G["m"], G["vref"], G["adj"]
    run = cg.read_edgedata(G["runs"] / run_id / G["edfile"])
    state = cg.classify(cg.relative_speed(run, vref), r_on=m["r_on"], persist_m=m["persist_m"])
    keep = state.index >= G["warmup"]
    # G1, G2 and phi_len again, with the criterion code the sweep itself uses (congestion.py):
    # comparing them with the sweep's columns checks the files, window and net read here,
    # not the criterion
    ser = cg.order_parameters(state[keep], run, net.edges, adj, m.get("weight", "lane_length"))
    summ, per_edge, spill = mm.run_measures(run, state, net.edges, G["warmup"], G["P"], n, m)
    qfile = G["runs"] / run_id / G["qfile"] if G["qfile"] else None   # runs made with [run] queue_output_s
    if qfile is not None and qfile.exists():
        summ.update(mm.queue_output_measures(mm.read_queue_output(qfile), state, spill, net.edges,
                                             G["warmup"], m["veh_length_m"] + m["min_gap_m"], G["P"]))
    summ.update(run_id=run_id, k=k, seed=seed, G1_recomputed=float(ser.G1.mean()),
                G2_recomputed=float(ser.G2.mean()), phi_len_recomputed=float(ser.phi_len.mean()))
    heat = None
    if run_id == G["heat_run"]:
        _, _, ratio = mm.queue_table(run, net.edges, G["P"], m["veh_length_m"], m["min_gap_m"])
        heat = ratio
    return summ, per_edge, heat


def mean_sd(df, cols):
    g = df.groupby("k")[cols]
    out = g.mean().add_suffix("_mean").join(g.std(ddof=1).add_suffix("_sd"))
    return out[[c + s for c in cols for s in ("_mean", "_sd")]]


def style(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#e4e3df", lw=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(colors="#52514e", labelsize=9)


def seeds_and_mean(ax, df, col, color, label):
    ax.scatter(df.k, df[col], s=14, color=color, alpha=0.45, lw=0)
    g = df.groupby("k")[col].mean()
    ax.plot(g.index, g.values, color=color, lw=2, marker="o", ms=4, label=label)
    return g


def peak_line(ax, peak, rng=None):
    if rng:
        ax.axvspan(rng[0], rng[1], color="#efeeea", zorder=0)
    else:
        ax.axvline(peak, color=GREY, lw=1, ls="--")


def peak_text(peak, rng=None, sep=" "):
    return f"flow plateau{sep}{rng[0]:g}-{rng[1]:g} veh/km" if rng else f"flow peak{sep}{peak:g} veh/km"


def figures(per_run, onset, btw, corr, heat, a):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    out = Path(a.figures_dir)
    out.mkdir(parents=True, exist_ok=True)
    peak = a.peak_density
    plt.rcParams.update({"font.size": 9, "axes.titlesize": 10, "axes.labelcolor": INK})

    # 01 MFD inputs: flow, speed, halting share
    fig, axs = plt.subplots(1, 3, figsize=(11, 3.4), dpi=130)
    seeds_and_mean(axs[0], per_run, "flow_veh_h", BLUE, r"$k \cdot \bar v$ (summary output)")
    seeds_and_mean(axs[0], per_run, "edgedata_flow_veh_h", ORANGE, "edgeData distance / (lane length x time)")
    axs[0].set(xlabel="density k (veh/km per lane)", ylabel="flow q (veh/h per lane)", title="Flow")
    axs[0].legend(frameon=False, fontsize=8, loc="lower right")
    seeds_and_mean(axs[1], per_run, "mean_speed_mps", BLUE, "")
    axs[1].set(xlabel="density k (veh/km per lane)", ylabel=r"mean speed $\bar v$ (m/s)", title="Speed")
    seeds_and_mean(axs[2], per_run, "city_halting_share", BLUE, "summary output: halting / running")
    seeds_and_mean(axs[2], per_run, "halted_share", ORANGE, "edgeData: waitingTime / (P x N)")
    axs[2].set(xlabel="density k (veh/km per lane)", ylabel="stopped-car share", title="Stopped cars",
               ylim=(0, 1))
    axs[2].legend(frameon=False, fontsize=8, loc="lower right")
    for ax in axs:
        style(ax); peak_line(ax, peak, a.peak_range)
    if a.peak_range:
        axs[0].text(sum(a.peak_range) / 2, 0.98, peak_text(peak, a.peak_range, "\n"), transform=axs[0].get_xaxis_transform(),
                    ha="center", va="top", color="#52514e", fontsize=8)
    else:
        axs[0].annotate(peak_text(peak), (peak, axs[0].get_ylim()[1]), xytext=(-4, -12), textcoords="offset points",
                        ha="right", color="#52514e", fontsize=8)
    fig.tight_layout(); fig.savefig(out / "01-mfd-inputs.png"); plt.close(fig)

    # 02 queues and spillback
    fig, axs = plt.subplots(1, 2, figsize=(9.5, 3.4), dpi=130)
    seeds_and_mean(axs[0], per_run, "city_congested_length_fraction", GREY, r"congested ($\phi_{len}$)")
    seeds_and_mean(axs[0], per_run, "queued_lane_share", BLUE, "standing queue (cycle mean)")
    seeds_and_mean(axs[0], per_run, "spill_len_share", ORANGE, "in spillback")
    axs[0].set(xlabel="density k (veh/km per lane)", ylabel="share of total lane length",
               title="Queued and spilled-back length", ylim=(0, None))
    axs[0].legend(frameon=False, fontsize=8, loc="upper left")
    seeds_and_mean(axs[1], per_run, "spill_events_per_h", ORANGE, "")
    axs[1].set(xlabel="density k (veh/km per lane)", ylabel="spillback onsets per hour (network)",
               title="Spillback events", ylim=(0, None))
    for ax in axs:
        style(ax); peak_line(ax, peak, a.peak_range)
    fig.tight_layout(); fig.savefig(out / "02-queues-spillback.png"); plt.close(fig)

    # 03 G1 and G2 against density
    fig, ax = plt.subplots(figsize=(6.2, 3.8), dpi=130)
    seeds_and_mean(ax, per_run, "city_congested_length_fraction", GREY, r"all congested length $\phi_{len}$")
    seeds_and_mean(ax, per_run, "city_largest_cluster", BLUE, r"largest cluster $G_1$")
    g2 = seeds_and_mean(ax, per_run, "city_second_cluster", ORANGE, r"second cluster $G_2$")
    peak_line(ax, peak, a.peak_range)
    if a.peak_range:
        ax.text(sum(a.peak_range) / 2, 0.98, peak_text(peak, a.peak_range, "\n"), transform=ax.get_xaxis_transform(),
                ha="center", va="top", color="#52514e", fontsize=8)
    else:
        ax.annotate(peak_text(peak, sep="\n"), (peak, 0.5), xytext=(4, 0), textcoords="offset points",
                    color="#52514e", fontsize=8)
    ax.annotate(f"$G_2$ peak {g2.idxmax():g} veh/km", (g2.idxmax(), g2.max()), xytext=(0, -14),
                textcoords="offset points", ha="center", color="#52514e", fontsize=8)
    ax.set(xlabel="density k (veh/km per lane)", ylabel="share of total lane length",
           title="Largest congested cluster against density", ylim=(0, None))
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    style(ax); fig.tight_layout(); fig.savefig(out / "03-g1-vs-density.png"); plt.close(fig)

    # 04 betweenness against onset density
    fig, axs = plt.subplots(1, 2, figsize=(11, 4.8), dpi=130, sharey=False)
    ks = sorted(onset.dropna().unique())
    cats = ks + [np.nan]
    labels = [f"{k:g}" for k in ks] + [f"none\n(<= {a.max_density:g})"]
    rng = np.random.default_rng(0)
    for ax, col, title in ((axs[0], "btw_junction_emp_lane", "junction graph (edge betweenness)"),
                           (axs[1], "btw_turn_emp_lane", "turn graph (turn restrictions kept)")):
        floor = btw[col][btw[col] > 0].min() / 2
        for i, c in enumerate(cats):
            sel = onset.isna() if np.isnan(c) else onset == c
            y = np.maximum(btw.loc[sel[sel].index, col], floor)
            x = i + rng.uniform(-0.28, 0.28, len(y))
            ax.scatter(x, y, s=7, color=GREY if np.isnan(c) else BLUE, alpha=0.5, lw=0)
            if len(y):
                ax.plot([i - 0.35, i + 0.35], [np.median(y)] * 2, color=ORANGE, lw=2.2)
            ax.text(i, 0.01, f"n={len(y)}", transform=ax.get_xaxis_transform(), ha="center",
                    fontsize=7, color="#52514e")
        ax.set_yscale("log")
        ax.set_xticks(range(len(cats)), labels)
        c = corr[(corr.graph == col) & (corr.threshold == a.onset_threshold)].iloc[0]
        ax.set(xlabel="onset density (veh/km per lane): first k with the edge congested > "
                      f"{a.onset_threshold:.0%} of cycles",
               ylabel="betweenness per lane (measured free-flow times, log)")
        ax.set_title(f"{title}\nSpearman rho = {c.rho_censored:.2f} (all {int(c.n_edges)} edges, none ranked last); "
                     f"{c.rho_onset_only:.2f} ({int(c.n_onset)} with onset)\n"
                     f"with the reference run's load removed: {c.partial_censored:.2f} and {c.partial_onset_only:.2f}\n"
                     f"with the load and lane count removed: {c.partial_load_lanes_censored:.2f} and "
                     f"{c.partial_load_lanes_onset_only:.2f}",
                     fontsize=9)
        style(ax)
    axs[0].scatter([], [], color=BLUE, s=10, label="edge"); axs[0].plot([], [], color=ORANGE, lw=2, label="median")
    axs[0].legend(frameon=False, fontsize=8, loc="lower left", bbox_to_anchor=(0, 0.05))
    fig.tight_layout(); fig.savefig(out / "04-betweenness-vs-onset.png"); plt.close(fig)

    # 05 per-edge queue over time, one run
    if heat is not None:
        order = onset.fillna(a.censor_at).sort_values(kind="stable").index
        h = heat.reindex(columns=order).fillna(0.0).T
        fig, ax = plt.subplots(figsize=(9, 4.4), dpi=130)
        im = ax.imshow(np.clip(h.to_numpy(), 0, 1), aspect="auto", cmap="Blues", vmin=0, vmax=1,
                       extent=(h.columns[0], h.columns[-1] + G["P"], len(order), 0), interpolation="nearest")
        ax.axvline(G["warmup"], color=ORANGE, lw=1.2, ls="--")
        ax.text(G["warmup"] + 40, 20, "measured from here", color=ORANGE, fontsize=8, ha="left", va="top")
        bounds = onset.reindex(order).fillna(a.censor_at).to_numpy()
        for kk in ks:
            y = int(np.searchsorted(bounds, kk, side="right"))
            ax.axhline(y, color="#d0cfca", lw=0.6)
        ax.set(xlabel="time (s)", ylabel=f"edges ({len(order)}), sorted by onset density",
               title=f"Cycle-mean standing queue / edge length, {G['heat_run']}")
        cb = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.01)
        cb.set_label("queue ratio (clipped at 1)")
        fig.tight_layout(); fig.savefig(out / "05-queue-heatmap.png"); plt.close(fig)


def main():
    a = parse_args()
    t0 = time.time()
    cfg = tomllib.loads(Path(a.config).read_text())
    m, root = cfg["measure"], Path(a.root).resolve()
    missing = [k for k in MEASURE_KEYS if k not in m]
    if missing:
        sys.exit(f"{a.config}: [measure] lacks {', '.join(missing)} (see configs/city/bugis_all_controller.toml)")
    if a.onset_threshold is None:
        a.onset_threshold = float(m["onset_share"])
    if a.peak_range is None and a.peak_density is None:
        a.peak_range = [float(v) for v in m["flow_plateau_veh_km"]]
    out_dir = Path(__file__).resolve().parents[1] / "results" / cfg["scenario"] / f"{cfg['name']}_measures"
    a.tables_dir = a.tables_dir or out_dir
    a.figures_dir = a.figures_dir or a.tables_dir
    net = cg.read_net(root / cfg["network"]["net_file"])
    P = cg.cycle_period(net, m["period_s"]) * m.get("period_mult", 1)
    if m.get("period_mult", 1) != 1:
        sys.exit("period_mult != 1 is not supported here")
    edfile = cfg["inputs"]["edgedata_file"].format(period=P)
    q_s = cfg["run"].get("queue_output_s")
    if q_s and float(q_s) != P:
        sys.exit(f"[run] queue_output_s = {q_s:g} s, but the queue measures need the criterion period {P:g} s")
    res = pd.read_csv(a.results_csv or root / "results" / cfg["scenario"] / f"{cfg['name']}.csv")
    res, skipped = select_runs(res, a.include_invalid)
    if skipped:
        print(f"skipping {len(skipped)} run(s) with valid = False: {', '.join(skipped)}")
    prefix = a.prefix or cfg["sweep"]["run_prefix"]
    ref_id = f"{prefix}_k{float(m['reference_density_veh_km']):g}_s{m['reference_seed']}"
    ref = cg.read_edgedata(root / "runs" / ref_id / edfile)
    warmup = float(a.warmup_s if a.warmup_s is not None else cfg["run"]["warmup_s"])
    vref, info = cg.free_flow_reference(ref, net.edges, warmup, m["vref_min_sampled_s"],
                                        m.get("vref_fallback", "class_median"))
    G.update(net=net, m=m, vref=vref, adj=cg.edge_adjacency(net, m["adjacency"]), runs=root / "runs",
             edfile=edfile, warmup=warmup, P=P,
             qfile=f"queue{float(cfg['run']['queue_output_s']):g}.xml.gz" if cfg["run"].get("queue_output_s") else None,
             heat_run=a.heatmap_run or f"{prefix}_k{float(m['heatmap_density_veh_km']):g}_s1")
    jobs = [(r.run_id, float(r.city_k_target), int(r.seed), int(r.city_n_vehicles)) for r in res.itertuples()]
    with Pool(min(a.jobs, len(jobs))) as pool:
        outs = pool.map(measure_one, jobs)
    summ = pd.DataFrame([o[0] for o in outs])
    keep_cols = ["run_id", "density_veh_km", "flow_veh_h", "mean_speed_mps", "city_halting_share",
                 "city_congested_length_fraction", "city_largest_cluster", "city_second_cluster",
                 "city_largest_cluster_var", "city_spillback_events"]
    per_run = summ.merge(res[keep_cols], on="run_id").sort_values(["k", "seed"])
    qo_cols = [c for c in summ.columns if c.startswith("qo_")]
    heat = next((o[2] for o in outs if o[2] is not None), None)

    # onset density and betweenness
    shares = mm.congested_shares({(o[0]["k"], o[0]["seed"]): o[1].congested_share for o in outs})
    # betweenness variants: graph (junction, turn) x weights (speed limit; measured near-empty
    # speed vref, "emp") x raw or per lane ("lane"); *_emp_lane is task 3's design
    tt_emp = mm.free_flow_time(net.edges, vref)
    btw = {}
    for graph, fn in (("junction", mm.junction_betweenness), ("turn", mm.turn_betweenness)):
        for tag, tt in (("", None), ("_emp", tt_emp)):
            b = fn(net, tt)
            btw[f"btw_{graph}{tag}"] = b
            btw[f"btw_{graph}{tag}_lane"] = mm.per_lane(b, net.edges)
    btw = pd.DataFrame(btw)
    load = mm.reference_load(ref, net.edges, warmup)
    a.max_density = float(shares.index.max())
    censor = a.censor_at = a.max_density * float(m["onset_censor_factor"])
    edges = net.edges[["length", "lanes", "limit"]].join(btw)
    edges["vref"], edges["ref_load"] = vref, load
    rows = []
    for th in sorted({a.onset_threshold, *map(float, m["onset_share_checks"])}):
        on = cg.onset_density(shares, th)
        edges[f"onset_k_{th:g}"] = on
        for col in btw.columns:
            rows.append(dict(threshold=th, graph=col,
                             **mm.onset_correlation(edges[col], on, censor, load, net.edges.lanes)))
    corr = pd.DataFrame(rows)
    onset = edges[f"onset_k_{a.onset_threshold:g}"]
    # length as a confounder check: betweenness and onset against edge length
    conf = dict(rho_length_btw_junction=float(pd.Series(edges.length).corr(edges.btw_junction, "spearman")),
                rho_length_onset=float(edges.length.corr(onset.fillna(censor), "spearman")),
                rho_load_btw_junction=float(edges.ref_load.corr(edges.btw_junction, "spearman")),
                rho_load_btw_turn_emp_lane=float(edges.ref_load.corr(edges.btw_turn_emp_lane, "spearman")),
                rho_load_onset=float(edges.ref_load.corr(onset.fillna(censor), "spearman")),
                partial_inv_lanes_onset_given_load=mm.partial_spearman(
                    1.0 / edges.lanes[onset.notna()], onset.dropna(), edges.ref_load[onset.notna()])[0],
                partial_inv_lanes_censored_given_load=mm.partial_spearman(
                    1.0 / edges.lanes, onset.fillna(censor), edges.ref_load)[0])

    tdir = Path(a.tables_dir); tdir.mkdir(parents=True, exist_ok=True)
    per_run.to_csv(tdir / "per-run.csv", index=False, float_format="%.6g")
    cols = ["flow_veh_h", "edgedata_flow_veh_h", "mean_speed_mps", "city_halting_share", "halted_share",
            "queued_lane_share", "queue_m_mean", "queue_m_p95", "queue_ratio_p95", "spill_edge_share",
            "spill_len_share", "spill_events_per_h", "spill_edges_ever", "spill_given_congested",
            "city_largest_cluster", "city_second_cluster", "city_congested_length_fraction"] + qo_cols
    mean_sd(per_run, cols).to_csv(tdir / "by-density.csv", float_format="%.6g")
    edges.to_csv(tdir / "edges-betweenness-onset.csv", float_format="%.6g")
    shares.T.to_csv(tdir / "edge-congested-share-by-density.csv", float_format="%.4g")
    corr.to_csv(tdir / "betweenness-onset-correlation.csv", index=False, float_format="%.6g")
    figures(per_run, onset, btw, corr, heat, a)

    chk = dict(
        vref_coverage=info["coverage"], n_runs=len(per_run), n_invalid_skipped=len(skipped),
        censor_at=censor, **conf,
        # against the sweep's columns, from the same criterion code: a check of the plumbing
        max_abs_G1_diff=float((per_run.G1_recomputed - per_run.city_largest_cluster).abs().max()),
        max_abs_phi_diff=float((per_run.phi_len_recomputed - per_run.city_congested_length_fraction).abs().max()),
        spill_events_equal=bool((per_run.spill_events == per_run.city_spillback_events).all()),
        max_abs_halting_diff=float((per_run.halted_share - per_run.city_halting_share).abs().max()),
        flow_ratio_edgedata_over_summary=[float(per_run.edgedata_flow_veh_h.div(per_run.flow_veh_h).min()),
                                          float(per_run.edgedata_flow_veh_h.div(per_run.flow_veh_h).max())],
        wall_s=round(time.time() - t0, 1))
    (tdir / "checks.json").write_text(json.dumps(chk, indent=1) + "\n")
    print(json.dumps(chk, indent=1))
    print(corr.to_string(index=False))


if __name__ == "__main__":
    main()
