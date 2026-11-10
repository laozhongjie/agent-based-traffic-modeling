"""Build the SUMO edge <-> LTA road-stretch lookup for one net (task 2).

One config, one command (SUMO_HOME must be set):
    python scripts/lta_lookup.py --config configs/city/lta_lookup.toml [--figure PNG] [--no-cleaning-cause]

Reads [network] net and [lta] input, runs matchers A and B with the [match] settings
(traffic_project.lta) and writes to [output] out_dir:
    <prefix>_pairs.csv          one row per (LTA link, SUMO edge, method), weights frac_of_lta, frac_of_edge
    <prefix>_links.csv          one row per LTA link of the input: matched?, cause if matcher A did not
                                place it, confidence, qa_flag, side
    <prefix>_missing_roads.csv  LTA road names with no SUMO edge of that name (feedback to task 1)
    <prefix>_checks.json        the proposal's four failure checks, the counts and the coverage tables
    README.md                   what the files hold, their columns, the coverage and how to rebuild them
    manifest.json               config, its hash, SUMO version and git commit (traffic_project.runner)
The cause "removed-by-cleaning" needs task 1's build run of the net ([causes] build_run_dir,
git-ignored); without it the script stops, unless --no-cleaning-cause is given, in which case
those links take a later cause. A rerun gives identical files apart from manifest.json.
Exits 1 if failure check 1, 2 or 3 fails. With --figure, draws the net and the links.
"""
import argparse
import json
import tomllib
from pathlib import Path

import pandas as pd

from traffic_project import ROOT, config, runner
from traffic_project import lta

CATEGORY = {1: "expressway", 2: "major arterial", 3: "arterial", 4: "minor arterial", 5: "small road",
            6: "slip road", 8: "short tunnel"}   # LTA DataMall API User Guide v6.10, section 2.19


def draw(net_path, full, out_png, title):
    """Map: SUMO edges grey; LTA links as arrows coloured by result and cause."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    sumolib = lta.import_sumolib()
    net = sumolib.net.readNet(str(net_path), withInternal=False)
    fig, ax = plt.subplots(figsize=(11, 8), dpi=110)
    for e in net.getEdges():
        xs, ys = zip(*e.getShape())
        ax.plot(xs, ys, color="#c8c8c8", lw=0.6, zorder=1)
    other = {"too-short", "no-edge-within-radius", "opposite-direction-only", "direction-test-failed",
             "path-too-long", "no-forward-path"}
    styles = [("placed by matcher A", "#1b9e77", lambda c: c == ""),
              ("matched by A on no length of an edge", "#a6d854", lambda c: c == "no-length-on-edge"),
              ("matched by B only", "#e6a700", lambda c: c == "matched-by-b-only"),
              ("road removed by task 1's cleaning", "#7570b3", lambda c: c == "removed-by-cleaning"),
              ("road not in the net", "#e7298a", lambda c: c == "road-not-in-net"),
              ("road in the net, not placed", "#d62728", lambda c: c in other),
              ("expressway, or outside the net", "#8c8c8c", lambda c: c in ("expressway", "outside-net"))]
    for label, colour, pick in styles:
        sel = full[full.cause.map(pick)]
        for r in sel.itertuples(index=False):
            S = net.convertLonLat2XY(r.lta_start_lon, r.lta_start_lat)
            E = net.convertLonLat2XY(r.lta_end_lon, r.lta_end_lat)
            ax.annotate("", xy=E, xytext=S, zorder=3,
                        arrowprops=dict(arrowstyle="-|>", color=colour, lw=1.0, mutation_scale=6))
        ax.plot([], [], color=colour, lw=2, label=f"{label} ({len(sel):,})")
    ax.set_aspect("equal")
    ax.set_xlabel("x (m, SUMO net coordinates)")
    ax.set_ylabel("y (m)")
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0), fontsize=8,
              title="LTA stretches (arrow = direction of travel)", title_fontsize=8)
    ax.set_title(title, fontsize=9)
    fig.tight_layout()
    fig.savefig(out_png)
    plt.close(fig)


def coverage(full, mask):
    """Per LTA category: stretches, those placed by matcher A on some edge length, and their
    straight-line length, inside mask."""
    d = full[mask].assign(placed=lambda x: x.cause == "", km=lambda x: x.lta_len_m / 1000.0)
    d = d.assign(placed_km=d.km.where(d.placed, 0.0))
    g = d.groupby("lta_category_code").agg(stretches=("placed", "size"), placed=("placed", "sum"),
                                           km=("km", "sum"), placed_km=("placed_km", "sum"))
    g.loc["all"] = g.sum()
    g["share"] = (g.placed / g.stretches).round(3)
    g["share_of_length"] = (g.placed_km / g.km).round(3)
    g[["km", "placed_km"]] = g[["km", "placed_km"]].round(2)
    g[["stretches", "placed"]] = g[["stretches", "placed"]].astype(int)
    return g


def cov_rows(g, arterial_codes):
    """Markdown rows of a coverage table, with the arterial group (main comparison) after its codes."""
    out = []
    art = g.loc[[c for c in g.index if c in arterial_codes]].sum()
    for code, r in g.iterrows():
        name = "all" if code == "all" else f"{code} {CATEGORY.get(code, '?')}"
        out.append(f"| {name} | {r.stretches:,.0f} | {r.placed:,.0f} | {r.share:.3f} | {r.km:.2f} | "
                   f"{r.placed_km:.2f} | {r.share_of_length:.3f} |")
        if code == max(arterial_codes):
            out.append(f"| 2 and 3, arterials | {art.stretches:,.0f} | {art.placed:,.0f} | "
                       f"{art.placed / art.stretches:.3f} | {art.km:.2f} | {art.placed_km:.2f} | "
                       f"{art.placed_km / art.km:.3f} |")
    return out


def readme(cfg, full, pairs, checks, counts, cov_tried, cov_box, cleaning):
    """The folder's README.md, from this run's numbers."""
    out = cfg["output"]["out_dir"]
    pre = cfg["output"]["prefix"]
    net = cfg["network"]["net"]
    m = cfg["match"]
    art = tuple(cfg.get("checks", {}).get("arterial_codes", (2, 3)))
    n = len(full)
    placed = int((full.cause == "").sum())
    tried = int(full.tried.sum())
    a_pairs = pairs[pairs.method == "A_endpoint_path"]
    by_cause = full.cause[full.cause != ""].value_counts()
    box = full.tried & full.in_study_box.fillna(False).astype(bool)
    c1, c2, c3 = (checks["1_direction_twins_disjoint"], checks["2_name_exact_rate"],
                  checks["3_side_left_majority_twins"])
    head = ("| LTA category | Stretches | Placed by A | Share | Length (km) | Placed length (km) | "
            "Share of length |")
    rule = "| --- | --- | --- | --- | --- | --- | --- |"
    L = [
        "# Lookup: which simulated road each LTA road stretch lies on",
        "",
        "This folder holds lookup v1, the table that says which road segment of the simulated city network (a "
        "SUMO edge, one direction of travel between two junctions) each LTA road stretch of the district lies on. "
        "With it, the speed bands in `../speedbands/` can be averaged onto the simulated roads, so that the "
        "most congested simulated roads can be set beside the slowest real ones. `scripts/lta_lookup.py` writes "
        "every file in this folder, this README included; change the script or its config, not the files (see "
        "\"Rebuild\").",
        "",
        f"- Network: `{net}`, sha256 `{counts['sumo_net_sha256']}`. The table holds this file's edge IDs only: "
        "a network with other edges, such as a closure or new-link variant, needs its own lookup.",
        f"- Stretches: the {n:,} rows of `{cfg['lta']['input']}` (LTA Traffic Speed Bands v4; source label "
        f"`{cfg['lta']['source']}`).",
        f"- Settings, agreed by the group on 2026-10-30: a stretch's end points snap to edges within "
        f"{m['radius']:g} m whose heading differs from the stretch's by at most {m['max_angle']:g} degrees; the "
        "table is many-to-many and records the share of each edge a stretch covers (`frac_of_edge`). Main "
        "comparison: LTA's major arterials and arterials (RoadCategory 2 and 3).",
        f"- Result: {tried:,} of the {n:,} stretches lie inside the network's area (its boundary less "
        f"{m['margin']:g} m). Matcher A placed {placed:,} of them ({placed / tried:.1%}) on some length of an edge; "
        f"it matched {int(by_cause.get('no-length-on-edge', 0)):,} more on no length of an edge, mostly short "
        "stretches inside a junction. Every stretch without a share of an edge has a `cause` (below).",
        "",
        "## Files",
        "",
        "| File | What it holds |",
        "| --- | --- |",
        f"| `{pre}_pairs.csv` | The lookup itself, many-to-many: one row per stretch, SUMO edge and matcher "
        f"({len(pairs):,} rows; {len(a_pairs):,} of them from matcher A, on {a_pairs.sumo_edge_id.nunique():,} "
        "edges). Use matcher A's rows (see \"Average speed bands onto edges\"). |",
        f"| `{pre}_links.csv` | One row per stretch, all {n:,}, in the order of `{cfg['lta']['input']}`: whether "
        "each matcher placed it, the edges, the road-name agreement and, for every stretch matcher A did not "
        "place, its `cause`. |",
        f"| `{pre}_missing_roads.csv` | LTA road names inside the network's area that no edge of the network "
        "carries, with their stretch counts (feedback to the network build). |",
        f"| `{pre}_checks.json` | The counts and coverage tables of this README and the four failure checks. |",
        "| `manifest.json` | The config, its hash, the SUMO version and the git commit of the build. |",
        "",
        "## How a stretch is matched",
        "",
        "LTA cuts the roads into short stretches (\"links\", keyed by `LinkID`), each one direction of travel with "
        "a start and an end point. Two matchers run on every stretch inside the network's area. **Matcher A**, the "
        f"result, snaps the start and the end point to edges within {m['radius']:g} m that point the same way "
        f"(within {m['max_angle']:g} degrees) and follows the shortest drivable path between them; it rejects a "
        f"path longer than {m['detour']:g} times the stretch plus 20 m. **Matcher B**, the cross-check, keeps "
        f"every same-direction edge that runs inside a band {m['buffer']:g} m either side of the stretch over at "
        f"least {m['min_frac']:g} of the stretch's length or of the edge's. Road names are compared as evidence, "
        "never used to choose an edge.",
        "",
        "## Average speed bands onto edges",
        "",
        "Take matcher A's rows. An edge's value is the mean of its stretches' values, each weighted by "
        "`frac_of_edge`, the share of the edge's length that the stretch covers; the sum of the weights, capped "
        "at 1, is the share of the edge with LTA data (`coverage`). `traffic_project.lta.aggregate_to_edges` "
        "does exactly this:",
        "",
        "```python",
        "import pandas as pd",
        "from traffic_project import lta",
        "",
        f'pairs = pd.read_csv("{out}/{pre}_pairs.csv", dtype={{"lta_link_id": str, "sumo_edge_id": str}})',
        'day = pd.read_csv("data/processed/lta/speedbands/2026-10-27.csv.gz", index_col="LinkID")',
        'col = next(c for c in day.columns if c.startswith("18:00"))   # the poll of the 18:00 slot, "18:00:17"',
        'band = day[col].replace(0, float("nan"))   # band 0 means no data',
        'values = pd.DataFrame({"lta_link_id": band.index.astype(str), "band": band.to_numpy()})',
        'edges = lta.aggregate_to_edges(pairs, values, value_col="band")',
        "# one row per SUMO edge: band (frac_of_edge-weighted mean), coverage (0-1), n_links",
        "```",
        "",
        "`aggregate_to_edges` keeps only matcher A's rows (`method == \"A_endpoint_path\"`); if you join by hand, "
        "filter on `method` too, or matcher B's rows are counted twice. A band is a 10 km/h class, not a speed "
        "(`../README.md`, \"Units\"), so compare where roads are slow, for example a stretch's evening band "
        "against its own night band, or ranks, rather than km/h. Stretches with a `cause` add nothing to an edge: "
        "they have no matcher A row, or (cause `no-length-on-edge`) only rows with `frac_of_edge` 0. Edges with no "
        "stretch get no row; edges with a low `coverage` rest on a small part of their length.",
        "",
        "## Why a stretch is not placed: `cause`",
        "",
        "Each stretch that matcher A did not place on some length of an edge takes the first cause that applies, "
        "in this order.",
        "",
        "| cause | Meaning | Stretches | In the study box |",
        "| --- | --- | --- | --- |",
    ]
    in_box = full[full.tried & full.in_study_box.fillna(False).astype(bool)].cause.value_counts()
    for key, meaning in lta.CAUSES.items():
        if key == "removed-by-cleaning" and not cleaning:
            meaning += " (not tested in this build: --no-cleaning-cause)"
        L.append(f"| `{key}` | {meaning} | {int(by_cause.get(key, 0)):,} | {int(in_box.get(key, 0)):,} |")
    L += [
        f"| (empty) | placed by matcher A on some length of an edge | {placed:,} | {int(in_box.get('', 0)):,} |",
        "",
        "The study box is the district task 1 studies (`study_box` in "
        f"`{cfg['network']['net_config']}`); \"in the study box\" counts the stretches inside the network's area "
        "with both end points in it. Outside the box, the network keeps a margin of roads cut at its edge. "
        "The network has no expressways or expressway slip roads, so the `expressway` stretches have no "
        "simulated counterpart; leave them out (`../README.md` says the same).",
        "",
        "## Coverage by road category",
        "",
        "Stretches inside the network's area (`tried` true): how many matcher A placed on some length of an "
        "edge (`cause` empty), by count and by straight-line length from start to end.",
        "",
        head, rule, *cov_rows(cov_tried, art),
        "",
        "The same inside the study box:",
        "",
        head, rule, *cov_rows(cov_box, art),
        "",
        f"Checks: matcher A's edge carries the stretch's own road name for {c2['rate']:.1%} of the "
        f"{c2['n']:,} stretches it matched. Of the {c1['n_twin_pairs']:,} two-way pairs (the two directions of one "
        f"road, end points swapped) inside the network's area, {c1['n_twin_pairs_both_matched_a']:,} have both "
        f"directions matched by matcher A, and {len(c1['shared'])} share an edge, so each direction lies on its "
        f"own carriageway; the carriageway lies left of LTA's direction of travel for {c3['left']} matched "
        f"two-way stretches and right for {c3['right']} ({c3['on']} on the line), as left-hand traffic requires. "
        "`" + pre + "_checks.json` holds the four failure checks.",
        "",
        "## Columns",
        "",
        f"`{pre}_links.csv` (one row per stretch):",
        "",
        "| Column | Meaning |",
        "| --- | --- |",
        "| `lta_link_id`, `lta_road_name`, `lta_road_category` | LTA's `LinkID`, `RoadName` and `RoadCategory` |",
        "| `lta_category_code` | RoadCategory as a number: 1 expressway, 2 major arterial, 3 arterial, 4 minor "
        "arterial, 5 small road, 6 slip road, 8 short tunnel |",
        "| `cause` | empty if matcher A placed the stretch on some length of an edge, else why not (table above) |",
        "| `tried` | true if both end points lie inside the network's area, so the matchers ran |",
        "| `in_study_box` | true if both end points lie inside the study box |",
        "| `a_matched`, `b_matched` | matched by matcher A (the result; true also for cause `no-length-on-edge`) / "
        "by matcher B (the cross-check) |",
        "| `lta_start_lon`, `lta_start_lat`, `lta_end_lon`, `lta_end_lat` | end points, degrees (WGS84) |",
        "| `lta_len_m`, `lta_heading_deg` | straight start-to-end length (m) and heading (degrees, "
        "anticlockwise from east, in the network's x, y) |",
        "| `n_edges_a`, `n_edges_b`, `a_edges`, `b_edges` | how many and which edges each matcher placed it on "
        "(IDs separated by spaces) |",
        "| `jaccard_ab` | overlap of the two matchers' edge sets, 0-1 |",
        "| `a_snap_start_m`, `a_snap_end_m`, `a_path_len_m` | matcher A: distance from each end point to its edge "
        "(m), and length of the matched path (m) |",
        "| `a_name_exact` | true if one of matcher A's edges carries the stretch's own road name |",
        "| `road_name_in_net` | true if some edge of the network carries the stretch's road name |",
        "| `a_side` | which side of LTA's start-to-end line the matched carriageway lies: left, right or on |",
        "| `confidence` | high: both matchers give the same edges and one of matcher A's edges carries the road "
        "name; medium: that name agrees but the matchers' edges differ; low: matched by either matcher without "
        "that name; empty: matched by neither |",
        "| `qa_flag`, `a_reason` | the matcher's own notes (`stub<15m`: matched, but under 15 m; `b-only;a-...`, "
        "`in-net-missed;a-...`, `absent-from-net`: not matched by A) and matcher A's reason for no match "
        "(`no-candidate-start` or `-end`, `detour`, `no-path`, `backward-on-edge`, `stub<1m`) |",
        "| `lta_source`, `lta_api_version`, `sumo_net`, `sumo_net_sha256`, `params`, `valid_for_results` | "
        "provenance: the LTA input, the network file and its sha256, the settings, and whether the table may "
        "be used for results (true only for v4 input not labelled a prototype) |",
        "",
        f"`{pre}_pairs.csv` (one row per stretch, edge and matcher) repeats the stretch's LTA columns, "
        "`confidence`, `qa_flag` and the provenance, and adds:",
        "",
        "| Column | Meaning |",
        "| --- | --- |",
        "| `method` | `A_endpoint_path` (matcher A, the result) or `B_buffer_overlap` (matcher B) |",
        "| `sumo_edge_id`, `sumo_edge_name`, `sumo_edge_len_m` | the edge, its road name and length (m) |",
        "| `overlap_m` | length of the stretch's path on this edge (m) |",
        "| `frac_of_edge` | share of the edge's length the stretch covers, 0-1: the weight for averaging onto "
        "edges |",
        "| `frac_of_lta` | share of the stretch on this edge, 0-1 (matcher A: sums to 1 over a stretch's rows, "
        "within rounding, and to 0 for cause `no-length-on-edge`; matcher B: overlap over the straight length) |",
        "| `heading_diff_deg` | heading difference between stretch and edge (degrees) |",
        "| `snap_start_m`, `snap_end_m` | matcher A: end-point distances to the edges (m) |",
        "| `hausdorff_m` | matcher B: largest distance between the stretch and the edge's piece (m) |",
        "| `kept` | matcher B: true if the overlap is large enough to count; always true for matcher A |",
        "| `name_match` | road-name agreement of stretch and edge: exact, partial, none or missing |",
        "",
        "## Rebuild",
        "",
        "From the repository root, with `SUMO_HOME` set:",
        "",
        "```bash",
        f"python scripts/lta_lookup.py --config {cfg['_path']}",
        "```",
        "",
        f"It reads `{net}` and `{cfg['lta']['input']}` (both in git) and, for the cause `removed-by-cleaning`, "
        f"task 1's build run of the network, `{cfg['causes']['build_run_dir']}/stage1.net.xml` (the network "
        "before cleaning) and `scc_edges.txt` (the edges cleaning kept), which are git-ignored and exist on C's "
        "machine. Without them, add `--no-cleaning-cause`: those stretches then take a later cause. A rerun "
        "gives identical files apart from `manifest.json`, which records the time and the git commit.",
        "",
        "## Source and licence",
        "",
        "Contains information from Traffic Speed Bands (v4) from LTA DataMall, which is made available under the "
        "terms of the Singapore Open Data Licence version 1.0 (https://data.gov.sg/open-data-licence).",
        "",
    ]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", required=True)
    ap.add_argument("--figure", help="also write a map PNG to this path")
    ap.add_argument("--no-cleaning-cause", action="store_true",
                    help="do not test the cause removed-by-cleaning (task 1's build run is missing)")
    a = ap.parse_args()
    cfg = config.load(a.config)
    net_path = ROOT / cfg["network"]["net"]
    params = lta.MatchParams(**cfg["match"])
    links = lta.load_links(ROOT / cfg["lta"]["input"])
    study_box = None
    if cfg["network"].get("net_config"):
        study_box = tuple(tomllib.loads((ROOT / cfg["network"]["net_config"]).read_text())["network"]["study_box"])
    stage1 = kept = None
    if not a.no_cleaning_cause:
        run = ROOT / cfg["causes"]["build_run_dir"]
        stage1, kept_file = run / "stage1.net.xml", run / "scc_edges.txt"
        if not (stage1.is_file() and kept_file.is_file()):
            raise SystemExit(f"{run.relative_to(ROOT)}: stage1.net.xml or scc_edges.txt missing (task 1's build "
                             "run, git-ignored); rerun with --no-cleaning-cause to skip that cause")
        kept = kept_file.read_text().split()
    out_dir = ROOT / cfg["output"]["out_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    run_id = out_dir.name
    runner.write_manifest(out_dir, run_id, cfg, dict(net=cfg["network"]["net"], lta_input=cfg["lta"]["input"],
                                                     lta_source=cfg["lta"]["source"], match=cfg["match"],
                                                     cleaning_cause=not a.no_cleaning_cause))
    pairs, linktab, _ = lta.match_links(net_path, links, params, cfg["lta"]["source"], cfg["lta"]["api_version"])
    for lid, note in cfg.get("qa", {}).get("manual", {}).items():  # causes found by hand, by LinkID
        hit = linktab.lta_link_id == str(lid)
        linktab.loc[hit, "qa_flag"] = linktab.loc[hit, "qa_flag"].fillna("") + ";manual:" + note
        if not pairs.empty:
            pairs.loc[pairs.lta_link_id == str(lid), "qa_flag"] = linktab.loc[hit, "qa_flag"].iloc[0] if hit.any() else None
    full = lta.assign_causes(net_path, links, linktab, pairs, params, stage1, kept, study_box)
    xway = set(full.lta_link_id[full.cause == "expressway"])
    n_xway_pairs = int(pairs.lta_link_id.isin(xway).sum()) if not pairs.empty else 0
    if n_xway_pairs:   # the network has no expressways: a pair of an expressway stretch is a surface road
        pairs = pairs[~pairs.lta_link_id.isin(xway)].reset_index(drop=True)
    chk = cfg.get("checks", {})
    art = tuple(chk.get("arterial_codes", (2, 3)))
    checks = lta.run_checks(pairs, linktab, links, chk.get("min_name_exact", 0.90),
                            chk.get("min_arterial_coverage", 0.85), art,
                            judge_coverage=cfg["lta"]["api_version"] == "v4")
    prefix = out_dir / cfg["output"]["prefix"]
    pairs.to_csv(f"{prefix}_pairs.csv", index=False, lineterminator="\n")
    full.to_csv(f"{prefix}_links.csv", index=False, lineterminator="\n")
    miss = lta.missing_roads(linktab)
    miss.to_csv(f"{prefix}_missing_roads.csv", index=False, lineterminator="\n")

    n = len(linktab)
    both = linktab.a_matched & linktab.b_matched
    in_box = full.tried & full.in_study_box.fillna(False).astype(bool)
    cov_tried, cov_box = coverage(full, full.tried), coverage(full, in_box)
    counts = dict(n_lta_links_in_file=len(links), n_considered=n, matched_a=int(linktab.a_matched.sum()),
                  matched_b=int(linktab.b_matched.sum()), matched_both=int(both.sum()),
                  ab_identical=int((linktab.jaccard_ab == 1).sum()),
                  matched_none=int((~linktab.a_matched & ~linktab.b_matched).sum()),
                  absent_from_net=int((linktab.qa_flag == "absent-from-net").sum()),
                  n_missing_road_names=len(miss), snap_start_median_m=float(linktab.a_snap_start_m.median()),
                  snap_start_max_m=float(linktab.a_snap_start_m.max()),
                  matched_a_by_category=linktab.groupby("lta_category_code").a_matched
                  .agg(lambda s: f"{int(s.sum())}/{len(s)}").to_dict(),
                  cause=full.cause.replace("", "(placed by A)").value_counts().to_dict(),
                  cause_in_study_box=full.cause[in_box].replace("", "(placed by A)").value_counts().to_dict(),
                  cleaning_cause_tested=not a.no_cleaning_cause, expressway_pairs_dropped=n_xway_pairs,
                  confidence=linktab.confidence.value_counts().to_dict(),
                  qa_flag=linktab.qa_flag.value_counts().to_dict(),
                  sumo_net_sha256=linktab.sumo_net_sha256.iloc[0] if n else None,
                  valid_for_results=bool(linktab.valid_for_results.iloc[0]) if n else False)
    tables = {"inside_net_area": cov_tried.reset_index().astype({"lta_category_code": str}).to_dict("records"),
              "inside_study_box": cov_box.reset_index().astype({"lta_category_code": str}).to_dict("records")}
    Path(f"{prefix}_checks.json").write_text(json.dumps(dict(counts=counts, coverage=tables, checks=checks),
                                                        indent=2, default=str) + "\n")
    (out_dir / "README.md").write_text(readme(cfg, full, pairs, checks, counts, cov_tried, cov_box,
                                              not a.no_cleaning_cause))
    print(f"params {params.label()}  source={cfg['lta']['source']}")
    print(f"LTA links in file: {len(links)}  inside the net's area: {n}  matched A: {counts['matched_a']}  "
          f"B: {counts['matched_b']}  both: {counts['matched_both']}  A-B identical edge sets: {counts['ab_identical']}")
    print(f"A by category: {counts['matched_a_by_category']}")
    print(f"A snap distance start m: median {counts['snap_start_median_m']:.1f}, max {counts['snap_start_max_m']:.1f}")
    print(f"causes: {counts['cause']}")
    print(f"coverage inside the net's area:\n{cov_tried.to_string()}")
    print(f"coverage inside the study box:\n{cov_box.to_string()}")
    for k, v in checks.items():
        print(f"check {k}: passed={v['passed']}  " + ", ".join(f"{a}={b}" for a, b in v.items() if a != "passed"))
    print(f"missing road names ({len(miss)}): {', '.join(miss.lta_road_name)}")
    print(f"wrote {prefix}_*.csv, {prefix}_checks.json, {out_dir / 'README.md'}")
    if a.figure:
        draw(net_path, full, a.figure, f"LTA stretch -> SUMO edge lookup v1 on {Path(net_path).name} "
                                       f"(sha256 {counts['sumo_net_sha256'][:8]})")
        print(f"wrote {a.figure}")
    if any(checks[k]["passed"] is False for k in list(checks)[:3]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
