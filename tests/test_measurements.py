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


def write_summary(path, running):
    """Minimal SUMO summary-output: running = {time_s: count}."""
    steps = "".join(f'  <step time="{t:.2f}" running="{n}"/>\n' for t, n in running.items())
    path.write_text(f"<summary>\n{steps}</summary>\n")
    return path


def test_network_summary_counts_teleporting_vehicles_from_summary_xml(tmp_path):
    # vehicle "b" is in mid-teleport at t = 1: missing from the FCD output, still running
    fcd = write_fcd(tmp_path / "fcd.xml", {0: [("a", 5.0), ("b", 5.0)], 1: [("a", 5.0)],
                                          2: [("a", 5.0), ("b", 5.0)]})
    args = (2, 100.0, 0, 1.0, 1.0)
    _, from_fcd, _ = measurements.network_summary(fcd, *args)
    assert not from_fcd["all_vehicles_present"]
    full = write_summary(tmp_path / "summary.xml", {0: 2, 1: 2, 2: 2})
    _, from_summary, _ = measurements.network_summary(fcd, *args, summary_xml=full)
    assert from_summary["all_vehicles_present"]
    delayed = write_summary(tmp_path / "late.xml", {0: 1, 1: 2, 2: 2})   # one insertion delayed
    _, late, _ = measurements.network_summary(fcd, *args, summary_xml=delayed)
    assert not late["all_vehicles_present"]


def test_city_summary_on_a_hand_built_net(tmp_path):
    # The three-node test net of test_congestion.py: lane length 700 m, one 60 s signal cycle.
    # AB (200 m of lane) runs at 1 m/s against a reference speed of 10 m/s in both intervals,
    # so it is congested; it holds 60 of the 120 vehicle-seconds of each interval.
    from test_congestion import EDGES, write_edgedata, write_net
    net = write_net(tmp_path / "t.net.xml")
    ref = write_edgedata(tmp_path / "ref.xml", [{e: (100, 10.0, 1, 5) for e in EDGES}] * 2)
    jam = {"AB": (60, 1.0, 10, 1), "BA": (20, 9.0, 1, 2), "BC": (20, 9.0, 1, 2), "CB": (20, 9.0, 1, 2)}
    run = write_edgedata(tmp_path / "run.xml", [jam, jam])
    steps = "".join(f'<step time="{t}.00" running="7" halting="0" meanSpeed="5.00"/>' for t in range(120))
    summary = tmp_path / "summary.xml"
    summary.write_text(f"<summary>{steps}</summary>")
    assert measurements.read_summary_xml(summary).shape == (120, 4)
    measure = dict(period_s="cycle", period_mult=1, r_on=0.5, persist_m=1, adjacency="directed",
                   weight="lane_length", vref_min_sampled_s=60, vref_fallback="class_median",
                   veh_length_m=5.0, min_gap_m=2.0, spillback_occ_frac=0.8, gridlock_outflow_frac=0.01,
                   gridlock_cycles=3, timeseries_every_s=30)
    m, checks, series = measurements.city_summary(run, ref, net, summary, measure, 0, n_vehicles=7)
    assert m["density_veh_km"] == pytest.approx(10)                 # 7 vehicles / 0.7 km
    assert m["flow_veh_h"] == pytest.approx(10 * 5 * 3.6)
    assert m["congested_fraction"] == pytest.approx(0.5) and m["congested_fraction_var"] == 0
    assert m["city_congested_length_fraction"] == pytest.approx(200 / 700)
    assert m["city_vref_coverage"] == 1 and m["city_lane_length_m"] == 700 and m["city_gridlock"] == 0
    assert all(checks.values())
    # 30 s rows; congested_fraction repeats the last completed 60 s interval (0 before the first)
    assert [(s["time_s"], s["congested_fraction"]) for s in series] == [(0, 0), (30, 0), (60, 0.5), (90, 0.5)]
    _, short, _ = measurements.city_summary(run, ref, net, summary, measure, 0, n_vehicles=8)
    assert not short["all_vehicles_present"]
