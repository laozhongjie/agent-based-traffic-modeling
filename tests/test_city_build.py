"""Tests of the city build's OSM turn-lane handling (scenarios/city/build_net.py, T1-D13).

netconvert 1.28.0 applies OSM turn:lanes as their mirror image in a --lefthand net (lane
order reversed, left and right swapped). With [network] osm_turn_lanes = "mirror" the build
rewrites every turn:lanes, turn:lanes:forward and turn:lanes:backward value to its mirror in
a temporary copy of the tiles, so netconvert's mirroring restores the lanes as tagged.
These tests need no netconvert run; importing build_net needs SUMO_HOME (sumolib).
"""
import gzip
import importlib.util
import json
import os
import tomllib

import pytest

from traffic_project import ROOT

BUGIS = ("bugis_all", "bugis_art")
TILE = """<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
 <way id="1"><nd ref="1"/><nd ref="2"/>
  <tag k="highway" v="primary"/><tag k="name" v="Left Street"/><tag k="oneway" v="yes"/>
  <tag k="turn:lanes" v="left;through|through|through;right|right"/>
 </way>
 <way id="2"><nd ref="2"/><nd ref="3"/>
  <tag k="highway" v="secondary"/>
  <tag k="turn:lanes:forward" v="none|through|through|through"/>
  <tag k="turn:lanes:backward" v="left|through"/>
 </way>
</osm>
"""


@pytest.fixture(scope="module")
def build_net():
    if "SUMO_HOME" not in os.environ:
        pytest.skip("SUMO_HOME not set (build_net imports sumolib)")
    spec = importlib.util.spec_from_file_location("build_net", ROOT / "scenarios" / "city" / "build_net.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def write_tiles(folder, names):
    folder.mkdir()
    for name in names:
        with gzip.open(folder / name, "wt", encoding="utf-8") as f:
            f.write(TILE)
    return [folder / name for name in names]


@pytest.mark.parametrize("value, mirrored", [
    ("left|through", "through|right"),
    ("through|right", "left|through"),
    ("left;through|through|through;right|right", "left|through;left|through|right;through"),
    ("none|through|through|through", "through|through|through|none"),   # turn:lanes:forward with a none lane
    ("through|through|through", "through|through|through"),            # Nicoll Highway way 633203157
    ("through|through|through|through;right|right", "left|through;left|through|through|through"),
    ("slight_left|through|sharp_right", "sharp_left|through|slight_right"),
    ("merge_to_right|through|reverse", "reverse|through|merge_to_left"),
    ("left||", "||right"),
    ("through", "through"),
])
def test_mirror_turn_lanes(build_net, value, mirrored):
    assert build_net.mirror_turn_lanes(value) == mirrored
    assert build_net.mirror_turn_lanes(mirrored) == value   # the mirror is its own inverse


def test_mirror_tiles_rewrites_only_turn_lane_values(build_net, tmp_path):
    (raw,) = write_tiles(tmp_path / "raw", ["t0.osm.xml.gz"])
    files, n = build_net.osm_inputs({"osm_turn_lanes": "mirror"}, [raw], tmp_path)
    assert files == ["osm_turn_lanes_mirrored/t0.osm.xml.gz"] and n == 3
    with gzip.open(tmp_path / files[0], "rt", encoding="utf-8") as f:
        text = f.read()
    expected = (TILE.replace("left;through|through|through;right|right", "left|through;left|through|right;through")
                .replace("none|through|through|through", "through|through|through|none")
                .replace('"left|through"', '"through|right"'))
    assert text == expected   # name="Left Street" and every other tag unchanged
    with gzip.open(raw, "rt", encoding="utf-8") as f:
        assert f.read() == TILE   # the raw tile is never changed


def test_mirror_tiles_refuses_values_it_cannot_rewrite(build_net, tmp_path):
    folder = tmp_path / "raw"
    folder.mkdir()
    with gzip.open(folder / "t0.osm.xml.gz", "wt", encoding="utf-8") as f:
        f.write(TILE.replace('<tag k="turn:lanes" v=', "<tag k='turn:lanes' v="))
    with pytest.raises(ValueError, match="turn:lanes"):
        build_net.osm_inputs({"osm_turn_lanes": "mirror"}, [folder / "t0.osm.xml.gz"], tmp_path)


def test_turn_lane_modes(build_net):
    assert build_net.turn_lane_opts({"osm_turn_lanes": "mirror"}) == ["--osm.turn-lanes"]
    assert build_net.turn_lane_opts({"osm_turn_lanes": "as_is"}) == ["--osm.turn-lanes"]
    assert build_net.turn_lane_opts({"osm_turn_lanes": "off"}) == []
    with pytest.raises(KeyError):
        build_net.turn_lane_opts({})   # required: no silent default
    with pytest.raises(ValueError):
        build_net.turn_lane_opts({"osm_turn_lanes": True})
    # a right-hand net reads turn:lanes correctly, so the mirror would break it
    with pytest.raises(ValueError, match="right-hand"):
        build_net.turn_lane_opts({"osm_turn_lanes": "mirror"}, lefthand=False)
    assert build_net.turn_lane_opts({"osm_turn_lanes": "as_is"}, lefthand=False) == ["--osm.turn-lanes"]


@pytest.mark.parametrize("name", BUGIS)
def test_bugis_stage1_imports_mirrored_turn_lanes(build_net, name, tmp_path):
    net = tomllib.loads((ROOT / "configs" / "city" / f"{name}.toml").read_text())["network"]
    assert net["osm_turn_lanes"] == "mirror"   # T1-D13 option B
    tiles = write_tiles(tmp_path / "raw", net["osm_files"])
    work = tmp_path / "work"
    work.mkdir()
    args, n = build_net.stage1_args(net, tiles, work)
    assert "--osm.turn-lanes" in args and "--lefthand" in args
    files = args[args.index("--osm-files") + 1].split(",")
    assert files == [f"osm_turn_lanes_mirrored/{t}" for t in net["osm_files"]]
    assert all((work / f).exists() for f in files) and n == 3 * len(files)


@pytest.mark.parametrize("name", BUGIS)
def test_committed_bugis_nets_were_built_from_mirrored_tiles(name):
    meta = json.loads((ROOT / "scenarios" / "city" / f"{name}.meta.json").read_text())
    assert meta["osm_turn_lanes"] == "mirror"
    assert meta["osm_turn_lanes_mirrored_values"] > 0
    s1 = meta["netconvert_stage1"].split()
    assert "--osm.turn-lanes" in s1
    assert s1[s1.index("--osm-files") + 1].split(",") == [f"osm_turn_lanes_mirrored/{t}" for t in meta["osm_sha256"]]
