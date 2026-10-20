"""SUMO edge <-> LTA road-stretch lookup, and helpers for polling LTA Traffic Speed Bands.

LTA DataMall "Traffic Speed Bands" serves one row per road stretch ("link", about 80 m,
one direction of travel) with a LinkID, a road name, a road category, start and end
points in WGS84 lon/lat and a 10 km/h speed band. Member E compares where the simulated
city network jams with where real roads are slow; that needs a table saying which LTA
links lie on which SUMO edges. This module builds it.

Two independent matchers run on every LTA link inside the net:
  A  endpoint snapping + directed shortest path: snap the start and the end point to
     nearby SUMO edges whose local heading agrees with the LTA start->end heading, then
     take the shortest drivable path between the snapped positions; reject the match if
     the path is much longer than the stretch. This is the primary matcher.
  B  buffer overlap + heading filter: keep every SUMO edge whose part inside a
     flat-ended buffer around the LTA start->end segment runs the same way, scored by
     overlap length / stretch length. This is the cross-check.
Road-name agreement is recorded as evidence, never used as a filter.

The table is many-to-many with two weights: frac_of_lta (share of the LTA link on that
edge) and frac_of_edge (share of the edge the LTA link covers). aggregate_to_edges()
turns per-link values into per-edge values with the frac_of_edge weights.

Ported from the role-C pilot (sandbox/c/task2/match_lta.py, 2026-10-20). Matching
settings come from [match] in configs/city/lta_lookup.toml; they are provisional
pending decision T2-D5.

Units: metres, degrees, seconds. Net coordinates are SUMO's metric x, y.
"""
import hashlib
import html
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

LINK_COLUMNS = ["LinkID", "RoadName", "RoadCategory", "StartLon", "StartLat", "EndLon", "EndLat"]
BAND_COLUMNS = ["SpeedBand", "MinimumSpeed", "MaximumSpeed"]
V4_URL = "https://datamall2.mytransport.sg/ltaodataservice/v4/TrafficSpeedBands"
PAGE_SIZE = 500  # DataMall returns at most 500 rows per call (API guide v6.10)

# v3 used letters A-F; v4 uses codes 1-6. ASSUMED: the letters map in order onto the
# codes (only A = 1 and C = 3 were cross-checked on shared LinkIDs, W1 evidence §2.4).
V3_LETTER_TO_CODE = {"A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "F": 6}

ABBR = {"AVE": "AVENUE", "AV": "AVENUE", "RD": "ROAD", "ST": "STREET", "DR": "DRIVE",
        "CRES": "CRESCENT", "PK": "PARK", "CL": "CLOSE", "LN": "LANE", "CTRL": "CENTRAL",
        "NTH": "NORTH", "STH": "SOUTH", "UPP": "UPPER", "BT": "BUKIT", "JLN": "JALAN",
        "LOR": "LORONG", "EXPWAY": "EXPRESSWAY", "PL": "PLACE", "TER": "TERRACE"}


def import_sumolib():
    """Import sumolib from $SUMO_HOME/tools (as traffic_project.runner does for traci)."""
    if "SUMO_HOME" not in os.environ:
        raise RuntimeError("SUMO_HOME is not set; see docs/guide.html, section 1")
    tools = os.path.join(os.environ["SUMO_HOME"], "tools")
    if tools not in sys.path:
        sys.path.append(tools)
    import sumolib
    return sumolib


@dataclass
class MatchParams:
    """Matcher settings, one per [match] key in the config (T2-D5)."""
    radius: float = 25.0      # endpoint snap radius, m
    max_angle: float = 45.0   # max heading difference between LTA link and SUMO edge, deg
    detour: float = 1.5       # A: max path length / stretch length
    buffer: float = 15.0      # B: half-width of the overlap buffer, m
    min_frac: float = 0.5     # B: keep an edge if overlap >= min_frac of the stretch (or of the edge)
    margin: float = 50.0      # skip links whose end points lie within this of the net boundary, m

    def label(self):
        return ";".join(f"{k}={v:g}" for k, v in asdict(self).items())


# ---------------------------------------------------------------- names and geometry

def norm_name(s):
    """Upper-case, strip punctuation and expand LTA abbreviations ("Ave 4" -> "AVENUE 4").
    XML entities are decoded first (sumolib returns "George&apos;s") and apostrophes are
    dropped, so "King George's Avenue" equals LTA's "KING GEORGES AVENUE"."""
    s = html.unescape(str(s or "")).replace("'", "").replace("\u2019", "")
    toks = re.sub(r"[^A-Z0-9 ]", " ", s.upper()).split()
    return " ".join(ABBR.get(t, t) for t in toks)


def name_agreement(a, b):
    """exact / partial (token Jaccard >= 0.5) / none / missing."""
    a, b = norm_name(a), norm_name(b)
    if not a or not b:
        return "missing"
    if a == b:
        return "exact"
    ta, tb = set(a.split()), set(b.split())
    return "partial" if len(ta & tb) / len(ta | tb) >= 0.5 else "none"


def category_code(cat):
    """LTA road category as an integer code 1-6 (v3 letters mapped in order, ASSUMED)."""
    s = str(cat).strip().upper()
    if s in V3_LETTER_TO_CODE:
        return V3_LETTER_TO_CODE[s]
    try:
        return int(float(s))
    except ValueError:
        return None


def ang_diff(a, b):
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)


def heading(p, q):
    return math.degrees(math.atan2(q[1] - p[1], q[0] - p[0]))


def local_heading(shape, offset):
    """Heading of the shape segment that contains `offset` (metres from the start)."""
    seen = 0.0
    for a, b in zip(shape[:-1], shape[1:]):
        seg = math.dist(a, b)
        if seen + seg >= offset or b is shape[-1]:
            return heading(a, b)
        seen += seg
    return heading(shape[-2], shape[-1])


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------- loading LTA data

def links_from_rows(rows):
    """DataFrame of LTA links (LINK_COLUMNS plus band columns if present) from API rows."""
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=LINK_COLUMNS)
    if "RoadCategory" not in df and "RoadCat" in df:
        df["RoadCategory"] = df["RoadCat"]
    df = df.drop_duplicates("LinkID").copy()
    df["LinkID"] = df["LinkID"].astype(str)
    for c in ["StartLon", "StartLat", "EndLon", "EndLat"]:
        df[c] = df[c].astype(float)
    keep = LINK_COLUMNS + [c for c in BAND_COLUMNS if c in df]
    return df[keep].reset_index(drop=True)


def load_links(path):
    """Read LTA links from a DataMall JSON response ({"value": [...]}; read as data only),
    or from a CSV or parquet file with LINK_COLUMNS (e.g. the poller's links file)."""
    path = Path(path)
    if path.suffix == ".parquet":
        return links_from_rows(pd.read_parquet(path).to_dict("records"))
    if path.suffix == ".csv":
        return links_from_rows(pd.read_csv(path, dtype={"LinkID": str}).to_dict("records"))
    j = json.loads(path.read_text(encoding="utf-8"))
    return links_from_rows(j.get("value") or j.get("Value") or [])


def twin_pairs(links, ndigits=6):
    """Pairs (id1, id2) of links whose end points are each other's swapped (a two-way road:
    one link per direction). Coordinates are compared rounded to `ndigits` degrees (~0.1 m)."""
    key = {}
    for r in links.itertuples(index=False):
        s = (round(r.StartLon, ndigits), round(r.StartLat, ndigits))
        e = (round(r.EndLon, ndigits), round(r.EndLat, ndigits))
        key.setdefault((s, e), []).append(r.LinkID)
    out = set()
    for (s, e), ids in key.items():
        for other in key.get((e, s), []):
            for i in ids:
                if i != other:
                    out.add(tuple(sorted((i, other))))
    return sorted(out)


# ---------------------------------------------------------------- matchers

def _snap_candidates(net, sumolib, pt, hdg, p, k=3):
    out = []
    for edge, _ in net.getNeighboringEdges(pt[0], pt[1], p.radius, includeJunctions=False):
        if not edge.allows("passenger"):
            continue
        shape = edge.getShape()
        off, d = sumolib.geomhelper.polygonOffsetAndDistanceToPoint(pt, shape, perpendicular=False)
        dh = ang_diff(local_heading(shape, off), hdg)
        if dh <= p.max_angle:
            out.append((d, edge, off, dh))
    out.sort(key=lambda t: t[0])
    return out[:k]


def method_a(net, sumolib, S, E, L, hdg, p):
    """Matcher A. Returns (best, reason): best = (score, pieces, snap_start, snap_end,
    path_len, max_heading_diff) with pieces = [(edge, overlap_m)], or None with the reason."""
    cs = _snap_candidates(net, sumolib, S, hdg, p)
    ce = _snap_candidates(net, sumolib, E, hdg, p)
    if not cs or not ce:
        return None, "no-candidate-" + ("start" if not cs else "end")
    best, reason = None, "no-path"
    for dS, eS, oS, hS in cs:
        for dE, eE, oE, hE in ce:
            if eS is eE and oS <= oE + 1.0:
                pieces = [(eS, max(0.0, oE - oS))]
            elif eS is eE:
                # end snapped upstream of start on the same edge: no forward path without a
                # loop (sumolib's getShortestPath(e, e) would return (e,) and fake one)
                reason = "backward-on-edge"
                continue
            else:
                path, _ = net.getShortestPath(eS, eE, vClass="passenger")
                if not path:
                    continue
                lenS = sumolib.geomhelper.polyLength(eS.getShape())
                pieces = [(eS, max(0.0, lenS - oS))]
                pieces += [(e, sumolib.geomhelper.polyLength(e.getShape())) for e in path[1:-1]]
                pieces += [(eE, oE)]
            plen = sum(q[1] for q in pieces)
            if plen > p.detour * L + 20.0:
                reason = "detour"
                continue
            score = dS + dE + abs(plen - L)
            if best is None or score < best[0]:
                best = (score, pieces, dS, dE, plen, max(hS, hE))
    return best, (None if best else reason)


def method_b(net, S, E, L, hdg, p):
    """Matcher B. Returns [(edge, overlap_m, heading_diff, hausdorff_m)]."""
    from shapely.geometry import LineString, Point
    seg = LineString([S, E])
    poly = seg.buffer(p.buffer, cap_style="flat")
    mid = ((S[0] + E[0]) / 2, (S[1] + E[1]) / 2)
    hits = []
    for edge, _ in net.getNeighboringEdges(mid[0], mid[1], L / 2 + p.buffer, includeJunctions=False):
        if not edge.allows("passenger"):
            continue
        line = LineString(edge.getShape())
        clip = line.intersection(poly)
        if clip.is_empty or clip.length < 1.0:
            continue
        geoms = [g for g in getattr(clip, "geoms", [clip]) if g.geom_type == "LineString"]
        if not geoms:
            continue
        # order the clipped pieces along the edge to get the travel heading inside the buffer
        p0 = min((line.project(Point(g.coords[0])), g.coords[0]) for g in geoms)
        p1 = max((line.project(Point(g.coords[-1])), g.coords[-1]) for g in geoms)
        if p1[0] - p0[0] < 1.0:
            continue
        dh = ang_diff(heading(p0[1], p1[1]), hdg)
        if dh > p.max_angle:
            continue
        hits.append((edge, sum(g.length for g in geoms), dh, max(seg.hausdorff_distance(g) for g in geoms)))
    return hits


def _side(sumolib, S, E, edge):
    """Which side of the LTA start->end vector the matched carriageway lies on, judged at
    the point of `edge` nearest the LTA start: left / right / on (within 0.5 m)."""
    shape = edge.getShape()
    off, _ = sumolib.geomhelper.polygonOffsetAndDistanceToPoint(S, shape, perpendicular=False)
    P = sumolib.geomhelper.positionAtShapeOffset(shape, off)
    L = math.dist(S, E)
    cross = ((E[0] - S[0]) * (P[1] - S[1]) - (E[1] - S[1]) * (P[0] - S[0])) / max(L, 1e-9)
    return "on" if abs(cross) < 0.5 else ("left" if cross > 0 else "right")


def match_links(net_path, links, p, lta_source="", lta_api_version=""):
    """Run matchers A and B on every LTA link inside the net (less p.margin).

    Returns (pairs, linktab, net_names):
      pairs    one row per (lta_link_id, sumo_edge_id, method) with weights and QA measures
      linktab  one row per LTA link considered: matched by A / B, agreement, qa_flag, side
      net_names  set of normalised road names present on the net's edges
    """
    sumolib = import_sumolib()
    net = sumolib.net.readNet(str(net_path), withInternal=False)
    xmin, ymin, xmax, ymax = net.getBoundary()
    net_names = {norm_name(e.getName()) for e in net.getEdges()} - {""}
    meta = dict(lta_source=lta_source, lta_api_version=lta_api_version,
                sumo_net=Path(net_path).name, sumo_net_sha256=sha256_file(net_path), params=p.label())
    pairs, rows = [], []
    for r in links.itertuples(index=False):
        S = net.convertLonLat2XY(r.StartLon, r.StartLat)
        E = net.convertLonLat2XY(r.EndLon, r.EndLat)
        if not all(xmin + p.margin <= q[0] <= xmax - p.margin and ymin + p.margin <= q[1] <= ymax - p.margin
                   for q in (S, E)):
            continue
        L, hdg = math.dist(S, E), heading(S, E)
        base = dict(lta_link_id=r.LinkID, lta_road_name=r.RoadName, lta_road_category=r.RoadCategory,
                    lta_category_code=category_code(r.RoadCategory),
                    lta_start_lon=r.StartLon, lta_start_lat=r.StartLat, lta_end_lon=r.EndLon,
                    lta_end_lat=r.EndLat, lta_len_m=round(L, 1), lta_heading_deg=round(hdg, 1))
        A, a_reason = method_a(net, sumolib, S, E, L, hdg, p) if L >= 1.0 else (None, "stub<1m")
        a_edges, a_names, side = [], set(), None
        if A:
            _, pieces, dS, dE, plen, hmax = A
            kept = [(e, ov) for e, ov in pieces if not (ov <= 0.5 and len(pieces) > 1)] or pieces[:1]
            tot = sum(ov for _, ov in kept)
            side = _side(sumolib, S, E, kept[0][0])
            for e, ov in kept:
                elen = sumolib.geomhelper.polyLength(e.getShape())
                nm = name_agreement(r.RoadName, e.getName())
                a_edges.append(e.getID())
                a_names.add(nm)
                pairs.append(dict(base, method="A_endpoint_path", sumo_edge_id=e.getID(),
                                  sumo_edge_name=e.getName(), sumo_edge_len_m=round(elen, 1),
                                  overlap_m=round(ov, 1), frac_of_lta=round(ov / max(tot, 1e-9), 3),
                                  frac_of_edge=round(min(1.0, ov / max(elen, 1e-9)), 3),
                                  heading_diff_deg=round(hmax, 1), snap_start_m=round(dS, 1),
                                  snap_end_m=round(dE, 1), hausdorff_m=None, kept=True, name_match=nm))
        b_edges = []
        for e, ov, dh, hd in (method_b(net, S, E, L, hdg, p) if L >= 1.0 else []):
            elen = sumolib.geomhelper.polyLength(e.getShape())
            frac = ov / max(L, 1e-9)
            keep = frac >= p.min_frac or ov / max(elen, 1e-9) >= 0.5
            if keep:
                b_edges.append(e.getID())
            pairs.append(dict(base, method="B_buffer_overlap", sumo_edge_id=e.getID(),
                              sumo_edge_name=e.getName(), sumo_edge_len_m=round(elen, 1),
                              overlap_m=round(ov, 1), frac_of_lta=round(frac, 3),
                              frac_of_edge=round(min(1.0, ov / max(elen, 1e-9)), 3),
                              heading_diff_deg=round(dh, 1), snap_start_m=None, snap_end_m=None,
                              hausdorff_m=round(hd, 1), kept=keep,
                              name_match=name_agreement(r.RoadName, e.getName())))
        sa, sb = set(a_edges), set(b_edges)
        in_net = norm_name(r.RoadName) in net_names
        if sa:
            qa = "stub<15m" if L < 15.0 else ""
        elif sb:
            qa = "b-only;a-" + a_reason
        else:
            qa = "absent-from-net" if not in_net else "in-net-missed;a-" + a_reason
        exact = "exact" in a_names
        conf = ("high" if sa and sa == sb and exact else
                "medium" if (sa or sb) and exact else "low" if (sa or sb) else "")
        rows.append(dict(base, a_matched=bool(sa), b_matched=bool(sb), n_edges_a=len(sa), n_edges_b=len(sb),
                         jaccard_ab=round(len(sa & sb) / len(sa | sb), 3) if sa | sb else None,
                         a_snap_start_m=round(A[2], 1) if A else None, a_snap_end_m=round(A[3], 1) if A else None,
                         a_path_len_m=round(A[4], 1) if A else None, a_name_exact=exact,
                         road_name_in_net=in_net, a_side=side, confidence=conf, qa_flag=qa,
                         a_edges=" ".join(sorted(sa)), b_edges=" ".join(sorted(sb))))
    pairs = pd.DataFrame(pairs)
    linktab = pd.DataFrame(rows)
    valid = lta_api_version == "v4" and "PROTOTYPE" not in lta_source.upper()
    for df in (pairs, linktab):
        for k, v in meta.items():
            df[k] = v
        df["valid_for_results"] = valid
    if not pairs.empty:  # confidence and qa_flag of the link on every pair row too
        pairs = pairs.merge(linktab[["lta_link_id", "confidence", "qa_flag"]], on="lta_link_id", how="left")
    return pairs, linktab, net_names


def missing_roads(linktab):
    """LTA road names with no SUMO edge of that (normalised) name: the roads the net drops."""
    if linktab.empty:
        return pd.DataFrame(columns=["lta_road_name", "lta_road_category", "n_links", "n_matched_a"])
    miss = linktab[~linktab.road_name_in_net]
    return (miss.groupby("lta_road_name")
            .agg(lta_road_category=("lta_road_category", lambda s: ",".join(sorted(set(map(str, s))))),
                 n_links=("lta_link_id", "size"), n_matched_a=("a_matched", "sum"))
            .reset_index().sort_values(["lta_road_category", "lta_road_name"]))


# ---------------------------------------------------------------- failure checks (proposal §2)

def run_checks(pairs, linktab, links, min_name_exact=0.90, min_arterial_coverage=0.85,
               arterial_codes=(2, 3), judge_coverage=False):
    """The proposal's four failure checks. Returns {check: dict(passed, detail, ...)}.
    passed is None when the check cannot be judged on this input."""
    out = {}
    considered = set(linktab.lta_link_id) if not linktab.empty else set()
    tw = [t for t in twin_pairs(links) if t[0] in considered and t[1] in considered]
    edges = {}
    if not pairs.empty:
        sel = pairs[(pairs.method == "A_endpoint_path") | pairs.kept.astype(bool)]
        for (lid, m), g in sel.groupby(["lta_link_id", "method"]):
            edges[(lid, m)] = set(g.sumo_edge_id)
    shared = [(a, b, m) for a, b in tw for m in ("A_endpoint_path", "B_buffer_overlap")
              if edges.get((a, m), set()) & edges.get((b, m), set())]
    n_both = sum(1 for a, b in tw if (a, "A_endpoint_path") in edges and (b, "A_endpoint_path") in edges)
    out["1_direction_twins_disjoint"] = dict(passed=not shared, n_twin_pairs=len(tw),
                                             n_twin_pairs_both_matched_a=n_both, shared=shared)
    am = linktab[linktab.a_matched] if not linktab.empty else linktab
    rate = float(am.a_name_exact.mean()) if len(am) else float("nan")
    out["2_name_exact_rate"] = dict(passed=bool(rate >= min_name_exact) if len(am) else None,
                                    rate=round(rate, 3), n=len(am), threshold=min_name_exact)
    twin_ids = {i for t in tw for i in t}
    sides = am[am.lta_link_id.isin(twin_ids)].a_side.value_counts().to_dict() if len(am) else {}
    left, right = sides.get("left", 0), sides.get("right", 0)
    out["3_side_left_majority_twins"] = dict(passed=(left > right) if left + right else None,
                                             left=left, right=right, on=sides.get("on", 0))
    art = linktab[linktab.lta_category_code.isin(arterial_codes)] if not linktab.empty else linktab
    cov = float(art.a_matched.mean()) if len(art) else float("nan")
    out["4_arterial_coverage"] = dict(passed=bool(cov >= min_arterial_coverage) if judge_coverage and len(art) else None,
                                      coverage=round(cov, 3), n=len(art), threshold=min_arterial_coverage,
                                      judged=bool(judge_coverage))
    return out


# ---------------------------------------------------------------- member E's aggregation

def aggregate_to_edges(lookup, link_values, value_col="value", method="A_endpoint_path"):
    """Per-SUMO-edge value from per-LTA-link values.

    lookup       pairs table from match_links (columns lta_link_id, sumo_edge_id, method,
                 frac_of_edge, kept)
    link_values  DataFrame with lta_link_id and value_col (e.g. peak/night relative speed)
    Returns one row per edge: value_col = mean of the link values weighted by frac_of_edge,
    coverage = sum of frac_of_edge capped at 1 (share of the edge with LTA data), n_links.
    """
    lk = lookup[(lookup.method == method) & lookup.kept.astype(bool)]
    lv = link_values[["lta_link_id", value_col]].astype({"lta_link_id": str})
    m = lk.astype({"lta_link_id": str}).merge(lv, on="lta_link_id").dropna(subset=[value_col])
    m = m[m.frac_of_edge > 0]
    if m.empty:
        return pd.DataFrame(columns=["sumo_edge_id", value_col, "coverage", "n_links"])
    m = m.assign(_wv=m.frac_of_edge * m[value_col])
    g = m.groupby("sumo_edge_id").agg(_wv=("_wv", "sum"), _w=("frac_of_edge", "sum"),
                                       n_links=("lta_link_id", "nunique")).reset_index()
    g[value_col] = g._wv / g._w
    g["coverage"] = g._w.clip(upper=1.0)
    return g[["sumo_edge_id", value_col, "coverage", "n_links"]]


# ---------------------------------------------------------------- polling helpers

def net_lonlat_box(net_path, margin_m):
    """(W, S, E, N) in degrees: the net's boundary grown by margin_m metres."""
    sumolib = import_sumolib()
    net = sumolib.net.readNet(str(net_path), withInternal=False)
    xmin, ymin, xmax, ymax = net.getBoundary()
    w, s = net.convertXY2LonLat(xmin - margin_m, ymin - margin_m)
    e, n = net.convertXY2LonLat(xmax + margin_m, ymax + margin_m)
    return (w, s, e, n)


def in_box(links, box):
    """Boolean Series: True if the link's start or end point lies inside box (W, S, E, N)."""
    w, s, e, n = box
    ins = links.StartLon.between(w, e) & links.StartLat.between(s, n)
    ine = links.EndLon.between(w, e) & links.EndLat.between(s, n)
    return ins | ine


def fetch_all_pages(key, url=V4_URL, page_size=PAGE_SIZE, pause_s=1.0, timeout_s=30.0,
                    max_pages=200, max_retries=4):
    """Fetch every page of a DataMall OData endpoint ($skip by page_size until a page has
    fewer rows). The key is sent only as the AccountKey header and never logged.
    Returns (rows, n_pages). Backs off exponentially on HTTP 429 and 5xx."""
    rows, page = [], 0
    while page < max_pages:
        req = urllib.request.Request(f"{url}?$skip={page * page_size}",
                                     headers={"AccountKey": key, "accept": "application/json"})
        for attempt in range(max_retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                    batch = json.loads(resp.read().decode("utf-8")).get("value", [])
                break
            except urllib.error.HTTPError as err:
                if (err.code == 429 or err.code >= 500) and attempt < max_retries:
                    time.sleep(pause_s * 2 ** (attempt + 1))
                    continue
                raise RuntimeError(f"HTTP {err.code} on page {page}") from None
        rows.extend(batch)
        page += 1
        if len(batch) < page_size:
            break
        time.sleep(pause_s)
    return rows, page
