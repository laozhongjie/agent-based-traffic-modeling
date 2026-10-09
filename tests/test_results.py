import math

import pytest

from traffic_project import results

CFG = {"scenario": "ring", "name": "t"}


def row(**changes):
    r = {"run_id": "ring_idm_L1000_n30_s1", "scenario": "ring", "model": "IDM", "variant": "",
         "seed": 1, "density_veh_km": 30.0, "mean_speed_mps": 16.6, "flow_veh_h": 1792.8,
         "congested_fraction": 0.0, "congested_fraction_var": 0.0, "valid": True,
         "ring_vehicles": 30, "checks": {"sumo_exit_ok": True}}
    r.update(changes)
    return r


def test_summary_round_trip(tmp_root):
    path = results.write_summary([row(), row(run_id="b", seed=2, valid=False)], CFG)
    assert path == tmp_root / "results" / "ring" / "t.csv"
    df = results.load_summary("ring", "t")
    assert list(df.columns) == [n for n, _, _ in results.SUMMARY] + ["ring_vehicles"]
    assert "checks" not in df.columns
    assert df["valid"].tolist() == [True, False]
    assert df["variant"].tolist() == ["", ""]
    assert df["mean_speed_mps"].iloc[0] == pytest.approx(16.6)


@pytest.mark.parametrize("bad, message", [
    ({"congested_fraction": 1.5}, "congested_fraction = 1.5 is out of range"),
    ({"mean_speed_mps": -1.0}, "mean_speed_mps = -1.0 is out of range"),
    ({"density_veh_km": math.nan}, "density_veh_km = nan is out of range"),
    ({"flow_veh_h": "1792"}, "flow_veh_h = '1792' is out of range"),
    ({"vehicles": 30}, "extra column 'vehicles' must start with 'ring_'"),
])
def test_summary_rejects_bad_rows(tmp_root, bad, message):
    with pytest.raises(ValueError, match=message):
        results.write_summary([row(**bad)], CFG)
    assert not (tmp_root / "results").exists()


def test_summary_rejects_missing_column(tmp_root):
    r = row()
    del r["seed"]
    with pytest.raises(ValueError, match="missing column 'seed'"):
        results.write_summary([r], CFG)


def test_timeseries_round_trip_and_check(tmp_root):
    series = [{"time_s": t, "density_veh_km": 30.0, "mean_speed_mps": 16.6,
               "flow_veh_h": 1792.8, "congested_fraction": 0.0} for t in (0, 10)]
    results.write_timeseries("r1", series, CFG)
    ts = results.load_timeseries("ring", "t", "r1")
    assert ts["time_s"].tolist() == [0, 10]

    series[1]["congested_fraction"] = 2.0
    with pytest.raises(ValueError, match="row 1: congested_fraction"):
        results.write_timeseries("r2", series, CFG)
