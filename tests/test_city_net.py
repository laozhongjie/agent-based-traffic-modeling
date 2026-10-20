"""Checks on the committed city networks in scenarios/city/ (task 1).

Every configs/city/*.toml whose net is committed is tested. The tests read the
net with ElementTree and networkx only: no SUMO run and no SUMO_HOME needed.

(a) normal edges joined by <connection> elements form one strongly connected
    component, so a vehicle on any road can reach every other road and return;
(c) the net is left-hand (Singapore);
(d) every signal is fixed-time ("static") and its phases sum to tls_cycle_s;
(e) meta.json lane_length_m equals a recount of normal-lane lengths within 1 m,
    and the other recorded counts match the net.
"""
import json
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path

import networkx as nx
import pytest

from traffic_project import ROOT

CITY = ROOT / "scenarios" / "city"
CONFIGS = sorted((ROOT / "configs" / "city").glob("*.toml"))
CASES = [c for c in CONFIGS if (CITY / f"{tomllib.loads(c.read_text())['name']}.net.xml").exists()]
REMOVED_ALWAYS = ("highway.motorway", "highway.motorway_link", "highway.service")


@pytest.fixture(scope="module", params=CASES, ids=lambda p: p.stem)
def city(request):
    """(config dict, net XML root, meta dict) for one committed city network."""
    cfg = tomllib.loads(request.param.read_text())
    root = ET.parse(CITY / f"{cfg['name']}.net.xml").getroot()
    meta = json.loads((CITY / f"{cfg['name']}.meta.json").read_text())
    return cfg, root, meta


def normal_edges(root):
    return [e for e in root.iter("edge") if e.get("function") != "internal"]


def test_city_nets_exist():
    assert CASES, "no committed city net: run scenarios/city/build_net.py"


def test_one_strong_component(city):
    _, root, _ = city
    g = nx.DiGraph()
    g.add_nodes_from(e.get("id") for e in normal_edges(root))
    for c in root.iter("connection"):
        if not c.get("from").startswith(":"):
            g.add_edge(c.get("from"), c.get("to"))
    assert g.number_of_nodes() > 0
    assert nx.number_strongly_connected_components(g) == 1


def test_lefthand(city):
    _, root, meta = city
    assert root.tag == "net" and root.get("lefthand") == "true"
    assert meta["lefthand"] is True


def test_signals_fixed_time_common_cycle(city):
    cfg, root, meta = city
    tls = list(root.iter("tlLogic"))
    assert len(tls) == meta["tls_count"] > 0
    for t in tls:
        assert t.get("type") == "static", t.get("id")
        cycle = sum(float(p.get("duration")) for p in t.iter("phase"))
        assert cycle == pytest.approx(cfg["network"]["tls_cycle_s"], abs=1e-6), t.get("id")


def test_lane_length_matches_meta(city):
    _, root, meta = city
    edges = normal_edges(root)
    lanes = [lane for e in edges for lane in e.iter("lane")]
    internal = [lane for e in root.iter("edge") if e.get("function") == "internal" for lane in e.iter("lane")]
    assert abs(sum(float(lane.get("length")) for lane in lanes) - meta["lane_length_m"]) <= 1.0
    assert abs(sum(float(lane.get("length")) for lane in internal) - meta["internal_lane_length_m"]) <= 1.0
    assert (len(edges), len(lanes)) == (meta["edges_normal"], meta["lanes_normal"])
    junctions = [j for j in root.iter("junction") if j.get("type") != "internal"]
    assert len(junctions) == meta["junctions"]


def test_no_expressway_or_service_roads(city):
    _, root, _ = city
    types = {e.get("type") for e in normal_edges(root)}
    assert not types & set(REMOVED_ALWAYS)


def test_density_denominator_is_passenger_lanes(city):
    """lane_length_m (all normal lanes) must equal the passenger-lane length.

    lane_length_m sums every lane of every normal edge. If a rebuild ever keeps
    bus-only, bicycle or sidewalk lanes, that sum would exceed the road space cars
    can use and every density on the MFD x-axis would be silently too low.
    """
    _, _, meta = city
    assert abs(meta["lane_length_m"] - meta["passenger_lane_length_m"]) <= 1.0


@pytest.mark.xfail(strict=True, reason="T1-D10 (proposed): stage 2 keeps pre-trim signal plans; "
                   "netconvert --tls.rebuild removes the unused states. Remove this marker after the rebuild.")
def test_no_unused_signal_states(city):
    """Every signal state string has exactly one character per controlled link.

    The strong-component pass removes some approaches of a few signals but keeps their
    old phase strings, so some phases give green only to removed links: the remaining
    approaches wait through a dead phase of up to 42 s in a 90 s cycle.
    """
    _, root, _ = city
    used = {}
    for c in root.iter("connection"):
        if c.get("tl"):
            used[c.get("tl")] = max(used.get(c.get("tl"), 0), int(c.get("linkIndex")) + 1)
    extra = [t.get("id") for t in root.iter("tlLogic")
             if len(next(t.iter("phase")).get("state")) != used.get(t.get("id"), 0)]
    assert not extra, f"{len(extra)} signals with unused states: {extra[:3]}"
