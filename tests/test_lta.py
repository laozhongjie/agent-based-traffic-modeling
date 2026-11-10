"""Tests of the SUMO edge <-> LTA road-stretch lookup (traffic_project.lta, task 2).

The matcher tests build a tiny left-hand net with netconvert: a straight two-way road
"Test Avenue 4" (two 200 m blocks, one edge per direction per block) and a one-way side
street. LTA links are written as lon/lat by converting net x, y back to WGS84.
"""
import json
import math
import shutil
import subprocess

import pandas as pd
import pytest

from traffic_project import lta

from conftest import needs_sumo

needs_netconvert = pytest.mark.skipif(shutil.which("netconvert") is None, reason="netconvert not on PATH")


def test_norm_name_expands_abbreviations():
    assert lta.norm_name("Ang Mo Kio Ave 4") == lta.norm_name("ANG MO KIO AVENUE 4")
    assert lta.name_agreement("Ang Mo Kio Ave 4", "ANG MO KIO AVENUE 4") == "exact"


def test_norm_name_handles_apostrophes_and_xml_entities():
    # sumolib returns names with XML entities; LTA drops the apostrophe
    assert lta.norm_name("King George&apos;s Avenue") == lta.norm_name("KING GEORGES AVENUE")
    assert lta.name_agreement("", "Middle Road") == "missing"
    assert lta.name_agreement("Ang Mo Kio Ave 4", "Ang Mo Kio Avenue 3") == "partial"
    assert lta.name_agreement("Middle Road", "Bencoolen Street") == "none"


def test_category_code_maps_v3_letters_in_order():
    assert [lta.category_code(c) for c in "ABCDEF"] == [1, 2, 3, 4, 5, 6]
    assert lta.category_code("2") == 2 and lta.category_code(3) == 3


def test_twin_pairs_finds_swapped_end_points():
    links = pd.DataFrame([dict(LinkID="1", StartLon=103.0, StartLat=1.0, EndLon=103.001, EndLat=1.0),
                          dict(LinkID="2", StartLon=103.001, StartLat=1.0, EndLon=103.0, EndLat=1.0),
                          dict(LinkID="3", StartLon=103.001, StartLat=1.0, EndLon=103.002, EndLat=1.0)])
    assert lta.twin_pairs(links) == [("1", "2")]


def test_in_box_keeps_links_with_an_end_inside():
    links = pd.DataFrame([dict(StartLon=0.5, StartLat=0.5, EndLon=2.0, EndLat=2.0),   # start inside
                          dict(StartLon=2.0, StartLat=2.0, EndLon=0.5, EndLat=0.5),   # end inside
                          dict(StartLon=2.0, StartLat=2.0, EndLon=3.0, EndLat=3.0)])  # outside
    assert lta.in_box(links, (0, 0, 1, 1)).tolist() == [True, True, False]


def test_aggregate_to_edges_weights_by_frac_of_edge():
    lookup = pd.DataFrame([dict(lta_link_id="1", sumo_edge_id="e", method="A_endpoint_path", frac_of_edge=0.75, kept=True),
                           dict(lta_link_id="2", sumo_edge_id="e", method="A_endpoint_path", frac_of_edge=0.25, kept=True),
                           dict(lta_link_id="2", sumo_edge_id="f", method="B_buffer_overlap", frac_of_edge=1.0, kept=True)])
    vals = pd.DataFrame(dict(lta_link_id=["1", "2"], value=[1.0, 0.0]))
    out = lta.aggregate_to_edges(lookup, vals)
    assert out.sumo_edge_id.tolist() == ["e"]
    assert out.value.iloc[0] == pytest.approx(0.75)
    assert out.coverage.iloc[0] == pytest.approx(1.0) and out.n_links.iloc[0] == 2


@pytest.fixture(scope="module")
def tiny(tmp_path_factory):
    """(net path, LTA links DataFrame) for a tiny two-way main road plus a one-way side street."""
    if shutil.which("netconvert") is None or "SUMO_HOME" not in __import__("os").environ:
        pytest.skip("netconvert or SUMO_HOME missing")
    d = tmp_path_factory.mktemp("lta_net")
    # nodes in lon/lat near Bugis; 200 m of longitude at latitude 1.3 deg is 0.0017971 deg
    dlon, dlat = 200 / 111290.0, 200 / 110574.0
    xy = dict(a=(0, 0), b=(1, 0), c=(2, 0), s=(1, 1))
    (d / "n.nod.xml").write_text("<nodes>" + "".join(
        f'<node id="{k}" x="{103.85 + i * dlon:.7f}" y="{1.30 + j * dlat:.7f}"/>' for k, (i, j) in xy.items())
        + "</nodes>")
    (d / "e.edg.xml").write_text(
        '<edges>'
        '<edge id="ab" from="a" to="b" numLanes="1" speed="13.89" name="Test Avenue 4"/>'
        '<edge id="ba" from="b" to="a" numLanes="1" speed="13.89" name="Test Avenue 4"/>'
        '<edge id="bc" from="b" to="c" numLanes="1" speed="13.89" name="Test Avenue 4"/>'
        '<edge id="cb" from="c" to="b" numLanes="1" speed="13.89" name="Test Avenue 4"/>'
        '<edge id="sb" from="s" to="b" numLanes="1" speed="13.89" name="Side Street"/>'
        '</edges>')
    net = d / "t.net.xml"
    # UTM projection with the offset normalised to node a = (0, 0), as for the city nets
    subprocess.run(["netconvert", "-n", str(d / "n.nod.xml"), "-e", str(d / "e.edg.xml"), "--lefthand",
                    "--proj.utm", "--output.street-names", "-o", str(net)], check=True, capture_output=True)
    sumolib = lta.import_sumolib()
    n = sumolib.net.readNet(str(net))

    def ll(x, y):
        return n.convertXY2LonLat(x, y)

    def link(i, name, cat, p, q):
        (slon, slat), (elon, elat) = ll(*p), ll(*q)
        return dict(LinkID=str(i), RoadName=name, RoadCategory=cat, StartLon=slon, StartLat=slat,
                    EndLon=elon, EndLat=elat)
    # LTA puts both directions of a two-way road on one centreline; netconvert offsets the
    # two edges by half a lane width each side, so both LTA twins sit on the centreline y = 0.
    rows = [link(1, "TEST AVE 4", "B", (60, 0), (340, 0)),     # eastbound, spans both blocks
            link(2, "TEST AVE 4", "B", (340, 0), (60, 0)),     # its westbound twin
            link(3, "SIDE STREET", "E", (200, 150), (200, 60)),  # with the one-way street
            link(4, "SIDE STREET", "E", (200, 60), (200, 150)),  # against the one-way street
            link(5, "NO SUCH ROAD", "E", (100, 150), (100, 120))]  # off the network
    return net, lta.links_from_rows(rows)


@needs_sumo
@needs_netconvert
def test_matcher_on_tiny_net(tiny):
    net, links = tiny
    p = lta.MatchParams(radius=25, max_angle=45, detour=1.5, buffer=15, min_frac=0.5, margin=0)
    pairs, lt, names = lta.match_links(net, links, p, "unit-test", "v4")
    lt = lt.set_index("lta_link_id")
    a = pairs[pairs.method == "A_endpoint_path"]
    # direction: twins go to disjoint edge sets, each in its own direction of travel
    assert set(a[a.lta_link_id == "1"].sumo_edge_id) == {"ab", "bc"}
    assert set(a[a.lta_link_id == "2"].sumo_edge_id) == {"cb", "ba"}
    # weights: frac_of_lta sums to 1 within 0.95-1.05 for every link matched by A
    sums = a.groupby("lta_link_id").frac_of_lta.sum()
    assert ((sums >= 0.95) & (sums <= 1.05)).all()
    assert math.isclose(a[(a.lta_link_id == "1") & (a.sumo_edge_id == "ab")].frac_of_edge.iloc[0], 0.7, abs_tol=0.05)
    # one-way street: matched with the flow, refused against it
    assert lt.loc["3", "a_matched"] and not lt.loc["4", "a_matched"]
    assert lt.loc["4", "qa_flag"].startswith("in-net-missed")
    assert lt.loc["5", "qa_flag"] == "absent-from-net"
    assert lt.loc["1", "a_name_exact"] and lt.loc["1", "confidence"] == "high"
    # left-hand traffic: each carriageway lies left of its LTA vector
    assert lt.loc["1", "a_side"] == "left" and lt.loc["2", "a_side"] == "left"
    assert bool(lt.valid_for_results.iloc[0]) and len(lt.sumo_net_sha256.iloc[0]) == 64
    checks = lta.run_checks(pairs, lt.reset_index(), links, judge_coverage=True)
    assert checks["1_direction_twins_disjoint"]["passed"] is True
    assert checks["1_direction_twins_disjoint"]["n_twin_pairs"] == 2
    assert checks["3_side_left_majority_twins"]["passed"] is True
    assert list(lta.missing_roads(lt.reset_index()).lta_road_name) == ["NO SUCH ROAD"]


@needs_sumo
@needs_netconvert
def test_prototype_source_is_never_valid_for_results(tiny):
    net, links = tiny
    _, lt, _ = lta.match_links(net, links.head(1), lta.MatchParams(margin=0), "v3-snapshot-2024-PROTOTYPE", "v3")
    assert not lt.valid_for_results.any()


def test_load_links_reads_api_json(tmp_path):
    f = tmp_path / "sb.json"
    f.write_text(json.dumps({"value": [dict(LinkID=7, RoadName="X RD", RoadCategory="2", SpeedBand=3,
                                            StartLon="103.8", StartLat="1.3", EndLon="103.81", EndLat="1.3")] * 2}))
    df = lta.load_links(f)
    assert len(df) == 1 and df.LinkID.iloc[0] == "7" and df.StartLon.dtype == float and "SpeedBand" in df


@pytest.fixture(scope="module")
def cleaned(tmp_path_factory):
    """(stage-1 net, cleaned net, kept edge IDs): the tiny net's roads plus an isolated one-way
    "Lost Lane" that the cleaned net drops, as task 1's strong-component pass drops roads."""
    if shutil.which("netconvert") is None or "SUMO_HOME" not in __import__("os").environ:
        pytest.skip("netconvert or SUMO_HOME missing")
    d = tmp_path_factory.mktemp("lta_clean")
    dlon, dlat = 200 / 111290.0, 200 / 110574.0
    xy = dict(a=(0, 0), b=(1, 0), c=(2, 0), s=(1, 1), m=(0.5, 0.75), q=(0.5, 0.25))
    (d / "n.nod.xml").write_text("<nodes>" + "".join(
        f'<node id="{k}" x="{103.85 + i * dlon:.7f}" y="{1.30 + j * dlat:.7f}"/>' for k, (i, j) in xy.items())
        + "</nodes>")
    (d / "e.edg.xml").write_text(
        '<edges>'
        '<edge id="ab" from="a" to="b" numLanes="1" speed="13.89" name="Test Avenue 4"/>'
        '<edge id="ba" from="b" to="a" numLanes="1" speed="13.89" name="Test Avenue 4"/>'
        '<edge id="bc" from="b" to="c" numLanes="1" speed="13.89" name="Test Avenue 4"/>'
        '<edge id="cb" from="c" to="b" numLanes="1" speed="13.89" name="Test Avenue 4"/>'
        '<edge id="sb" from="s" to="b" numLanes="1" speed="13.89" name="Side Street"/>'
        '<edge id="mq" from="m" to="q" numLanes="1" speed="13.89" name="Lost Lane"/>'
        '</edges>')
    stage1, clean, kept = d / "stage1.net.xml", d / "clean.net.xml", ["ab", "ba", "bc", "cb", "sb"]
    subprocess.run(["netconvert", "-n", str(d / "n.nod.xml"), "-e", str(d / "e.edg.xml"), "--lefthand",
                    "--proj.utm", "--output.street-names", "-o", str(stage1)], check=True, capture_output=True)
    subprocess.run(["netconvert", "-s", str(stage1), "--keep-edges.explicit", ",".join(kept), "-o", str(clean)],
                   check=True, capture_output=True)
    return stage1, clean, kept


@needs_sumo
@needs_netconvert
def test_assign_causes_names_why_a_link_is_not_placed(cleaned):
    stage1, clean, kept = cleaned
    n = lta.import_sumolib().net.readNet(str(clean))

    def link(i, name, cat, p, q):
        (slon, slat), (elon, elat) = n.convertXY2LonLat(*p), n.convertXY2LonLat(*q)
        return dict(LinkID=str(i), RoadName=name, RoadCategory=cat, StartLon=slon, StartLat=slat,
                    EndLon=elon, EndLat=elat)
    # the main road's two edges run at y = +1.7 (eastbound) and -1.5 (westbound); stretches sit at y = 0.5
    links = lta.links_from_rows([
        link(1, "TEST AVE 4", "B", (60, 0.5), (340, 0.5)),        # placed on ab and bc
        link(2, "LOST LANE", "E", (100, 140), (100, 60)),         # on the road the cleaning removed
        link(3, "NO SUCH ROAD", "E", (300, 150), (300, 120)),     # no edge carries its name
        link(4, "SIDE STREET", "E", (200, 60), (200, 150)),       # against the one-way side street
        link(5, "TEST AVE 4", "B", (60, 5), (60, 20)),            # across the main road, 90 degrees off
        link(6, "TEST AVE 4", "B", (198, 0.5), (202, 0.5)),       # inside junction b, between ab and bc
        link(7, "TEST AVE 4", "B", (300, 0.5), (300.4, 0.5)),     # under 1 m
        link(8, "TEST EXPRESSWAY", "A", (80, 0.5), (180, 0.5)),   # an expressway above the main road
        link(9, "TEST AVE 4", "B", (1000, 0.5), (1100, 0.5))])    # beyond the net
    p = lta.MatchParams(margin=0)
    pairs, lt, _ = lta.match_links(clean, links, p, "unit-test", "v4")
    full = lta.assign_causes(clean, links, lt, pairs, p, stage1, kept)
    assert list(full.lta_link_id) == [str(i) for i in range(1, 10)]
    assert dict(zip(full.lta_link_id, full.cause)) == {
        "1": "", "2": "removed-by-cleaning", "3": "road-not-in-net", "4": "opposite-direction-only",
        "5": "direction-test-failed", "6": "no-length-on-edge", "7": "too-short", "8": "expressway",
        "9": "outside-net"}
    assert full.tried.tolist() == [True] * 8 + [False]
    assert full.a_matched.iloc[5] and full.a_matched.iloc[7]   # matched by A, yet not placed
    # without the stage-1 net, the removed road's stretch takes its next cause
    assert lta.assign_causes(clean, links, lt, pairs, p).cause.iloc[1] == "road-not-in-net"
    # a stage-1 net whose kept edges are not this net's edges is refused
    with pytest.raises(ValueError):
        lta.assign_causes(clean, links, lt, pairs, p, stage1, kept[:-1])
