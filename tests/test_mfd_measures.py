"""Hand-built cases with known answers for traffic_project.mfd_measures (task 6).

Test net (no file): nodes A, B, C; edges AB (100 m, 2 lanes, 10 m/s), BC (200 m, 1 lane,
10 m/s), AC (500 m, 1 lane, 10 m/s, a slow direct road), and a parallel pair X1, X2 from
C to A (X1 50 m, X2 100 m, both 10 m/s). Lane length 200 + 200 + 500 + 50 + 100 = 1050 m.
"""
import numpy as np
import pandas as pd
import pytest

from traffic_project import congestion as cg
from traffic_project import mfd_measures as mm

P = 90.0
M = dict(veh_length_m=5.0, min_gap_m=2.0, spillback_occ_frac=0.8, persist_m=2)


def make_net(connections=None):
    edges = pd.DataFrame(dict(
        edge=["AB", "BC", "AC", "X1", "X2"], frm=["A", "B", "A", "C", "C"], to=["B", "C", "C", "A", "A"],
        length=[100.0, 200.0, 500.0, 50.0, 100.0], lanes=[2, 1, 1, 1, 1], limit=[10.0] * 5)).set_index("edge")
    conns = connections if connections is not None else {
        ("AB", "BC"), ("BC", "X1"), ("BC", "X2"), ("AC", "X1"), ("AC", "X2"), ("X1", "AB"), ("X1", "AC"),
        ("X2", "AB"), ("X2", "AC")}
    return cg.Net(edges, conns, {})


def edgedata(rows):
    """rows: (begin, edge, sampledSeconds, speed, occupancy, waitingTime)."""
    out = pd.DataFrame(rows, columns=("begin", "edge", "sampledSeconds", "speed", "occupancy", "waitingTime"))
    out["end"] = out.begin + P
    for c in ("entered", "left", "density"):
        out[c] = 0.0
    return out[["begin", "end", "edge", *cg.EDGEDATA_COLS]]


# ---------------------------------------------------------------- queues

def test_queue_table_halted_metres_and_ratio():
    net = make_net()
    df = edgedata([(0, "AB", 900, 2.0, 50, 180), (0, "BC", 90, 5.0, 10, 90), (0, "AC", 0, np.nan, np.nan, 0),
                   (0, "X1", 0, np.nan, np.nan, 0), (0, "X2", 0, np.nan, np.nan, 0)])
    halted, qm, ratio = mm.queue_table(df, net.edges, P, 5.0, 2.0)
    # AB: 180 halting s / 90 s = 2 cars; 2 x 7 m over 2 lanes = 7 m per lane; 7 / 100 m
    assert halted.loc[0, "AB"] == pytest.approx(2.0)
    assert qm.loc[0, "AB"] == pytest.approx(7.0)
    assert ratio.loc[0, "AB"] == pytest.approx(0.07)
    # BC: 1 car, 7 m on one lane, 7 / 200
    assert qm.loc[0, "BC"] == pytest.approx(7.0) and ratio.loc[0, "BC"] == pytest.approx(0.035)
    assert halted.loc[0, "AC"] == 0.0


def test_rises_counts_first_row_and_transitions():
    x = np.array([[1, 0], [1, 1], [0, 1], [1, 0]])
    # column 0: rise at row 0 and row 3; column 1: rise at row 1
    assert mm.rises(x).tolist() == [1, 1, 0, 1]


def test_run_measures_on_two_cycle_window():
    net = make_net()
    E = net.edges
    rows = []
    for t in (0, 90, 180, 270):
        jam = t >= 90   # AB jammed (congested + occupancy 70 % >= 0.8 x 5/7 = 57.1 %) from t = 90
        rows += [(t, "AB", 900, 0.5 if jam else 10.0, 70 if jam else 5, 180 if jam else 0),
                 (t, "BC", 90, 10.0, 5, 0), (t, "AC", 0, np.nan, np.nan, 0),
                 (t, "X1", 0, np.nan, np.nan, 0), (t, "X2", 0, np.nan, np.nan, 0)]
    df = edgedata(rows)
    vref = pd.Series(10.0, index=E.index)
    state = cg.classify(cg.relative_speed(df, vref), r_on=0.5, persist_m=2)
    # AB congested from the second slow interval (t = 180) on: persist m = 2
    assert state.AB.tolist() == [0, 0, 1, 1]
    summ, per_edge, spill = mm.run_measures(df, state, E, warmup_s=180, period_s=P, n_vehicles=4, m=M)
    assert summ["n_intervals"] == 2
    assert summ["halted_veh"] == pytest.approx(2.0)          # AB: 180 s / 90 s
    assert summ["halted_share"] == pytest.approx(0.5)        # 2 of 4 cars
    assert summ["queued_lane_share"] == pytest.approx(14.0 / 1050)
    # spillback needs 2 consecutive raw intervals: raw from t = 180, state from t = 270
    assert spill.AB.tolist() == [0, 0, 0, 1]
    assert summ["spill_events"] == 1 and summ["spill_edges_ever"] == 1
    assert summ["spill_events_per_h"] == pytest.approx(1 / (180 / 3600))
    assert summ["spill_edge_share"] == pytest.approx(1 / (2 * 5))
    assert summ["spill_len_share"] == pytest.approx((0 + 200 / 1050) / 2)
    assert summ["spill_given_congested"] == pytest.approx(0.5)
    # distance: AB 900 s x 0.5 m/s + BC 90 s x 10 m/s per interval, over 1050 lane-m x 180 s
    assert summ["edgedata_flow_veh_h"] == pytest.approx(2 * (450 + 900) / (1050 * 180) * 3600)
    assert per_edge.loc["AB", "congested_share"] == 1.0 and per_edge.loc["BC", "congested_share"] == 0.0


# ---------------------------------------------------------------- queue-output

QUEUE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<queue-export>
    <interval begin="0.00" end="90.00">
        <edge id="AB" samples="5" maxQueueLengthInVehicles="14.00" medianQueueLengthInVehicles="3.00" percentileQueueLengthInVehicles="12.00" maxQueueLengthInMeters="98.00" medianQueueLengthInMeters="20.00" percentileQueueLengthInMeters="90.00"/>
        <edge id="BC" samples="2" maxQueueLengthInVehicles="1.00" medianQueueLengthInVehicles="1.00" percentileQueueLengthInVehicles="1.00" maxQueueLengthInMeters="7.00" medianQueueLengthInMeters="7.00" percentileQueueLengthInMeters="7.00"/>
        <edge id=":B_0" samples="1" maxQueueLengthInVehicles="1.00" medianQueueLengthInVehicles="1.00" percentileQueueLengthInVehicles="1.00" maxQueueLengthInMeters="5.00" medianQueueLengthInMeters="5.00" percentileQueueLengthInMeters="5.00"/>
    </interval>
    <interval begin="90.00" end="180.00">
        <edge id="AB" samples="5" maxQueueLengthInVehicles="2.00" medianQueueLengthInVehicles="1.00" percentileQueueLengthInVehicles="2.00" maxQueueLengthInMeters="14.00" medianQueueLengthInMeters="7.00" percentileQueueLengthInMeters="14.00"/>
    </interval>
</queue-export>
"""


def test_read_queue_output(tmp_path):
    f = tmp_path / "queue90.xml"
    f.write_text(QUEUE_XML)
    q = mm.read_queue_output(f)
    assert len(q) == 4
    row = q[(q.begin == 0) & (q.edge == "AB")].iloc[0]
    assert (row.max_veh, row.max_m, row.median_m, row.pct_m, row.samples) == (14, 98, 20, 90, 5)


def test_queue_output_measures(tmp_path):
    f = tmp_path / "queue90.xml"
    f.write_text(QUEUE_XML)
    q = mm.read_queue_output(f)
    E = make_net().edges
    idx = pd.Index([0.0, 90.0], name="begin")
    state = pd.DataFrame(0, index=idx, columns=E.index)
    spill = state.copy()
    spill.loc[0.0, "AB"] = 1
    out = mm.queue_output_measures(q, state, spill, E, warmup_s=0, spacing_m=7.0)
    # full: AB at t = 0 (98 m >= 100 - 7); BC (7 m < 193) and AB at t = 90 are not; ':B_0' dropped
    assert out["qo_full_share"] == pytest.approx(1 / 10)
    assert out["qo_queue_share"] == pytest.approx(3 / 10)
    assert out["qo_full_also_spill"] == 1.0 and out["qo_spill_also_full"] == 1.0
    assert out["qo_max_m_mean"] == pytest.approx((98 + 7 + 14) / 10)


# ---------------------------------------------------------------- betweenness and onset

def test_junction_betweenness_parallel_edges_and_shortcut():
    b = mm.junction_betweenness(make_net())
    # free-flow times: AB 10 s, BC 20 s, AC 50 s, X1 5 s, X2 10 s. A -> C goes A-B-C (30 s < 50 s),
    # so AC carries no shortest path; X2 is slower than its parallel X1 and carries none.
    assert b["AC"] == 0.0 and b["X2"] == 0.0
    # ordered pairs (A,B) (A,C) (B,C) (B,A) (C,A) (C,B): X1 is on B->A, C->A, C->B; AB on A->B, A->C, C->B
    n = 3
    assert b["X1"] == pytest.approx(3 / (n * (n - 1)))
    assert b["AB"] == pytest.approx(3 / (n * (n - 1)))
    assert b["BC"] == pytest.approx(3 / (n * (n - 1)))


def test_turn_betweenness_respects_turn_restrictions():
    # restricted turns: no arc enters X2, so no path passes through it; AB is entered only
    # from X2, so it lies on X2 -> BC, X2 -> X1 and X2 -> AC
    conns = {("AB", "BC"), ("BC", "X1"), ("AC", "X1"), ("X1", "AC"), ("X2", "AB")}
    b = mm.turn_betweenness(make_net(conns))
    assert b["X2"] == 0.0
    assert b["AB"] > 0.0 and b["BC"] > 0.0
    # all turns: X1 and X2 have the same arcs in and out, and leaving X1 costs 5 s against 10 s,
    # so every shortest path takes X1
    b_full = mm.turn_betweenness(make_net())
    assert b_full["X2"] == 0.0 and b_full["X1"] > 0.0


def test_congested_shares_mean_over_seeds():
    per_run = {(10.0, 1): pd.Series({"a": 0.2, "b": 0.0}), (10.0, 2): pd.Series({"a": 0.6, "b": 0.0}),
               (5.0, 1): pd.Series({"a": 0.1, "b": 0.0})}
    s = mm.congested_shares(per_run)
    assert s.index.tolist() == [5.0, 10.0]
    assert s.loc[10.0, "a"] == pytest.approx(0.4) and s.loc[5.0, "a"] == pytest.approx(0.1)
    on = cg.onset_density(s, 0.3)
    assert on["a"] == 10.0 and np.isnan(on["b"])


def test_onset_correlation_signs_and_censoring():
    btw = pd.Series([0.5, 0.4, 0.3, 0.2, 0.1], index=list("abcde"))
    onset = pd.Series([5.0, 10.0, 20.0, np.nan, np.nan], index=list("abcde"))
    out = mm.onset_correlation(btw, onset, censor_at=50.0)
    assert out["n_onset"] == 3 and out["n_censored"] == 2
    assert out["rho_onset_only"] == pytest.approx(-1.0)
    # censored edges tie at the top rank: still a perfect inverse ordering apart from the tie
    assert out["rho_censored"] < -0.9 and out["tau_censored"] < -0.9


def test_free_flow_time_takes_a_measured_speed():
    net = make_net()
    assert mm.free_flow_time(net.edges)["AC"] == pytest.approx(50.0)
    v = pd.Series(10.0, index=net.edges.index)
    v["AC"] = 50.0                                   # AC measured fast: 500 m / 50 m/s = 10 s
    tt = mm.free_flow_time(net.edges, v)
    assert tt["AC"] == pytest.approx(10.0) and tt["AB"] == pytest.approx(10.0)
    # A -> C now goes by AC (10 s < 30 s): AC gains that path, AB keeps A->B and C->B only
    b = mm.junction_betweenness(net, tt)
    assert b["AC"] == pytest.approx(1 / 6) and b["AB"] == pytest.approx(2 / 6)
    assert mm.turn_betweenness(net, tt)["AC"] > mm.turn_betweenness(net)["AC"]


def test_per_lane_divides_by_lanes():
    net = make_net()
    b = mm.per_lane(pd.Series(0.5, index=net.edges.index), net.edges)
    assert b["AB"] == pytest.approx(0.25) and b["BC"] == pytest.approx(0.5)


def test_reference_load_counts_cars_leaving_after_warmup():
    net = make_net()
    d = edgedata([(0.0, "AB", 10, 9, 1, 0), (90.0, "AB", 10, 9, 1, 0), (180.0, "AB", 10, 9, 1, 0),
                  (90.0, "BC", 10, 9, 1, 0)])
    d["left"] = [5.0, 3.0, 4.0, 2.0]
    load = mm.reference_load(d, net.edges, warmup_s=90.0)
    assert load["AB"] == 7.0 and load["BC"] == 2.0 and load["AC"] == 0.0


def test_partial_spearman_removes_a_shared_driver():
    rng = np.random.default_rng(1)
    z = np.arange(300.0)
    x = z + rng.normal(0, 20, 300)
    y = z + rng.normal(0, 20, 300)
    assert stats_spearman(x, y) > 0.9
    r, p = mm.partial_spearman(x, y, z)
    assert abs(r) < 0.2 and p > 0.01                 # x and y agree only through z
    e = rng.normal(0, 1, 300)
    r2, p2 = mm.partial_spearman(z + 30 * e, e, z)   # a link that z does not explain survives
    assert r2 > 0.8 and p2 < 1e-6


def stats_spearman(a, b):
    return pd.Series(a).corr(pd.Series(b), "spearman")


def test_onset_correlation_partial_on_load_and_few_onsets():
    idx = list("abcdef")
    btw = pd.Series([0.6, 0.5, 0.4, 0.3, 0.2, 0.1], index=idx)
    onset = pd.Series([5.0, 10.0, 15.0, 20.0, np.nan, np.nan], index=idx)
    load = pd.Series([1.0, 2.0, 1.0, 2.0, 1.0, 2.0], index=idx)   # unrelated to the order
    out = mm.onset_correlation(btw, onset, censor_at=50.0, load=load)
    assert out["partial_onset_only"] < -0.9 and out["partial_censored"] < -0.8
    assert "rho_btw_load" in out
    few = mm.onset_correlation(btw, pd.Series([5.0] + [np.nan] * 5, index=idx), censor_at=50.0)
    assert np.isnan(few["rho_onset_only"]) and np.isnan(few["p_onset_only"])


def test_partial_spearman_several_controls_and_edge_cases():
    rng = np.random.default_rng(2)
    n = 400
    lanes = rng.integers(1, 4, n).astype(float)
    load = rng.normal(0, 1, n)
    onset = -2.0 * load + 3.0 * lanes + rng.normal(0, 0.5, n)      # load and lanes drive onset
    btw = (np.exp(load) / lanes) * np.exp(rng.normal(0, 0.1, n))   # per lane: carries both
    r1, _ = mm.partial_spearman(btw, onset, load)
    assert r1 < -0.3                                  # load alone leaves the lane-count link
    r2, p2 = mm.partial_spearman(btw, onset, np.column_stack([load, lanes]))
    assert abs(r2) < abs(r1)                          # removing lanes too weakens it
    # exact: the partial Pearson correlation of the ranks, from the inverse correlation matrix
    R = np.column_stack([pd.Series(v).rank().to_numpy() for v in (btw, onset, load, lanes)])
    P = np.linalg.inv(np.corrcoef(R, rowvar=False))
    assert r2 == pytest.approx(-P[0, 1] / np.sqrt(P[0, 0] * P[1, 1]), abs=1e-10)
    t = r2 * np.sqrt((n - 4) / (1 - r2 ** 2))
    assert p2 == pytest.approx(2 * __import__("scipy").stats.t.sf(abs(t), n - 4), rel=1e-9)
    # edge cases: a residual that is constant, and too few points for the degrees of freedom
    assert np.isnan(mm.partial_spearman([1, 2, 3, 4], [1, 2, 3, 4], [1, 2, 3, 4])[0])
    r, p = mm.partial_spearman([1, 2, 3], [3, 1, 2], [1, 3, 2])
    assert np.isnan(p)
    with pytest.raises(ValueError):
        mm.partial_spearman([1.0, np.nan, 3.0, 4.0], [1, 2, 3, 4], [4, 3, 2, 1])


def test_free_flow_time_rejects_non_positive_speed():
    net = make_net()
    v = pd.Series(10.0, index=net.edges.index)
    v["AB"] = 0.0
    with pytest.raises(ValueError):
        mm.free_flow_time(net.edges, v)


def test_onset_correlation_load_and_lanes():
    idx = [f"e{i}" for i in range(8)]
    btw = pd.Series([0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2], index=idx)
    onset = pd.Series([5.0, 10.0, 15.0, 20.0, 25.0, np.nan, np.nan, np.nan], index=idx)
    load = pd.Series([2.0, 1.0, 2.0, 1.0, 2.0, 1.0, 2.0, 1.0], index=idx)
    lanes = pd.Series([1, 2, 1, 2, 1, 2, 1, 2], index=idx)
    out = mm.onset_correlation(btw, onset, censor_at=50.0, load=load, lanes=lanes)
    for k in ("partial_load_lanes_onset_only", "partial_load_lanes_censored", "p_partial_load_lanes_censored"):
        assert k in out
    with pytest.raises(ValueError):
        mm.onset_correlation(btw, onset, censor_at=50.0, load=load.drop("e0"))


# ---------------------------------------------------------------- proposed sweep output

def test_city_sweep_queue_output_flag_is_opt_in():
    import importlib.util
    from types import SimpleNamespace
    from traffic_project import ROOT, config
    spec = importlib.util.spec_from_file_location("city_sweep", ROOT / "scripts" / "city_sweep.py")
    cs = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cs)
    cs.CTX["net_path"] = ROOT / "scenarios" / "city" / "bugis_all.net.xml"
    args = dict(densities=None, seeds=None, end_s=None, warmup_s=None, block_s=None, jobs=None,
                prefix=None, name=None, verify_routes=False)
    cfg = config.load(ROOT / "configs" / "city" / "bugis_all_controller.toml")
    over, smoke = cs.apply_overrides(cfg, SimpleNamespace(**args))
    plain = cs.sumocfg_text(cfg, ROOT / "runs" / "x", 1)
    assert "queue-output" not in plain and over == {}
    assert '<output><summary-output value="summary.xml"/></output>' in plain
    cfg = config.load(ROOT / "configs" / "city" / "bugis_all_controller.toml")
    over, smoke = cs.apply_overrides(cfg, SimpleNamespace(**args, queue_output_s=90.0))
    text = cs.sumocfg_text(cfg, ROOT / "runs" / "x", 1)
    assert not smoke and over == {"run.queue_output_s": 90.0}
    assert ('<queue-output value="queue90.xml.gz"/><queue-output.aggregation value="90"/>' in text)
    assert text.replace('<queue-output value="queue90.xml.gz"/><queue-output.aggregation value="90"/>', "") == plain
