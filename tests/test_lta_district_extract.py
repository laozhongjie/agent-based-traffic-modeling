"""scripts/lta_district_extract.py: the district box filter, the split of polls into Singapore
days, and reproducible day files, on small made-up inputs (no raw LTA data needed).
"""
import importlib.util
from datetime import date, datetime, timedelta

import pandas as pd
import pytest

from traffic_project import ROOT

pytest.importorskip("pyarrow")


@pytest.fixture(scope="module")
def ex():
    spec = importlib.util.spec_from_file_location("lta_district_extract", ROOT / "scripts" / "lta_district_extract.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def links_table(rows):
    return pd.DataFrame(rows, columns=["LinkID", "RoadName", "RoadCategory", "StartLon", "StartLat", "EndLon", "EndLat"])


def test_box_keeps_a_link_with_either_end_inside(ex):
    box = (103.0, 1.0, 104.0, 2.0)   # W, S, E, N
    links = links_table([
        ("30", "START IN", "2", 103.5, 1.5, 105.0, 1.5),
        ("4", "END IN", "3", 102.0, 1.5, 103.5, 1.5),
        ("200", "BOTH OUT, CROSSING", "4", 102.5, 1.5, 104.5, 1.5),
        ("1", "ON THE EDGE", "5", 104.0, 2.0, 104.5, 2.5),
        ("7", "FAR OUT", "5", 110.0, 1.5, 110.1, 1.5),
    ])
    kept = ex.district_links(links, box)
    assert list(kept.LinkID) == ["1", "4", "30"]   # sorted by LinkID as a number, not as text


def test_net_box_contains_the_net_and_its_margin(ex):
    pytest.importorskip("pyproj")
    net = ROOT / "scenarios" / "city" / "bugis_all.net.xml"
    w, s, e, n = ex.district_box(net, 200.0)
    w0, s0, e0, n0 = ex.district_box(net, 0.0)
    assert w < w0 < e0 < e and s < s0 < n0 < n
    assert (s0 - s) * 110_574 == pytest.approx(200.0, rel=0.01)   # one degree of latitude is 110,574 m at the equator


def write_poll(path, utc, bands):
    df = pd.DataFrame({"poll_time_utc": utc, "LinkID": list(bands), "SpeedBand": list(bands.values())})
    df["MinimumSpeed"] = (df.SpeedBand - 1) * 10.0
    df["MaximumSpeed"] = df.MinimumSpeed + 9
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def test_polls_split_by_singapore_day_and_files_are_reproducible(ex, tmp_path):
    sb = tmp_path / "speedbands"
    write_poll(sb / "20261020" / "235501.parquet", "2026-10-20T15:55:01Z", {"10": 3, "2": 5, "99": 1})
    write_poll(sb / "20261021" / "000003.parquet", "2026-10-20T16:00:03Z", {"2": 4, "10": 2})   # link 99 missing
    write_poll(sb / "20261021" / "000003_1.parquet", "2026-10-20T16:00:03Z", {"2": 6, "10": 6, "99": 6})
    write_poll(sb / "20261021" / "001000_truncated.parquet", "2026-10-20T16:10:00Z", {"2": 1})
    (sb / "20261021" / "001500.parquet.tmp").write_bytes(b"half a file")

    days, truncated = ex.poll_files(tmp_path)
    assert [label for label, _ in days[date(2026, 10, 21)]] == ["00:00:03", "00:00:03_1"]
    assert [t.strftime("%Y-%m-%d %H:%M:%S") for t in truncated] == ["2026-10-21 00:10:00"]

    order = ["2", "10", "99"]
    table, facts, ranges = ex.day_table(days[date(2026, 10, 21)], order, date(2026, 10, 21))
    assert list(table.index) == order and list(table.columns) == ["00:00:03", "00:00:03_1"]
    assert table.loc["99", "00:00:03"] is pd.NA and table.loc["2", "00:00:03"] == 4
    assert [f["present"] for f in facts] == [2, 3] and ranges[4] == {(30.0, 39.0)}

    out = tmp_path / "out.csv.gz"
    ex.write_csv_gz(table, out, 9)
    first = out.read_bytes()
    ex.write_csv_gz(table, out, 9)
    assert out.read_bytes() == first
    assert first[3] == 0 and first[4:8] == bytes(4)   # gzip header: no file name flag, time stamp 0
    back = pd.read_csv(out, index_col="LinkID")
    assert list(back.index) == [2, 10, 99] and back.isna().sum().sum() == 1

    with pytest.raises(SystemExit):   # a poll whose stored time is not its file's Singapore time
        ex.day_table(days[date(2026, 10, 20)], order, date(2026, 10, 21))


def test_gaps_name_their_cause(ex):
    sgt = ex.SGT
    t0 = datetime(2026, 10, 28, 6, 50, 4, tzinfo=sgt)
    starts = [t0, t0 + timedelta(minutes=5), t0 + timedelta(minutes=30)]   # slots 07:00-07:15 have no poll
    log = [{"start": datetime(2026, 10, 28, 7, 10, 2, tzinfo=sgt), "status": "failed", "error": "HTTP 502"}]
    gaps = ex.find_gaps(starts, log, [], datetime(2026, 10, 28, 7, 25, tzinfo=sgt), 300,
                        {"2026-10-28 07:00": "restart"})
    assert [(g["first"].strftime("%H:%M"), g["slots"]) for g in gaps] == [("07:00", 2), ("07:10", 1), ("07:15", 1)]
    assert gaps[0]["cause"].endswith("restart") and "HTTP 502" in gaps[1]["cause"]
