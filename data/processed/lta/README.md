# LTA speed bands for the city district

Member E's history of real traffic speeds in the city district (Bugis-Rochor-Lavender) lives here: the speed band that LTA DataMall's Traffic Speed Bands feed (v4) gave each of the district's 4,778 road stretches in every poll from 2026-10-20 14:54:46 to the end of 2026-10-31 (Singapore time), 3,267 polls, about every 5 minutes. `scripts/lta_district_extract.py` writes every file in this folder, this README included, from C's raw polls; change the script, not the files (see "Regenerate").

## Files

| File | What it holds |
| --- | --- |
| `district_links.csv` | One row per district link (LTA's word for a road stretch: one direction of travel, median length 29 m start to end): `LinkID`, `RoadName`, `RoadCategory`, and the start and end points `StartLon`, `StartLat`, `EndLon`, `EndLat` (degrees, WGS84). Sorted by LinkID; 4,778 rows. |
| `speedbands/<YYYY-MM-DD>.csv.gz` | One file per Singapore calendar day. Column `LinkID` first, rows in the order of `district_links.csv`; then one column per complete poll of that day, headed by the poll's Singapore start time `HH:MM:SS`. A cell is the link's speed band in that poll, empty when LTA's answer did not include the link. |

The data files take 3.5 MB in all, 0.28 MB for a full day.

## Units: the speed band

A cell is a speed band, a 10 km/h class of the stretch's speed, not a speed. The ranges below are the `MinimumSpeed` and `MaximumSpeed` that LTA served with each band; each band came with one range in every poll here. They agree with LTA's definition (LTA DataMall API User Guide v6.10, section 2.19, as quoted in `notebooks/c/task2-lta-lookup-2026-10-21.ipynb`). Differences smaller than one band cannot be measured.

| Band | MinimumSpeed (km/h) | MaximumSpeed (km/h) | Meaning |
| --- | --- | --- | --- |
| 0 |  |  | no range: no data for that link in that poll |
| 1 | 0 | 9 | 0 to 9 km/h |
| 2 | 10 | 19 | 10 to 19 km/h |
| 3 | 20 | 29 | 20 to 29 km/h |
| 4 | 30 | 39 | 30 to 39 km/h |
| 5 | 40 | 49 | 40 to 49 km/h |
| 6 | 50 | 59 | 50 to 59 km/h |
| 7 | 60 | 69 | 60 to 69 km/h |
| 8 | 70 | 999 | 70 km/h or more (LTA serves a maximum of 999) |

Band 0 appears in 3,267 of the 15,609,726 filled cells (0.02%), on 1 link: 214011 (Kampong Java Road, 3,267 polls). Band 0 is a value LTA's guide does not define; it comes with no speed range, so treat it as missing. Empty cells, links missing from a poll, are 0 of 15,609,726 (0.00%).

`RoadCategory` is LTA's road category (same guide, section 2.19). In the district:

| RoadCategory | Meaning | Links |
| --- | --- | --- |
| 1 | expressway | 79 |
| 2 | major arterial | 1,485 |
| 3 | arterial | 388 |
| 4 | minor arterial | 1,289 |
| 5 | small road | 1,406 |
| 6 | slip road | 127 |
| 8 | short tunnel | 4 |

The simulated network (`scenarios/city/bugis_all.net.xml`) has no expressways or expressway ramps: its build leaves out OpenStreetMap's `motorway` and `motorway_link` roads. So links of category 1, and the 21 slip-road links (category 6) named Central Expressway or East Coast Parkway, have no simulated counterpart; leave them out when you compare.

## The district box

A link belongs to the district when its start point or its end point lies inside the box W 103.843404, S 1.289438, E 103.870171, N 1.318825 (degrees, WGS84). The box is the city network's boundary (`convBoundary` 80.36, 285.38, 2660.2, 3132.88 m in `scenarios/city/bugis_all.net.xml`) grown by 200 m on each side and taken back to longitude and latitude through the net's `netOffset` and projection (`+proj=utm +zone=48 +ellps=WGS84 +datum=WGS84 +units=m +no_defs`); its south-west and north-east corners give the four edges. A link whose two end points both lie outside is left out, even if it crosses a corner of the box.

## Polls and their times

C's poller asks LTA for the whole island every 5 minutes, all day, every day, and keeps every link; LTA refreshes the feed every 5 minutes. A column's time is the moment its poll started, in Singapore time (UTC+8). Most polls start a few seconds after a 5-minute boundary (median 9 s); a poll then takes 126 s (median; at most 275 s) to download the island's pages, so a column's bands were fetched within a few minutes after its time. To line days up, use the 5-minute slot a column falls in (`slot` in the pandas example below).

Polls that started more than 60 s after their 5-minute boundary: 2026-10-20 14:54:46, 2026-10-20 14:56:59, 2026-10-28 07:49:09, 2026-10-28 07:51:18.

| Day (SGT) | Weekday | Polls | First | Last | Missing 5-min slots | Links present per poll |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-10-20 | Tue | 110 | 14:54:46 | 23:55:03 | 0 | 4,778 to 4,778 |
| 2026-10-21 | Wed | 288 | 00:00:02 | 23:55:03 | 0 | 4,778 to 4,778 |
| 2026-10-22 | Thu | 288 | 00:00:04 | 23:55:03 | 0 | 4,778 to 4,778 |
| 2026-10-23 | Fri | 288 | 00:00:03 | 23:55:03 | 0 | 4,778 to 4,778 |
| 2026-10-24 | Sat | 288 | 00:00:03 | 23:55:03 | 0 | 4,778 to 4,778 |
| 2026-10-25 | Sun | 288 | 00:00:03 | 23:55:03 | 0 | 4,778 to 4,778 |
| 2026-10-26 | Mon | 288 | 00:00:03 | 23:55:02 | 0 | 4,778 to 4,778 |
| 2026-10-27 | Tue | 288 | 00:00:03 | 23:55:03 | 0 | 4,778 to 4,778 |
| 2026-10-28 | Wed | 279 | 00:00:04 | 23:55:02 | 9 | 4,778 to 4,778 |
| 2026-10-29 | Thu | 288 | 00:00:03 | 23:55:03 | 0 | 4,778 to 4,778 |
| 2026-10-30 | Fri | 288 | 00:00:03 | 23:55:01 | 0 | 4,778 to 4,778 |
| 2026-10-31 | Sat | 286 | 00:00:02 | 23:55:02 | 2 | 4,778 to 4,778 |

2026-10-20 begins at 14:54:46, the first complete poll (the earlier polls that day were cut short or failed; see below); every later day runs from midnight to midnight.

## Gaps

A gap is a 5-minute slot with no complete poll. From 2026-10-20 14:54:46 to the end of 2026-10-31 there are 11 missing slots in 3 runs:

| First missing slot (SGT) | Last missing slot (SGT) | Slots | Cause |
| --- | --- | --- | --- |
| 2026-10-28 07:00 | 2026-10-28 07:40 | 9 | no poll and no line in poll_log.csv, so the poller was not running; C's record: the Linux system on C's computer that runs the poller (WSL) restarted |
| 2026-10-31 01:05 | 2026-10-31 01:05 | 1 | poll failed at 01:05:02: HTTP 502 on page 275 |
| 2026-10-31 01:20 | 2026-10-31 01:20 | 1 | poll failed at 01:20:05: HTTP 502 on page 0 |

Every poll that `poll_log.csv` records as failed or missed in these days (a failed poll whose slot has no other poll is one of the gaps above):

| Poll start (SGT) | Status | Error | Slot filled by another poll |
| --- | --- | --- | --- |
| 2026-10-20 14:52:45 | failed | <urlopen error [Errno -3] Temporary failure in name resolution> | yes |
| 2026-10-31 01:05:02 | failed | HTTP 502 on page 275 | no |
| 2026-10-31 01:20:05 | failed | HTTP 502 on page 0 | no |

Left out as incomplete (`*_truncated.parquet` in the raw folder): 2026-10-20 14:47:58 (100,000 links served).

## Read a day with pandas

```python
import pandas as pd

links = pd.read_csv("data/processed/lta/district_links.csv", index_col="LinkID")
day = pd.read_csv("data/processed/lta/speedbands/2026-10-31.csv.gz", index_col="LinkID")
# day: one row per link (same order as links), one column per poll, headed HH:MM:SS (Singapore time);
# NaN where the link was missing from that poll

# long form, one row per link and poll, with a full time stamp:
long = day.rename_axis(columns="time").stack().rename("SpeedBand").reset_index()
long["time"] = pd.to_datetime("2026-10-31 " + long["time"])
long["slot"] = long["time"].dt.floor("5min")   # the 5-minute slot, for example 07:49:09 -> 07:45:00
```

To put a link's end point on the simulated net, `sumolib.net.readNet("scenarios/city/bugis_all.net.xml").convertLonLat2XY(lon, lat)` gives its x and y in metres.

## Regenerate

The raw polls are git-ignored and exist only on C's machine (`data/raw/lta_speedbands_v4`, one Parquet file per poll for the whole island, about 300 MB per day). From the repository root:

```bash
python scripts/lta_district_extract.py --config configs/city/lta_district_extract.toml --through 2026-10-31
```

`--through` names the last Singapore day to write (default: yesterday); today is never written, because the poller is still filling it. Every parameter (network file, box margin, folders, cadence) is in the config. A rerun on the same raw files gives byte-identical files; a later `--through` adds the new days and rewrites this README.

## Source and licence

Contains information from Traffic Speed Bands (v4) accessed from 2026-10-20 to 2026-10-31 from LTA DataMall, which is made available under the terms of the Singapore Open Data Licence version 1.0 (https://data.gov.sg/open-data-licence).
