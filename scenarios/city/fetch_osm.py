"""Download raw OpenStreetMap data for a city network from the OSM API, in 2x2 tiles.

The study box from the config, widened by [network] download_margin_deg, is split
into four tiles (the OSM API /map call refuses large boxes). Each tile is saved
gzipped as <osm_dir>/t0.osm.xml.gz ... t3.osm.xml.gz, and <osm_dir>/fetch.json
records the UTC time, the bbox of each tile and its sha256, so a build's
meta.json can be traced to one download. Public Overpass servers were at capacity
on 2026-10-20, which is why the pilot used the OSM API.

Raw data stay in data/raw/ (git-ignored). The script refuses to overwrite an
existing download unless --force is given, because a fresh fetch picks up OSM
edits and changes the network (T1-D9).

Usage (from the repository root):
    python -I scenarios/city/fetch_osm.py --config configs/city/bugis_all.toml
"""
import argparse
import datetime as dt
import gzip
import hashlib
import json
import time
import urllib.request
from pathlib import Path

from traffic_project import ROOT, config

API = "https://api.openstreetmap.org/api/0.6/map?bbox={},{},{},{}"
USER_AGENT = "PC5253-student-project"


def tiles(box, margin):
    """Four (W, S, E, N) tiles covering the box plus margin, in the pilot's t0..t3 order."""
    w, s, e, n = (round(v, 5) for v in (box[0] - margin, box[1] - margin, box[2] + margin, box[3] + margin))
    mx, my = round((w + e) / 2, 5), round((s + n) / 2, 5)
    return [(w, s, mx, my), (mx, s, e, my), (w, my, mx, n), (mx, my, e, n)]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", required=True)
    ap.add_argument("--osm-dir", default=None, help="default [network] osm_dir")
    ap.add_argument("--force", action="store_true", help="overwrite an existing download")
    args = ap.parse_args()
    cfg = config.load(args.config)
    net = cfg["network"]
    out = Path(args.osm_dir or ROOT / net["osm_dir"])
    if out.exists() and any(out.iterdir()) and not args.force:
        raise SystemExit(f"{out} is not empty; pass --force to re-download (this changes the network)")
    out.mkdir(parents=True, exist_ok=True)
    record = {"fetched_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "source": API.split("?")[0], "study_box": net["study_box"],
              "download_margin_deg": net["download_margin_deg"], "tiles": {}}
    for i, bb in enumerate(tiles(net["study_box"], net["download_margin_deg"])):
        req = urllib.request.Request(API.format(*bb), headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=180) as r:
            data = r.read()
        if not data.rstrip().endswith(b"</osm>"):
            raise RuntimeError(f"tile t{i} {bb}: truncated or error response: {data[:200]!r}")
        path = out / f"t{i}.osm.xml.gz"
        path.write_bytes(gzip.compress(data))
        record["tiles"][path.name] = {"bbox": list(bb), "bytes_raw": len(data),
                                      "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        time.sleep(2)  # be polite to the public API
    (out / "fetch.json").write_text(json.dumps(record, indent=1) + "\n")
    print(json.dumps(record, indent=1))


if __name__ == "__main__":
    main()
