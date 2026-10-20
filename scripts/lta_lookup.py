"""Build the SUMO edge <-> LTA road-stretch lookup for one net (task 2).

One config, one command (SUMO_HOME must be set):
    python scripts/lta_lookup.py --config configs/city/lta_lookup.toml [--figure PNG]

Reads [network] net and [lta] input, runs matchers A and B with the [match] settings
(traffic_project.lta) and writes to [output] out_dir:
    <prefix>_pairs.csv          one row per (LTA link, SUMO edge, method), weights frac_of_lta, frac_of_edge
    <prefix>_links.csv          one row per LTA link considered: matched?, confidence, qa_flag, side
    <prefix>_missing_roads.csv  LTA road names with no SUMO edge of that name (feedback to task 1)
    <prefix>_checks.json        the proposal's four failure checks, plus the counts printed below
    manifest.json               config, its hash, SUMO version and git commit (traffic_project.runner)
Exits 1 if failure check 1, 2 or 3 fails. With --figure, draws the net and the links.
"""
import argparse
import json
from pathlib import Path

from traffic_project import ROOT, config, runner
from traffic_project import lta


def draw(net_path, linktab, out_png):
    """Map: SUMO edges grey; LTA links matched by A green, B-only orange, unmatched red."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    sumolib = lta.import_sumolib()
    net = sumolib.net.readNet(str(net_path), withInternal=False)
    fig, ax = plt.subplots(figsize=(8, 8), dpi=110)
    for e in net.getEdges():
        xs, ys = zip(*e.getShape())
        ax.plot(xs, ys, color="#b0b0b0", lw=0.6, zorder=1)
    styles = [("matched by A", "#1b9e77", lambda r: r.a_matched),
              ("matched by B only", "#e6a700", lambda r: not r.a_matched and r.b_matched),
              ("unmatched, road absent from net", "#7570b3", lambda r: r.qa_flag == "absent-from-net"),
              ("unmatched, road in net", "#d62728", lambda r: not r.a_matched and not r.b_matched
               and r.qa_flag != "absent-from-net")]
    for label, colour, pick in styles:
        first = True
        for r in linktab.itertuples(index=False):
            if not pick(r):
                continue
            S = net.convertLonLat2XY(r.lta_start_lon, r.lta_start_lat)
            E = net.convertLonLat2XY(r.lta_end_lon, r.lta_end_lat)
            ax.annotate("", xy=E, xytext=S, zorder=3,
                        arrowprops=dict(arrowstyle="-|>", color=colour, lw=1.6, mutation_scale=9))
            if first:
                ax.plot([], [], color=colour, lw=2, label=f"{label} ({sum(pick(x) for x in linktab.itertuples())})")
                first = False
    ax.set_aspect("equal")
    ax.set_xlabel("x (m, SUMO net coordinates)")
    ax.set_ylabel("y (m)")
    ax.legend(loc="lower left", fontsize=8, title="LTA stretches (arrow = direction of travel)", title_fontsize=8)
    ax.set_title(f"LTA stretch -> SUMO edge lookup on {Path(net_path).name} (prototype input)", fontsize=10)
    fig.tight_layout()
    fig.savefig(out_png)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", required=True)
    ap.add_argument("--figure", help="also write a map PNG to this path")
    a = ap.parse_args()
    cfg = config.load(a.config)
    net_path = ROOT / cfg["network"]["net"]
    params = lta.MatchParams(**cfg["match"])
    links = lta.load_links(ROOT / cfg["lta"]["input"])
    out_dir = ROOT / cfg["output"]["out_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    run_id = out_dir.name
    runner.write_manifest(out_dir, run_id, cfg, dict(net=cfg["network"]["net"], lta_input=cfg["lta"]["input"],
                                                     lta_source=cfg["lta"]["source"], match=cfg["match"]))
    pairs, linktab, _ = lta.match_links(net_path, links, params, cfg["lta"]["source"], cfg["lta"]["api_version"])
    for lid, note in cfg.get("qa", {}).get("manual", {}).items():  # step 3a diagnoses, by LinkID
        hit = linktab.lta_link_id == str(lid)
        linktab.loc[hit, "qa_flag"] = linktab.loc[hit, "qa_flag"].fillna("") + ";manual:" + note
        if not pairs.empty:
            pairs.loc[pairs.lta_link_id == str(lid), "qa_flag"] = linktab.loc[hit, "qa_flag"].iloc[0] if hit.any() else None
    chk = cfg.get("checks", {})
    checks = lta.run_checks(pairs, linktab, links, chk.get("min_name_exact", 0.90),
                            chk.get("min_arterial_coverage", 0.85), tuple(chk.get("arterial_codes", (2, 3))),
                            judge_coverage=cfg["lta"]["api_version"] == "v4")
    prefix = out_dir / cfg["output"]["prefix"]
    pairs.to_csv(f"{prefix}_pairs.csv", index=False)
    linktab.to_csv(f"{prefix}_links.csv", index=False)
    miss = lta.missing_roads(linktab)
    miss.to_csv(f"{prefix}_missing_roads.csv", index=False)

    n = len(linktab)
    both = linktab.a_matched & linktab.b_matched
    counts = dict(n_lta_links_in_file=len(links), n_considered=n, matched_a=int(linktab.a_matched.sum()),
                  matched_b=int(linktab.b_matched.sum()), matched_both=int(both.sum()),
                  ab_identical=int((linktab.jaccard_ab == 1).sum()),
                  matched_none=int((~linktab.a_matched & ~linktab.b_matched).sum()),
                  absent_from_net=int((linktab.qa_flag == "absent-from-net").sum()),
                  n_missing_road_names=len(miss), snap_start_median_m=float(linktab.a_snap_start_m.median()),
                  snap_start_max_m=float(linktab.a_snap_start_m.max()),
                  matched_a_by_category=linktab.groupby("lta_road_category").a_matched
                  .agg(lambda s: f"{int(s.sum())}/{len(s)}").to_dict(),
                  confidence=linktab.confidence.value_counts().to_dict(),
                  qa_flag=linktab.qa_flag.value_counts().to_dict(),
                  sumo_net_sha256=linktab.sumo_net_sha256.iloc[0] if n else None,
                  valid_for_results=bool(linktab.valid_for_results.iloc[0]) if n else False)
    Path(f"{prefix}_checks.json").write_text(json.dumps(dict(counts=counts, checks=checks), indent=2, default=str))
    print(f"params {params.label()}  source={cfg['lta']['source']}")
    print(f"LTA links inside net: {n}  matched A: {counts['matched_a']}  B: {counts['matched_b']}  "
          f"both: {counts['matched_both']}  A-B identical edge sets: {counts['ab_identical']}")
    print(f"A by category: {counts['matched_a_by_category']}")
    print(f"A snap distance start m: median {counts['snap_start_median_m']:.1f}, max {counts['snap_start_max_m']:.1f}")
    for k, v in checks.items():
        print(f"check {k}: passed={v['passed']}  " + ", ".join(f"{a}={b}" for a, b in v.items() if a != "passed"))
    print(f"missing road names ({len(miss)}): {', '.join(miss.lta_road_name)}")
    print(f"wrote {prefix}_*.csv")
    if a.figure:
        draw(net_path, linktab, a.figure)
        print(f"wrote {a.figure}")
    if any(checks[k]["passed"] is False for k in list(checks)[:3]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
