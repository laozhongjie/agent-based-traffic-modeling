"""Hand-built cases with known answers for traffic_project.congestion.

The test net has three nodes A - B - C and four edges: AB (100 m, 2 lanes), BA (100 m),
BC (200 m), CB (200 m), all 10 m/s. Lane length 200 + 100 + 200 + 200 = 700 m,
road length 600 m. Lane connections: AB -> BC, CB -> BA (straight on) and the U-turns
AB -> BA, BC -> CB, CB -> BC, BA -> AB.
"""
import numpy as np
import pandas as pd
import pytest

from traffic_project import congestion as cg

EDGES = ("AB", "BA", "BC", "CB")


def write_net(path):
    lanes = {"AB": 2, "BA": 1, "BC": 1, "CB": 1}
    length = {"AB": 100, "BA": 100, "BC": 200, "CB": 200}
    ends = {"AB": ("A", "B"), "BA": ("B", "A"), "BC": ("B", "C"), "CB": ("C", "B")}
    xml = ['<net>']
    for e in EDGES:
        xml.append(f'  <edge id="{e}" from="{ends[e][0]}" to="{ends[e][1]}">')
        xml += [f'    <lane id="{e}_{i}" index="{i}" speed="10.00" length="{length[e]}"/>'
                for i in range(lanes[e])]
        xml.append('  </edge>')
    xml.append('  <edge id=":B_0" function="internal"><lane id=":B_0_0" speed="5" length="3"/></edge>')
    xml.append('  <tlLogic id="B" type="static"><phase duration="30"/><phase duration="3"/>'
               '<phase duration="27"/></tlLogic>')
    xml.append('  <tlLogic id="X" type="static"><phase duration="45"/></tlLogic>')
    for a, b in [("AB", "BC"), ("CB", "BA"), ("AB", "BA"), ("BC", "CB"), ("CB", "BC"),
                 ("BA", "AB"), (":B_0", "BC")]:
        xml.append(f'  <connection from="{a}" to="{b}" fromLane="0" toLane="0"/>')
    xml.append('</net>')
    path.write_text("\n".join(xml))
    return path


def write_edgedata(path, intervals, period=60):
    """intervals: list of {edge: (sampledSeconds, speed or None, occupancy %, left)}."""
    xml = ['<meandata>']
    for i, rows in enumerate(intervals):
        xml.append(f'  <interval begin="{i * period:.2f}" end="{(i + 1) * period:.2f}" id="x">')
        for e, (s, v, occ, left) in rows.items():
            extra = "" if v is None else f' speed="{v}" occupancy="{occ}"'
            xml.append(f'    <edge id="{e}" sampledSeconds="{s}" left="{left}"{extra}/>')
        xml.append('  </interval>')
    xml.append('</meandata>')
    path.write_text("\n".join(xml))
    return path


@pytest.fixture
def net(tmp_path):
    return cg.read_net(write_net(tmp_path / "t.net.xml"))


def edge_pairs(net, adj):
    names = list(net.edges.index)
    return {(names[i], names[j]) for i, j in adj}


def test_read_net_and_cycle(net):
    assert list(net.edges.index) == list(EDGES)          # internal edge skipped
    assert net.edges.at["AB", "lanes"] == 2
    assert cg.cycle_period(net, "cycle") == 60            # longest of 60 s and 45 s
    assert cg.cycle_period(net, 90) == 90.0
    assert ('AB', 'BC') in net.connections and (":B_0", "BC") not in net.connections


def test_uturn_pairs_not_adjacent(net):
    directed = edge_pairs(net, cg.edge_adjacency(net, "directed"))
    assert directed == {("AB", "BC"), ("CB", "BA")}
    # AB and its U-turn BA congested: two clusters (directed), one (junction)
    state = np.array([1, 1, 0, 0])
    L = cg.edge_weights(net.edges)
    assert len(cg.clusters(state, cg.edge_adjacency(net, "directed"), L)) == 2
    assert len(cg.clusters(state, cg.edge_adjacency(net, "junction"), L)) == 1


def test_empty_interval_is_free(net, tmp_path):
    f = write_edgedata(tmp_path / "e.xml", [
        {"AB": (0, None, 0, 0), "BA": (30, 1.0, 50, 2), "BC": (30, 9.0, 5, 2), "CB": (30, 9, 5, 2)}])
    df = cg.read_edgedata(f)
    assert np.isnan(df.set_index("edge").at["AB", "speed"])
    vref = pd.Series(10.0, index=net.edges.index)
    state = cg.classify(cg.relative_speed(df, vref), r_on=0.5, persist_m=1)
    assert state.loc[0.0].tolist() == [0, 1, 0, 0]


def test_state_flips_only_after_two_intervals():
    r = pd.DataFrame({"e": [0.3, 0.6, 0.3, 0.3, 0.6, 0.6, np.nan, np.nan]})
    assert cg.classify(r, r_on=0.5, persist_m=2)["e"].tolist() == [0, 0, 0, 1, 1, 0, 0, 0]
    assert cg.classify(r, r_on=0.5, persist_m=1)["e"].tolist() == [1, 0, 1, 1, 0, 0, 0, 0]


def test_g1_weighted_by_lane_length_and_phi_veh_differs(net, tmp_path):
    # AB and BC congested and connected (AB -> BC). AB holds most vehicle-time.
    f = write_edgedata(tmp_path / "e.xml", [
        {"AB": (90, 1.0, 60, 0), "BA": (10, 9.0, 5, 1), "BC": (10, 1.0, 60, 0), "CB": (10, 9.0, 5, 1)}])
    df = cg.read_edgedata(f)
    vref = pd.Series(10.0, index=net.edges.index)
    state = cg.classify(cg.relative_speed(df, vref), r_on=0.5, persist_m=1)
    adj = cg.edge_adjacency(net, "directed")
    lane = cg.order_parameters(state, df, net.edges, adj, "lane_length").iloc[0]
    road = cg.order_parameters(state, df, net.edges, adj, "road_length").iloc[0]
    assert lane.G1 == pytest.approx(400 / 700) and lane.phi_len == pytest.approx(400 / 700)
    assert road.G1 == pytest.approx(300 / 600)
    assert lane.G2 == 0 and lane.n_clusters == 1
    assert lane.phi_veh == pytest.approx(100 / 120)
    assert lane.phi_veh != pytest.approx(lane.phi_len)


def test_free_flow_reference_fallback(net, tmp_path):
    # AB sampled 100 s at 4 m/s, BA 100 s at 6 m/s, BC only 30 s, CB never.
    f = write_edgedata(tmp_path / "ref.xml", [
        {"AB": (50, 4.0, 1, 1), "BA": (50, 6.0, 1, 1), "BC": (30, 8.0, 1, 1), "CB": (0, None, 0, 0)},
        {"AB": (50, 4.0, 1, 1), "BA": (50, 6.0, 1, 1), "BC": (0, None, 0, 0), "CB": (0, None, 0, 0)}])
    df = cg.read_edgedata(f)
    vref, info = cg.free_flow_reference(df, net.edges, warmup_s=0, min_sampled_s=60)
    assert vref.tolist() == pytest.approx([4.0, 6.0, 5.0, 5.0])   # median ratio 0.5 x 10
    assert info == {"coverage": 0.5, "n_fallback": 2}
    vref0, info0 = cg.free_flow_reference(df, net.edges, warmup_s=0, min_sampled_s=0)
    assert vref0["BC"] == 8.0 and info0["n_fallback"] == 1


def test_merge_intervals_weighted_and_aligned(tmp_path):
    f = write_edgedata(tmp_path / "e.xml", [
        {"AB": (10, 2.0, 40, 1)}, {"AB": (30, 6.0, 20, 3)},
        {"AB": (0, None, 0, 0)}, {"AB": (20, 4.0, 10, 2)}, {"AB": (5, 1.0, 10, 0)}], period=90)
    m = cg.merge_intervals(cg.read_edgedata(f), 2)
    assert m.begin.tolist() == [0.0, 180.0]               # trailing half interval dropped
    assert m.speed.tolist() == pytest.approx([(20 + 180) / 40, 4.0])
    assert m.sampledSeconds.tolist() == [40, 20] and m.left.tolist() == [4, 2]
    assert m.occupancy.tolist() == pytest.approx([30, 5])


def test_spillback_gridlock_onset():
    state = pd.DataFrame({"e": [1, 1, 1, 1]})
    occ = pd.DataFrame({"e": [70.0, 70.0, 10.0, np.nan]})
    sp = cg.spillback(state, occ, occ_jam=5 / 7, occ_frac=0.8, persist_m=1)
    assert sp["e"].tolist() == [1, 1, 0, 0] and cg.onsets(sp) == 0
    assert cg.gridlock([100, 0, 0, 0, 5, 0], free_outflow=100, frac=0.01, cycles=3).tolist() == \
        [False, False, False, True, False, False]
    shares = pd.DataFrame({"a": [0.0, 0.6, 0.9], "b": [0.0, 0.1, 0.2]}, index=[30.0, 10.0, 20.0])
    on = cg.onset_density(shares)
    assert on["a"] == 10.0 and np.isnan(on["b"])


def test_edgedata_additional():
    txt = cg.edgedata_additional(90, "edge90.xml.gz")
    assert 'period="90"' in txt and 'excludeEmpty="false"' in txt and "sampledSeconds" in txt
