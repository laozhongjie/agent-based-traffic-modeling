import pytest

from traffic_project import measurements
from conftest import write_fcd


def test_ring_summary_values(tmp_path):
    # 2 vehicles on a 100 m ring, so k = 20 veh/km. Warm-up 1 s, jam below 5 m/s.
    fcd = write_fcd(tmp_path / "fcd.xml", {
        0: [("a", 0), ("b", 0)],
        1: [("a", 2), ("b", 4)],   # v = 3, phi = 1
        2: [("a", 6), ("b", 6)],   # v = 6, phi = 0
        3: [("a", 4), ("b", 8)],   # v = 6, phi = 0.5
    })
    m, checks, series = measurements.ring_summary(fcd, 2, 100, warmup_s=1,
                                                  jam_speed_mps=5, sample_every_s=2)
    assert m["density_veh_km"] == 20
    assert m["mean_speed_mps"] == pytest.approx(5)
    assert m["flow_veh_h"] == pytest.approx(20 * 5 * 3.6)
    assert m["congested_fraction"] == pytest.approx(0.5)
    assert m["congested_fraction_var"] == pytest.approx(1 / 6)
    assert checks == {"all_vehicles_present": True, "no_negative_speed": True}
    # Samples every 2 s over the whole run, warm-up included
    assert [s["time_s"] for s in series] == [0, 2]
    assert series[1] == {"time_s": 2, "density_veh_km": 20, "mean_speed_mps": 6,
                         "flow_veh_h": 432.0, "congested_fraction": 0}


def test_ring_summary_checks_fail(tmp_path):
    fcd = write_fcd(tmp_path / "fcd.xml", {
        0: [("a", 1), ("b", 1)],
        1: [("a", -0.1)],          # b is missing, a moves backwards
    })
    _, checks, _ = measurements.ring_summary(fcd, 2, 100, warmup_s=0,
                                             jam_speed_mps=5, sample_every_s=1)
    assert checks == {"all_vehicles_present": False, "no_negative_speed": False}
