"""Extract the city district's LTA speed bands into one compact file per Singapore day.

Usage (from the repository root; needs the git-ignored raw polls, which only C's machine has):
    python scripts/lta_district_extract.py --config configs/city/lta_district_extract.toml
    python scripts/lta_district_extract.py --config configs/city/lta_district_extract.toml --through 2026-10-31

C's poller (scripts/lta_poll.py, not yet on main) stores every 5-min poll of LTA DataMall
Traffic Speed Bands (v4), island-wide, in [input] raw_dir. This script keeps the links of the
city district and writes, under [output] out_dir (member E's data):
    district_links.csv               one row per district link: LinkID, RoadName, RoadCategory,
                                     StartLon, StartLat, EndLon, EndLat (sorted by LinkID)
    speedbands/<YYYY-MM-DD>.csv.gz   one file per Singapore calendar day: column LinkID (rows in
                                     district_links order), then one column per complete poll of
                                     that day, headed by its Singapore start time HH:MM:SS; cells
                                     are the speed band, empty when the link is missing from that poll
    README.md                        what the files hold, the box, the days and the gaps; written
                                     by this script (change the text here, then rerun)

The district is the net's convBoundary grown by [box] margin_m on each side and taken back to
lon/lat through the net's <location> (netOffset, projParameter); a link is kept if its start or
its end point lies inside. Files named *_truncated.parquet are incomplete polls and are left out.
Only whole days are written: up to --through (default yesterday, Singapore time), never today,
which the poller is still filling. The gzip header holds no time stamp and no file name, so a
rerun on the same raw files gives identical bytes. The script stops, writing nothing more, when
a poll's stored time disagrees with its file name, when a link appears twice in one poll, or when
one speed band arrives with two different speed ranges.
"""
import argparse
import gzip
import math
import os
import re
import xml.etree.ElementTree as ET
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from traffic_project import ROOT, config

SGT = timezone(timedelta(hours=8))   # Singapore time: the poller names its folders and files by it
LINK_COLUMNS = ["LinkID", "RoadName", "RoadCategory", "StartLon", "StartLat", "EndLon", "EndLat"]
POLL_COLUMNS = ["poll_time_utc", "LinkID", "SpeedBand", "MinimumSpeed", "MaximumSpeed"]
POLL_NAME = re.compile(r"^(\d{6})(?:_(\d+))?\.parquet$")   # HHMMSS.parquet, HHMMSS_1.parquet (2nd poll that second)
TRUNCATED = re.compile(r"^(\d{6})(?:_\d+)?_truncated\.parquet$")
# LTA road categories (LTA DataMall API User Guide v6.10, section 2.19, as quoted in
# notebooks/c/task2-lta-lookup-2026-10-21.ipynb)
CATEGORY_NAME = {"1": "expressway", "2": "major arterial", "3": "arterial", "4": "minor arterial",
                 "5": "small road", "6": "slip road", "8": "short tunnel"}


# ---------------------------------------------------------------- the district

def net_location(net_path):
    """netOffset (x, y), convBoundary (xmin, ymin, xmax, ymax) and projParameter of a SUMO net."""
    for _, el in ET.iterparse(net_path, events=("start",)):
        if el.tag == "location":
            offset = tuple(float(v) for v in el.get("netOffset").split(","))
            boundary = tuple(float(v) for v in el.get("convBoundary").split(","))
            return offset, boundary, el.get("projParameter")
    raise ValueError(f"{net_path}: no <location> element")


def district_box(net_path, margin_m):
    """(W, S, E, N) in degrees (WGS84): the net's convBoundary grown by margin_m metres.

    SUMO stores x = projected x + netOffset, so a projected corner is the net corner minus
    netOffset. The south-west and the north-east corner give the box."""
    from pyproj import CRS, Transformer
    (ox, oy), (xmin, ymin, xmax, ymax), proj = net_location(net_path)
    to_lonlat = Transformer.from_crs(CRS.from_proj4(proj), "EPSG:4326", always_xy=True)
    w, s = to_lonlat.transform(xmin - margin_m - ox, ymin - margin_m - oy)
    e, n = to_lonlat.transform(xmax + margin_m - ox, ymax + margin_m - oy)
    return (w, s, e, n)


def in_box(links, box):
    """Boolean Series: True if the link's start or end point lies inside box (W, S, E, N), edges included."""
    w, s, e, n = box
    start = links.StartLon.between(w, e) & links.StartLat.between(s, n)
    end = links.EndLon.between(w, e) & links.EndLat.between(s, n)
    return start | end


def district_links(links, box):
    """The links inside box, sorted by LinkID as a number (every LTA LinkID is digits)."""
    if not links.LinkID.is_unique:
        raise SystemExit("links.parquet: a LinkID appears twice")
    kept = links.loc[in_box(links, box), LINK_COLUMNS]
    return kept.sort_values("LinkID", key=lambda s: s.astype("int64")).reset_index(drop=True)


def length_m(links):
    """Straight-line start-to-end length of each link in metres (equirectangular; fine at these lengths, median about 29 m)."""
    lat = (links.StartLat + links.EndLat) / 2 * math.pi / 180
    dx = (links.EndLon - links.StartLon) * math.pi / 180 * lat.map(math.cos)
    dy = (links.EndLat - links.StartLat) * math.pi / 180
    return 6371008.8 * (dx ** 2 + dy ** 2) ** 0.5


# ---------------------------------------------------------------- the polls

def poll_files(raw_dir):
    """({day: [(label, path), ...]}, [truncated start times]) for the polls under raw_dir/speedbands.

    The day is the Singapore date of the folder; label is the poll's Singapore start time
    HH:MM:SS (with _n for a second poll in the same second). Polls are in time order.
    *_truncated.parquet files (incomplete polls) are returned separately, never as polls."""
    days, truncated = {}, []
    for day_dir in sorted((Path(raw_dir) / "speedbands").iterdir()):
        if not (day_dir.is_dir() and re.fullmatch(r"\d{8}", day_dir.name)):
            continue
        day = datetime.strptime(day_dir.name, "%Y%m%d").date()
        polls = []
        for f in day_dir.iterdir():
            m, t = POLL_NAME.match(f.name), TRUNCATED.match(f.name)
            if t:
                truncated.append(datetime.strptime(day_dir.name + t.group(1), "%Y%m%d%H%M%S").replace(tzinfo=SGT))
            if not m:   # *_truncated.parquet and the poller's *.tmp files
                continue
            hms, n = m.group(1), m.group(2)
            polls.append((f"{hms[:2]}:{hms[2:4]}:{hms[4:]}" + (f"_{n}" if n else ""), f))
        days[day] = sorted(polls, key=lambda p: (p[0][:8], int(p[0][9:] or 0)))
    return days, sorted(truncated)


def utc_to_sgt(stamp):
    """'2026-10-20T06:54:46Z' -> aware datetime in Singapore time."""
    return datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).astimezone(SGT)


def day_table(polls, link_ids, day):
    """One day's speed bands: rows link_ids, one Int64 column per poll, <NA> where a link is missing.

    Returns (table, facts, ranges): facts has one dict per poll (label, start, served, present);
    ranges maps each band to the set of (MinimumSpeed, MaximumSpeed) seen with it in the district."""
    want = pa.array(list(link_ids), type=pa.string())
    columns, facts, ranges = {}, [], {}
    for label, path in polls:
        t = pq.read_table(path, columns=POLL_COLUMNS)
        stamps = pc.unique(t["poll_time_utc"]).to_pylist()
        start = utc_to_sgt(stamps[0])
        if len(stamps) != 1 or start.date() != day or start.strftime("%H:%M:%S") != label[:8]:
            raise SystemExit(f"{path}: poll_time_utc {stamps} is not {day} {label} Singapore time")
        d = t.filter(pc.is_in(t["LinkID"], value_set=want)).to_pandas()
        if not d.LinkID.is_unique:
            raise SystemExit(f"{path}: a district LinkID appears twice in one poll")
        columns[label] = d.set_index("LinkID")["SpeedBand"]
        for band, lo, hi in d[["SpeedBand", "MinimumSpeed", "MaximumSpeed"]].drop_duplicates().itertuples(index=False):
            ranges.setdefault(int(band), set()).add((None if pd.isna(lo) else float(lo),
                                                     None if pd.isna(hi) else float(hi)))
        facts.append({"label": label, "start": start, "served": t.num_rows, "present": len(d)})
    index = pd.Index(list(link_ids), name="LinkID")
    table = pd.DataFrame(columns, index=index, columns=[p[0] for p in polls]).astype("Int64")
    return table, facts, ranges


def write_csv_gz(table, path, level):
    """Write table as gzip CSV with no time stamp and no file name in the gzip header: same table, same bytes."""
    data = table.to_csv(lineterminator="\n").encode("utf-8")
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(gzip.compress(data, compresslevel=level, mtime=0))
    os.replace(tmp, path)


# ---------------------------------------------------------------- gaps

def slot_of(t, interval_s):
    """Start of the interval_s slot that contains t (Singapore time)."""
    epoch = int(t.timestamp())
    return datetime.fromtimestamp(epoch - epoch % interval_s, SGT)


def read_log(raw_dir):
    """poll_log.csv as a list of dicts with an added 'start' (Singapore time)."""
    log = pd.read_csv(Path(raw_dir) / "poll_log.csv", dtype=str, keep_default_na=False)
    rows = log.to_dict("records")
    for r in rows:
        r["start"] = utc_to_sgt(r["poll_time_utc"])
    return rows


def find_gaps(starts, log, truncated, end, interval_s, notes=None):
    """Runs of interval_s slots with no complete poll, from the first complete poll's slot to end.

    starts: Singapore start times of the complete polls; log: read_log rows; truncated: start
    times of incomplete polls; notes: {"YYYY-MM-DD HH:MM": cause} for gaps that start at that slot.
    Returns a list of dicts: first, last (slot starts), slots, cause."""
    have = {slot_of(t, interval_s) for t in starts}
    in_slot = {}
    for r in log:
        in_slot.setdefault(slot_of(r["start"], interval_s), []).append(r)
    cut = {slot_of(t, interval_s) for t in truncated}
    step, gaps, slot = timedelta(seconds=interval_s), [], min(have)
    while slot < end:
        if slot not in have:
            rows = [r for r in in_slot.get(slot, []) if r["status"] != "ok"]
            if rows:
                cause = "; ".join(f"poll {r['status']} at {r['start']:%H:%M:%S}: {r['error']}" for r in rows)
            elif slot in cut:
                cause = "incomplete poll, left out"
            else:
                cause = "no poll and no line in poll_log.csv, so the poller was not running"
            if gaps and gaps[-1]["last"] + step == slot and gaps[-1]["generic"] == cause:
                gaps[-1].update(last=slot, slots=gaps[-1]["slots"] + 1)
            else:
                gaps.append({"first": slot, "last": slot, "slots": 1, "cause": cause, "generic": cause})
        slot += step
    for g in gaps:
        note = (notes or {}).get(f"{g['first']:%Y-%m-%d %H:%M}")
        if note:
            g["cause"] = f"{g['cause']}; {note}"
    return gaps


# ---------------------------------------------------------------- README

def band_rows(ranges):
    """Markdown rows of the band table from the ranges seen; stops if a band came with two ranges."""
    rows = []
    for band in sorted(ranges):
        if len(ranges[band]) != 1:
            raise SystemExit(f"speed band {band} arrived with more than one range: {sorted(ranges[band], key=str)}")
        (lo, hi), = ranges[band]
        if lo is None and hi is None:
            meaning = "no range: no data for that link in that poll"
        elif hi is not None and hi >= 999:
            meaning = f"{lo:g} km/h or more (LTA serves a maximum of {hi:g})"
        else:
            meaning = f"{lo:g} to {hi:g} km/h"
        rows.append(f"| {band} | {'' if lo is None else f'{lo:g}'} | {'' if hi is None else f'{hi:g}'} | {meaning} |")
    return rows


def readme(cfg, box, links, days, gaps, failed, late, truncated, ranges, poll_seconds, sizes, band0_links):
    first_day, last_day = min(days), max(days)
    first_poll = days[first_day]["first"]
    n_links = len(links)
    cells = sum(d["cells"] for d in days.values())
    empty = sum(d["empty"] for d in days.values())
    band0 = sum(d["band0"] for d in days.values())
    n_polls = sum(d["polls"] for d in days.values())
    margin = cfg["box"]["margin_m"]
    (_, _), (xmin, ymin, xmax, ymax), proj = net_location(ROOT / cfg["network"]["net"])
    cats = links.RoadCategory.astype(str).value_counts()
    cat = links.RoadCategory.astype(str)
    expressways = sorted(set(links.RoadName[cat == "1"]))
    ramps = links[(cat == "6") & links.RoadName.isin(expressways)]   # slip roads named after an expressway
    script, conf, out = "scripts/lta_district_extract.py", cfg["_path"], cfg["output"]["out_dir"]
    L = [
        "# LTA speed bands for the city district",
        "",
        f"Member E's history of real traffic speeds in the city district (Bugis-Rochor-Lavender) lives here: the "
        f"speed band that LTA DataMall's Traffic Speed Bands feed (v4) gave each of the district's {n_links:,} road "
        f"stretches in every poll from {first_day} {first_poll} to the end of {last_day} (Singapore time), "
        f"{n_polls:,} polls, about every 5 minutes. `{script}` writes every file in this folder, this README included, "
        f"from C's raw polls; change the script, not the files (see \"Regenerate\").",
        "",
        "## Files",
        "",
        "| File | What it holds |",
        "| --- | --- |",
        f"| `district_links.csv` | One row per district link (LTA's word for a road stretch: one direction of travel, "
        f"median length {length_m(links).median():.0f} m start to end): `LinkID`, `RoadName`, `RoadCategory`, and the "
        f"start and end points `StartLon`, `StartLat`, `EndLon`, `EndLat` (degrees, WGS84). Sorted by LinkID; "
        f"{n_links:,} rows. |",
        "| `speedbands/<YYYY-MM-DD>.csv.gz` | One file per Singapore calendar day. Column `LinkID` first, rows in the "
        "order of `district_links.csv`; then one column per complete poll of that day, headed by the poll's "
        "Singapore start time `HH:MM:SS`. A cell is the link's speed band in that poll, empty when LTA's answer "
        "did not include the link. |",
        "",
        f"The data files take {sizes['total'] / 1e6:.1f} MB in all, {sizes['day_median'] / 1e6:.2f} MB for a full day.",
        "",
        "## Units: the speed band",
        "",
        "A cell is a speed band, a 10 km/h class of the stretch's speed, not a speed. The ranges below are the "
        "`MinimumSpeed` and `MaximumSpeed` that LTA served with each band; each band came with one range in every "
        "poll here. They agree with LTA's definition (LTA DataMall API User Guide v6.10, section 2.19, as quoted in "
        "`notebooks/c/task2-lta-lookup-2026-10-21.ipynb`). Differences smaller than one band cannot be measured.",
        "",
        "| Band | MinimumSpeed (km/h) | MaximumSpeed (km/h) | Meaning |",
        "| --- | --- | --- | --- |",
        *band_rows(ranges),
        "",
        f"Band 0 appears in {band0:,} of the {cells - empty:,} filled cells ({band0 / max(cells - empty, 1):.2%}), "
        f"on {len(band0_links)} link{'' if len(band0_links) == 1 else 's'}"
        + (": " + ", ".join(f"{i} ({links.set_index('LinkID').RoadName[i].title()}, {n:,} polls)"
                            for i, n in band0_links.items()) if 0 < len(band0_links) <= 10 else "") + ". "
        f"Band 0 is a value LTA's guide does not define; it comes with no speed range, so treat it as missing. "
        f"Empty cells, links missing from a poll, are {empty:,} of {cells:,} ({empty / max(cells, 1):.2%}).",
        "",
        "`RoadCategory` is LTA's road category (same guide, section 2.19). In the district:",
        "",
        "| RoadCategory | Meaning | Links |",
        "| --- | --- | --- |",
        *[f"| {c} | {CATEGORY_NAME.get(c, 'not in the guide')} | {cats[c]:,} |"
          for c in sorted(cats.index, key=int)],
        "",
        f"The simulated network (`{cfg['network']['net']}`) has no expressways or expressway ramps: its build leaves out "
        f"OpenStreetMap's `motorway` and `motorway_link` roads. So links of category 1"
        + (f", and the {len(ramps)} slip-road links (category 6) named "
           + " or ".join(n.title() for n in expressways) + "," if len(ramps) else "")
        + " have no simulated counterpart; leave them out when you compare.",
        "",
        "## The district box",
        "",
        f"A link belongs to the district when its start point or its end point lies inside the box W {box[0]:.6f}, "
        f"S {box[1]:.6f}, E {box[2]:.6f}, N {box[3]:.6f} (degrees, WGS84). The box is the city network's boundary "
        f"(`convBoundary` {xmin:g}, {ymin:g}, {xmax:g}, {ymax:g} m in `{cfg['network']['net']}`) grown by "
        f"{margin:g} m on each side and taken back to longitude and latitude through the net's `netOffset` and "
        f"projection (`{proj}`); its south-west and north-east corners give the four edges. A link whose two end "
        f"points both lie outside is left out, even if it crosses a corner of the box.",
        "",
        "## Polls and their times",
        "",
        f"C's poller asks LTA for the whole island every {cfg['input']['interval_s'] // 60} minutes, all day, every "
        f"day, and keeps every link; LTA refreshes the feed every 5 minutes. A column's time is the moment its poll "
        f"started, in Singapore time (UTC+8). Most polls start a few seconds after a 5-minute boundary (median "
        f"{poll_seconds['offset_median']:.0f} s); a poll then takes {poll_seconds['median']:.0f} s (median; at most "
        f"{poll_seconds['max']:.0f} s) to download the island's pages, so a column's bands were fetched within a few "
        f"minutes after its time. To line days up, use the 5-minute slot a column falls in (`slot` in the pandas example below).",
        "",
    ]
    if late:
        L += [f"Polls that started more than {cfg['input']['late_s']} s after their 5-minute boundary: " + ", ".join(f"{t:%Y-%m-%d %H:%M:%S}" for t in late) + ".",
              ""]
    L += [
        "| Day (SGT) | Weekday | Polls | First | Last | Missing 5-min slots | Links present per poll |",
        "| --- | --- | --- | --- | --- | --- | --- |",
        *[f"| {day} | {day:%a} | {d['polls']} | {d['first']} | {d['last']} | {d['missing']} | "
          f"{d['present_min']:,} to {d['present_max']:,} |" for day, d in days.items()],
        "",
        f"{first_day} begins at {first_poll}, the first complete poll (the earlier polls that day were cut short or failed; see below); "
        "every later day runs from midnight to midnight.",
        "",
        "## Gaps",
        "",
    ]
    if gaps:
        L += [f"A gap is a 5-minute slot with no complete poll. From {first_day} {first_poll} to the end of "
              f"{last_day} there are {sum(g['slots'] for g in gaps)} missing slots in {len(gaps)} runs:",
              "",
              "| First missing slot (SGT) | Last missing slot (SGT) | Slots | Cause |",
              "| --- | --- | --- | --- |",
              *[f"| {g['first']:%Y-%m-%d %H:%M} | {g['last']:%Y-%m-%d %H:%M} | {g['slots']} | {g['cause']} |"
                for g in gaps],
              ""]
    else:
        L += [f"No 5-minute slot from {first_day} {first_poll} to the end of {last_day} is without a complete poll.", ""]
    if failed:
        L += ["Every poll that `poll_log.csv` records as failed or missed in these days (a failed poll whose slot "
              "has no other poll is one of the gaps above):",
              "",
              "| Poll start (SGT) | Status | Error | Slot filled by another poll |",
              "| --- | --- | --- | --- |",
              *[f"| {f['start']:%Y-%m-%d %H:%M:%S} | {f['status']} | {f['error']} | {'yes' if f['filled'] else 'no'} |"
                for f in failed],
              ""]
    if truncated:
        L += ["Left out as incomplete (`*_truncated.parquet` in the raw folder): "
              + ", ".join(f"{t['start']:%Y-%m-%d %H:%M:%S} ({t['served']})" for t in truncated) + ".", ""]
    L += [
        "## Read a day with pandas",
        "",
        "```python",
        "import pandas as pd",
        "",
        f'links = pd.read_csv("{out}/district_links.csv", index_col="LinkID")',
        f'day = pd.read_csv("{out}/speedbands/{last_day}.csv.gz", index_col="LinkID")',
        "# day: one row per link (same order as links), one column per poll, headed HH:MM:SS (Singapore time);",
        "# NaN where the link was missing from that poll",
        "",
        "# long form, one row per link and poll, with a full time stamp:",
        'long = day.rename_axis(columns="time").stack().rename("SpeedBand").reset_index()',
        f'long["time"] = pd.to_datetime("{last_day} " + long["time"])',
        'long["slot"] = long["time"].dt.floor("5min")   # the 5-minute slot, for example 07:49:09 -> 07:45:00',
        "```",
        "",
        f"To put a link's end point on the simulated net, `sumolib.net.readNet(\"{cfg['network']['net']}\")"
        f".convertLonLat2XY(lon, lat)` gives its x and y in metres.",
        "",
        "## Regenerate",
        "",
        "The raw polls are git-ignored and exist only on C's machine (`" + cfg["input"]["raw_dir"] + "`, one "
        "Parquet file per poll for the whole island, about 300 MB per day). From the repository root:",
        "",
        "```bash",
        f"python {script} --config {conf} --through {last_day}",
        "```",
        "",
        "`--through` names the last Singapore day to write (default: yesterday); today is never written, because "
        "the poller is still filling it. Every parameter (network file, box margin, folders, cadence) is in the "
        "config. A rerun on the same raw files gives byte-identical files; a later `--through` adds the new days "
        "and rewrites this README.",
        "",
        "## Source and licence",
        "",
        f"Contains information from Traffic Speed Bands (v4) accessed from {first_day} to {last_day} from LTA DataMall, "
        "which is made available under the terms of the Singapore Open Data Licence version 1.0 "
        "(https://data.gov.sg/open-data-licence).",
        "",
    ]
    return "\n".join(L)


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", required=True)
    ap.add_argument("--through", type=date.fromisoformat,
                    help="last Singapore day to write, YYYY-MM-DD (default: yesterday, Singapore time)")
    a = ap.parse_args()
    cfg = config.load(a.config)
    today = datetime.now(SGT).date()
    through = a.through or today - timedelta(days=1)
    if through >= today:
        raise SystemExit(f"--through {through}: today ({today}, Singapore time) is still being polled; "
                         "give an earlier day")
    raw, out = ROOT / cfg["input"]["raw_dir"], ROOT / cfg["output"]["out_dir"]
    interval, late_s, level = cfg["input"]["interval_s"], cfg["input"]["late_s"], cfg["output"]["gzip_level"]

    box = district_box(ROOT / cfg["network"]["net"], cfg["box"]["margin_m"])
    links = district_links(pd.read_parquet(raw / "links.parquet", columns=LINK_COLUMNS), box)
    print(f"box W,S,E,N = {', '.join(f'{v:.6f}' for v in box)}: {len(links):,} district links")

    all_days, truncated = poll_files(raw)
    polls = {d: p for d, p in all_days.items() if d <= through and p}
    if not polls:
        raise SystemExit(f"no complete polls up to {through} in {raw}")
    (out / "speedbands").mkdir(parents=True, exist_ok=True)
    links.to_csv(out / "district_links.csv", index=False, lineterminator="\n")

    days, starts, ranges, written, band0 = {}, [], {}, set(), pd.Series(0, index=links.LinkID)
    for day, day_polls in polls.items():
        table, facts, seen = day_table(day_polls, links.LinkID, day)
        path = out / "speedbands" / f"{day}.csv.gz"
        write_csv_gz(table, path, level)
        written.add(path.name)
        for band, r in seen.items():
            ranges.setdefault(band, set()).update(r)
        starts += [f["start"] for f in facts]
        present = [f["present"] for f in facts]
        values = table.to_numpy(dtype="float64", na_value=float("nan"))
        band0 += (values == 0).sum(axis=1)
        days[day] = {"polls": len(facts), "first": facts[0]["label"], "last": facts[-1]["label"],
                     "present_min": min(present), "present_max": max(present), "cells": table.size,
                     "empty": int(table.isna().sum().sum()), "band0": int((values == 0).sum()),
                     "bytes": path.stat().st_size}
        print(f"{day}: {len(facts)} polls, {facts[0]['label']} to {facts[-1]['label']}, "
              f"{min(present):,} to {max(present):,} links present, {path.stat().st_size / 1e6:.2f} MB")

    end = datetime.combine(max(polls) + timedelta(days=1), time(0), SGT)
    log = [r for r in read_log(raw) if r["start"] < end]
    gaps = find_gaps(starts, log, truncated, end, interval, cfg.get("notes", {}))
    for d in days.values():
        d["missing"] = 0
    for g in gaps:   # a day with no poll at all has no file and no row; its slots still appear in the gap table
        for k in range(g["slots"]):
            gap_day = (g["first"] + timedelta(seconds=k * interval)).date()
            if gap_day in days:
                days[gap_day]["missing"] += 1
    have = {slot_of(t, interval) for t in starts}
    failed = [dict(r, filled=slot_of(r["start"], interval) in have) for r in log if r["status"] != "ok"]
    late = [t for t in starts if (t - slot_of(t, interval)).total_seconds() > late_s]
    first = min(starts)
    ok = [r for r in log if r["status"] == "ok" and r["start"] >= first]
    seconds = pd.Series([float(r["seconds"]) for r in ok])
    offsets = pd.Series([(t - slot_of(t, interval)).total_seconds() for t in starts])
    served = {r["start"]: r["n_rows_total"] for r in log}
    cut = [{"start": t, "served": f"{int(served[t]):,} links served" if served.get(t) else "size not logged"}
           for t in truncated if t < end]
    stale = sorted(p.name for p in (out / "speedbands").glob("*.csv.gz") if p.name not in written)
    if stale:
        print(f"WARNING: day files not written by this run remain in {out / 'speedbands'}: {', '.join(stale)}")
    slots_per_day = 24 * 3600 // interval
    day_bytes = sorted(d["bytes"] for d in days.values() if d["polls"] >= 0.9 * slots_per_day)   # "a full day"
    sizes = {"total": sum(p.stat().st_size for p in out.rglob("*") if p.is_file() and p.name != "README.md"),
             "day_median": day_bytes[len(day_bytes) // 2] if day_bytes else 0}
    text = readme(cfg, box, links, days, gaps, failed, late, cut, ranges,
                  {"median": seconds.median(), "max": seconds.max(), "offset_median": offsets.median()}, sizes,
                  band0[band0 > 0])
    (out / "README.md").write_text(text)
    print(f"{len(polls)} days, {len(starts):,} polls, {sum(g['slots'] for g in gaps)} missing slots; "
          f"{sizes['total'] / 1e6:.2f} MB in {out}")


if __name__ == "__main__":
    main()
