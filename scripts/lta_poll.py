"""Poll LTA DataMall Traffic Speed Bands (v4) and keep the district's links (task 2).

One config, one command (run with `python -I`; SUMO_HOME must be set):
    python -I scripts/lta_poll.py --config configs/city/lta_lookup.toml            # one live poll
    python -I scripts/lta_poll.py --config configs/city/lta_lookup.toml --loop     # poll in [poll] windows
    python -I scripts/lta_poll.py --config configs/city/lta_lookup.toml \
        --from-file Speed_Bands.json --out runs/lta_poll_dryrun                     # dry run, no key

A live poll reads the AccountKey from the environment variable LTA_ACCOUNT_KEY (never from
a file under git) and sends it only as a request header; it is never printed or written.
Without the key and without --from-file the script exits with status 2.

Each poll pages `$skip` by 500 until a page has fewer than 500 rows, keeps the links with
an end point inside the net boundary grown by [poll] bbox_margin_m, and writes to the
output folder ([poll] out_dir, or --out):
    speedbands_<YYYYMMDD>.parquet  appended: poll_time_utc, LinkID, SpeedBand, MinimumSpeed, MaximumSpeed
    links.parquet                  one row per LinkID seen: name, category, end points (lookup input)
    poll_log.csv                   one line per poll, including failed or missed polls, so gaps are visible
"""
import argparse
import csv
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from traffic_project import ROOT, config
from traffic_project import lta

SGT = timezone(timedelta(hours=8))
LOG_FIELDS = ["poll_time_utc", "status", "source", "n_rows_total", "n_kept", "n_pages", "seconds", "error"]


def in_windows(now_sgt, windows, weekdays_only):
    """True if now (Singapore time) falls in one of the "HH:MM-HH:MM" windows."""
    if weekdays_only and now_sgt.weekday() >= 5:
        return False
    hm = now_sgt.strftime("%H:%M")
    return any(a <= hm < b for a, b in (w.split("-") for w in windows))


def log_line(out_dir, **row):
    path = out_dir / "poll_log.csv"
    new = not path.exists()
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, LOG_FIELDS)
        if new:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in LOG_FIELDS})


def store(out_dir, rows, poll_time, box):
    """Filter rows to the box and append them; returns (n_total, n_kept)."""
    links = lta.links_from_rows(rows)
    if links.empty:
        return 0, 0
    kept = links[lta.in_box(links, box)].copy()
    day = poll_time.astimezone(SGT).strftime("%Y%m%d")
    bands = kept[["LinkID"] + [c for c in lta.BAND_COLUMNS if c in kept]].copy()
    bands.insert(0, "poll_time_utc", poll_time.strftime("%Y-%m-%dT%H:%M:%SZ"))
    for c in lta.BAND_COLUMNS:
        if c in bands:
            bands[c] = pd.to_numeric(bands[c], errors="coerce")
    f = out_dir / f"speedbands_{day}.parquet"
    if f.exists():
        bands = pd.concat([pd.read_parquet(f), bands], ignore_index=True)
    bands.to_parquet(f, index=False)
    geo = kept[lta.LINK_COLUMNS]
    g = out_dir / "links.parquet"
    if g.exists():
        geo = pd.concat([pd.read_parquet(g), geo]).drop_duplicates("LinkID", keep="last")
    geo.to_parquet(g, index=False)
    return len(links), len(kept)


def poll_once(out_dir, p, box, key=None, from_file=None):
    """One poll; always writes one poll_log line, also on failure. Returns True on success."""
    t0, now = time.time(), datetime.now(timezone.utc)
    try:
        if from_file:
            rows, pages, source = lta.load_links(from_file).to_dict("records"), 0, "file:" + Path(from_file).name
        else:
            rows, pages = lta.fetch_all_pages(key, p["url"], pause_s=p.get("page_pause_s", 1.0),
                                              timeout_s=p.get("timeout_s", 30.0))
            source = "api"
        n_total, n_kept = store(out_dir, rows, now, box)
        log_line(out_dir, poll_time_utc=now.strftime("%Y-%m-%dT%H:%M:%SZ"), status="ok", source=source,
                 n_rows_total=n_total, n_kept=n_kept, n_pages=pages, seconds=round(time.time() - t0, 1))
        print(f"{now:%Y-%m-%d %H:%M:%S} UTC: {n_total} links served, {n_kept} kept, {pages} pages")
        return True
    except Exception as err:  # noqa: BLE001  a failed poll is logged, never fatal in --loop
        msg = str(err).replace(key, "<redacted>") if key else str(err)
        log_line(out_dir, poll_time_utc=now.strftime("%Y-%m-%dT%H:%M:%SZ"), status="failed",
                 source="file" if from_file else "api", seconds=round(time.time() - t0, 1), error=msg[:200])
        print(f"poll failed: {msg[:200]}", file=sys.stderr)
        return False


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", required=True)
    ap.add_argument("--from-file", help="dry run: read one DataMall JSON response instead of calling the API")
    ap.add_argument("--out", help="output folder (default [poll] out_dir)")
    ap.add_argument("--loop", action="store_true", help="poll every interval_s inside the [poll] windows")
    a = ap.parse_args()
    cfg = config.load(a.config)
    p = cfg["poll"]
    key = os.environ.get("LTA_ACCOUNT_KEY", "").strip() or None
    if not a.from_file and not key:
        print("LTA_ACCOUNT_KEY is not set (decision T2-D1); use --from-file for a dry run", file=sys.stderr)
        raise SystemExit(2)
    out_dir = Path(a.out) if a.out else ROOT / p["out_dir"]
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    box = lta.net_lonlat_box(ROOT / cfg["network"]["net"], p["bbox_margin_m"])
    print(f"box W,S,E,N = {', '.join(f'{v:.5f}' for v in box)} (net boundary + {p['bbox_margin_m']:g} m)")
    if not a.loop:
        raise SystemExit(0 if poll_once(out_dir, p, box, key, a.from_file) else 1)
    interval = p["interval_s"]
    slot = time.time() // interval * interval  # the interval boundary this poll belongs to
    while True:  # one poll per interval boundary inside the windows; a failed poll is logged and skipped
        now = datetime.now(SGT)
        if in_windows(now, p["windows"], p.get("weekdays_only", True)):
            poll_once(out_dir, p, box, key, a.from_file)
        time.sleep(max(0.0, slot + interval - time.time()))
        slot += interval
        while slot + interval <= time.time():  # the machine slept: log every slot it missed
            t = datetime.fromtimestamp(slot, SGT)
            if in_windows(t, p["windows"], p.get("weekdays_only", True)):
                log_line(out_dir, poll_time_utc=t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                         status="missed", source="api", error="no poll in this slot (host asleep or busy)")
            slot += interval


if __name__ == "__main__":
    main()
