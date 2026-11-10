# Lookup: which simulated road each LTA road stretch lies on

This folder holds lookup v1, the table that says which road segment of the simulated city network (a SUMO edge, one direction of travel between two junctions) each LTA road stretch of the district lies on. With it, the speed bands in `../speedbands/` can be averaged onto the simulated roads, so that the most congested simulated roads can be set beside the slowest real ones. `scripts/lta_lookup.py` writes every file in this folder, this README included; change the script or its config, not the files (see "Rebuild").

- Network: `scenarios/city/bugis_all.net.xml`, sha256 `0fa042dabe60a2fbc2335d553c9f6bd531772dc37ee945d7ddaeb09a77a6bdca`. The table holds this file's edge IDs only: a network with other edges, such as a closure or new-link variant, needs its own lookup.
- Stretches: the 4,778 rows of `data/processed/lta/district_links.csv` (LTA Traffic Speed Bands v4; source label `v4-district-links-2026-10-20`).
- Settings, agreed by the group on 2026-10-30: a stretch's end points snap to edges within 25 m whose heading differs from the stretch's by at most 45 degrees; the table is many-to-many and records the share of each edge a stretch covers (`frac_of_edge`). Main comparison: LTA's major arterials and arterials (RoadCategory 2 and 3).
- Result: 3,742 of the 4,778 stretches lie inside the network's area (its boundary less 50 m). Matcher A placed 2,033 of them (54.3%) on some length of an edge; it matched 390 more on no length of an edge, mostly short stretches inside a junction. Every stretch without a share of an edge has a `cause` (below).

## Files

| File | What it holds |
| --- | --- |
| `bugis_all_pairs.csv` | The lookup itself, many-to-many: one row per stretch, SUMO edge and matcher (5,047 rows; 2,678 of them from matcher A, on 1,046 edges). Use matcher A's rows (see "Average speed bands onto edges"). |
| `bugis_all_links.csv` | One row per stretch, all 4,778, in the order of `data/processed/lta/district_links.csv`: whether each matcher placed it, the edges, the road-name agreement and, for every stretch matcher A did not place, its `cause`. |
| `bugis_all_missing_roads.csv` | LTA road names inside the network's area that no edge of the network carries, with their stretch counts (feedback to the network build). |
| `bugis_all_checks.json` | The counts and coverage tables of this README and the four failure checks. |
| `manifest.json` | The config, its hash, the SUMO version and the git commit of the build. |

## How a stretch is matched

LTA cuts the roads into short stretches ("links", keyed by `LinkID`), each one direction of travel with a start and an end point. Two matchers run on every stretch inside the network's area. **Matcher A**, the result, snaps the start and the end point to edges within 25 m that point the same way (within 45 degrees) and follows the shortest drivable path between them; it rejects a path longer than 1.5 times the stretch plus 20 m. **Matcher B**, the cross-check, keeps every same-direction edge that runs inside a band 15 m either side of the stretch over at least 0.5 of the stretch's length or of the edge's. Road names are compared as evidence, never used to choose an edge.

## Average speed bands onto edges

Take matcher A's rows. An edge's value is the mean of its stretches' values, each weighted by `frac_of_edge`, the share of the edge's length that the stretch covers; the sum of the weights, capped at 1, is the share of the edge with LTA data (`coverage`). `traffic_project.lta.aggregate_to_edges` does exactly this:

```python
import pandas as pd
from traffic_project import lta

pairs = pd.read_csv("data/processed/lta/lookup/bugis_all_pairs.csv", dtype={"lta_link_id": str, "sumo_edge_id": str})
day = pd.read_csv("data/processed/lta/speedbands/2026-10-27.csv.gz", index_col="LinkID")
col = next(c for c in day.columns if c.startswith("18:00"))   # the poll of the 18:00 slot, "18:00:17"
band = day[col].replace(0, float("nan"))   # band 0 means no data
values = pd.DataFrame({"lta_link_id": band.index.astype(str), "band": band.to_numpy()})
edges = lta.aggregate_to_edges(pairs, values, value_col="band")
# one row per SUMO edge: band (frac_of_edge-weighted mean), coverage (0-1), n_links
```

`aggregate_to_edges` keeps only matcher A's rows (`method == "A_endpoint_path"`); if you join by hand, filter on `method` too, or matcher B's rows are counted twice. A band is a 10 km/h class, not a speed (`../README.md`, "Units"), so compare where roads are slow, for example a stretch's evening band against its own night band, or ranks, rather than km/h. Stretches with a `cause` add nothing to an edge: they have no matcher A row, or (cause `no-length-on-edge`) only rows with `frac_of_edge` 0. Edges with no stretch get no row; edges with a low `coverage` rest on a small part of their length.

## Why a stretch is not placed: `cause`

Each stretch that matcher A did not place on some length of an edge takes the first cause that applies, in this order.

| cause | Meaning | Stretches | In the study box |
| --- | --- | --- | --- |
| `outside-net` | an end point lies outside the network's area (its boundary less the margin set in [match]), so the matchers did not run | 1,036 | 0 |
| `expressway` | an expressway stretch (RoadCategory 1) or a slip road named after an expressway: the network has no expressways, so such a stretch is never placed, even if a matcher found a surface road below it | 17 | 14 |
| `no-length-on-edge` | matcher A placed it, but on no length of any edge (frac_of_edge 0): both end points snap to the same point of one edge, usually its end, so the stretch lies inside a junction and adds nothing to an edge's average | 390 | 366 |
| `matched-by-b-only` | matcher A found no edge path, but matcher B (the cross-check) found edges: the stretch's pairs are B rows only | 32 | 29 |
| `removed-by-cleaning` | matched again on task 1's network before its cleaning, it lands on an edge that the strong-component pass removed | 394 | 266 |
| `road-not-in-net` | no edge of the network carries the stretch's road name | 230 | 188 |
| `too-short` | start and end lie under 1 m apart, so the stretch has no heading to test | 0 | 0 |
| `no-edge-within-radius` | no drivable edge lies within the snap radius of its start (or end) point | 216 | 199 |
| `opposite-direction-only` | every drivable edge within the snap radius runs against the stretch (more than 135 degrees off): the network lacks this direction there | 10 | 10 |
| `direction-test-failed` | drivable edges lie within the snap radius, but none within the heading tolerance | 417 | 400 |
| `path-too-long` | both ends snap, but the drivable path between them exceeds the detour limit | 3 | 3 |
| `no-forward-path` | both ends snap, but no forward drivable path joins them | 0 | 0 |
| (empty) | placed by matcher A on some length of an edge | 2,033 | 1,893 |

The study box is the district task 1 studies (`study_box` in `configs/city/bugis_all.toml`); "in the study box" counts the stretches inside the network's area with both end points in it. Outside the box, the network keeps a margin of roads cut at its edge. The network has no expressways or expressway slip roads, so the `expressway` stretches have no simulated counterpart; leave them out (`../README.md` says the same).

## Coverage by road category

Stretches inside the network's area (`tried` true): how many matcher A placed on some length of an edge (`cause` empty), by count and by straight-line length from start to end.

| LTA category | Stretches | Placed by A | Share | Length (km) | Placed length (km) | Share of length |
| --- | --- | --- | --- | --- | --- | --- |
| 1 expressway | 10 | 0 | 0.000 | 1.65 | 0.00 | 0.000 |
| 2 major arterial | 973 | 670 | 0.689 | 42.64 | 33.21 | 0.779 |
| 3 arterial | 330 | 182 | 0.552 | 11.99 | 7.94 | 0.662 |
| 2 and 3, arterials | 1,303 | 852 | 0.654 | 54.63 | 41.15 | 0.753 |
| 4 minor arterial | 1,169 | 508 | 0.435 | 40.20 | 23.45 | 0.583 |
| 5 small road | 1,189 | 641 | 0.539 | 34.74 | 24.42 | 0.703 |
| 6 slip road | 67 | 32 | 0.478 | 4.62 | 1.76 | 0.380 |
| 8 short tunnel | 4 | 0 | 0.000 | 0.36 | 0.00 | 0.000 |
| all | 3,742 | 2,033 | 0.543 | 136.19 | 90.77 | 0.667 |

The same inside the study box:

| LTA category | Stretches | Placed by A | Share | Length (km) | Placed length (km) | Share of length |
| --- | --- | --- | --- | --- | --- | --- |
| 1 expressway | 8 | 0 | 0.000 | 1.31 | 0.00 | 0.000 |
| 2 major arterial | 868 | 628 | 0.724 | 37.55 | 30.36 | 0.808 |
| 3 arterial | 306 | 172 | 0.562 | 10.81 | 7.49 | 0.692 |
| 2 and 3, arterials | 1,174 | 800 | 0.681 | 48.36 | 37.85 | 0.783 |
| 4 minor arterial | 1,065 | 482 | 0.453 | 35.90 | 22.13 | 0.617 |
| 5 small road | 1,056 | 582 | 0.551 | 30.87 | 22.11 | 0.716 |
| 6 slip road | 61 | 29 | 0.475 | 4.12 | 1.60 | 0.389 |
| 8 short tunnel | 4 | 0 | 0.000 | 0.36 | 0.00 | 0.000 |
| all | 3,368 | 1,893 | 0.562 | 120.93 | 83.69 | 0.692 |

Checks: matcher A's edge carries the stretch's own road name for 94.0% of the 2,423 stretches it matched. Of the 216 two-way pairs (the two directions of one road, end points swapped) inside the network's area, 53 have both directions matched by matcher A, and 0 share an edge, so each direction lies on its own carriageway; the carriageway lies left of LTA's direction of travel for 81 matched two-way stretches and right for 34 (7 on the line), as left-hand traffic requires. `bugis_all_checks.json` holds the four failure checks.

## Columns

`bugis_all_links.csv` (one row per stretch):

| Column | Meaning |
| --- | --- |
| `lta_link_id`, `lta_road_name`, `lta_road_category` | LTA's `LinkID`, `RoadName` and `RoadCategory` |
| `lta_category_code` | RoadCategory as a number: 1 expressway, 2 major arterial, 3 arterial, 4 minor arterial, 5 small road, 6 slip road, 8 short tunnel |
| `cause` | empty if matcher A placed the stretch on some length of an edge, else why not (table above) |
| `tried` | true if both end points lie inside the network's area, so the matchers ran |
| `in_study_box` | true if both end points lie inside the study box |
| `a_matched`, `b_matched` | matched by matcher A (the result; true also for cause `no-length-on-edge`) / by matcher B (the cross-check) |
| `lta_start_lon`, `lta_start_lat`, `lta_end_lon`, `lta_end_lat` | end points, degrees (WGS84) |
| `lta_len_m`, `lta_heading_deg` | straight start-to-end length (m) and heading (degrees, anticlockwise from east, in the network's x, y) |
| `n_edges_a`, `n_edges_b`, `a_edges`, `b_edges` | how many and which edges each matcher placed it on (IDs separated by spaces) |
| `jaccard_ab` | overlap of the two matchers' edge sets, 0-1 |
| `a_snap_start_m`, `a_snap_end_m`, `a_path_len_m` | matcher A: distance from each end point to its edge (m), and length of the matched path (m) |
| `a_name_exact` | true if one of matcher A's edges carries the stretch's own road name |
| `road_name_in_net` | true if some edge of the network carries the stretch's road name |
| `a_side` | which side of LTA's start-to-end line the matched carriageway lies: left, right or on |
| `confidence` | high: both matchers give the same edges and one of matcher A's edges carries the road name; medium: that name agrees but the matchers' edges differ; low: matched by either matcher without that name; empty: matched by neither |
| `qa_flag`, `a_reason` | the matcher's own notes (`stub<15m`: matched, but under 15 m; `b-only;a-...`, `in-net-missed;a-...`, `absent-from-net`: not matched by A) and matcher A's reason for no match (`no-candidate-start` or `-end`, `detour`, `no-path`, `backward-on-edge`, `stub<1m`) |
| `lta_source`, `lta_api_version`, `sumo_net`, `sumo_net_sha256`, `params`, `valid_for_results` | provenance: the LTA input, the network file and its sha256, the settings, and whether the table may be used for results (true only for v4 input not labelled a prototype) |

`bugis_all_pairs.csv` (one row per stretch, edge and matcher) repeats the stretch's LTA columns, `confidence`, `qa_flag` and the provenance, and adds:

| Column | Meaning |
| --- | --- |
| `method` | `A_endpoint_path` (matcher A, the result) or `B_buffer_overlap` (matcher B) |
| `sumo_edge_id`, `sumo_edge_name`, `sumo_edge_len_m` | the edge, its road name and length (m) |
| `overlap_m` | length of the stretch's path on this edge (m) |
| `frac_of_edge` | share of the edge's length the stretch covers, 0-1: the weight for averaging onto edges |
| `frac_of_lta` | share of the stretch on this edge, 0-1 (matcher A: sums to 1 over a stretch's rows, within rounding, and to 0 for cause `no-length-on-edge`; matcher B: overlap over the straight length) |
| `heading_diff_deg` | heading difference between stretch and edge (degrees) |
| `snap_start_m`, `snap_end_m` | matcher A: end-point distances to the edges (m) |
| `hausdorff_m` | matcher B: largest distance between the stretch and the edge's piece (m) |
| `kept` | matcher B: true if the overlap is large enough to count; always true for matcher A |
| `name_match` | road-name agreement of stretch and edge: exact, partial, none or missing |

## Rebuild

From the repository root, with `SUMO_HOME` set:

```bash
python scripts/lta_lookup.py --config configs/city/lta_lookup.toml
```

It reads `scenarios/city/bugis_all.net.xml` and `data/processed/lta/district_links.csv` (both in git) and, for the cause `removed-by-cleaning`, task 1's build run of the network, `runs/city-build-bugis_all-20261029-164348/stage1.net.xml` (the network before cleaning) and `scc_edges.txt` (the edges cleaning kept), which are git-ignored and exist on C's machine. Without them, add `--no-cleaning-cause`: those stretches then take a later cause. A rerun gives identical files apart from `manifest.json`, which records the time and the git commit.

## Source and licence

Contains information from Traffic Speed Bands (v4) from LTA DataMall, which is made available under the terms of the Singapore Open Data Licence version 1.0 (https://data.gov.sg/open-data-licence).
