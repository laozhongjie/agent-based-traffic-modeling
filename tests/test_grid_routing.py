"""The grid's run rules (T4-D1 routing, T3-D11 teleports): scenarios/grid/build_run.py writes
one-edge start routes and a sumocfg with the rerouting device and the teleport time, and
scripts/grid_sweep.py runs the constant-density controller (traffic_project.demand) on the
grid nets, which are built without internal junction lanes.
"""
import importlib.util
import re
import shutil
import xml.etree.ElementTree as ET

import pytest

from traffic_project import ROOT, config, demand, runner
from conftest import needs_sumo

VARIANTS = ("base", "closure", "newlink")


def _script(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _cfg():
    return config.load(ROOT / "configs" / "validation" / "grid_smoke.toml")


def _net(variant):
    return ROOT / "scenarios" / "grid" / f"grid4x4_L200_{variant}.net.xml"


@pytest.fixture
def build_run(tmp_path, monkeypatch):
    """build_run.py writing into tmp_path/runs/, with the grid nets copied to tmp_path."""
    mod = _script("build_run", "scenarios/grid/build_run.py")
    (tmp_path / "scenarios" / "grid").mkdir(parents=True)
    for v in VARIANTS:
        shutil.copy(_net(v), tmp_path / "scenarios" / "grid")
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    return mod


@pytest.mark.parametrize("variant", VARIANTS)
def test_grid_nets_meet_the_controller_assumptions(variant):
    """No internal lanes, every car edge reachable from every other one (uniform destinations),
    and every edge longer than guard_m, so a near set holds only the destination itself and
    is exact (near_sets ignores internal lanes, of which these nets have none)."""
    cfg = _cfg()
    net = _net(variant)
    assert not [e for e in ET.parse(net).getroot().iter("edge") if e.get("function") == "internal"]
    gs = _script("grid_sweep", "scripts/grid_sweep.py")
    routing = gs.net_routing(cfg, variant)
    lanes = demand.car_lanes(net)
    assert routing["dests"] == sorted(e for e, *_ in lanes)
    assert demand.outside_largest_scc(demand.car_successors(net)) == []
    assert min(length for _, length, _ in lanes) > cfg["controller"]["guard_m"]
    assert all(s == {d} for d, s in routing["near"].items())


def test_check_config():
    gs = _script("grid_sweep", "scripts/grid_sweep.py")
    gs.check_config(_cfg())                                   # the smoke config passes
    cfg = _cfg()
    cfg["run"]["step_s"] = 2.0                                # 30 m/s x 2 s = 60 m: not < guard_m
    with pytest.raises(SystemExit, match="guard_m"):
        gs.check_config(cfg)
    cfg = _cfg()
    cfg["controller"]["destination"] = "od_matrix"
    with pytest.raises(SystemExit, match="uniform_edge"):
        gs.check_config(cfg)


def test_build_run_writes_one_edge_routes_rerouting_and_teleport_time(build_run):
    cfg = _cfg()
    run_id, run_dir = build_run.build(cfg, "closure", 100, 1)
    assert run_id == "grid4_idm_closure_n100_s1"
    routes = re.findall(r'<route edges="([^"]*)"/>', (run_dir / "vehicles.rou.xml").read_text())
    car_edges = {e for e, *_ in demand.car_lanes(_net("closure"))}
    assert len(routes) == 100 and all(r in car_edges for r in routes)   # one edge each
    opts = {el.tag: el.get("value") for el in ET.parse(run_dir / "run.sumocfg").getroot().iter()}
    assert opts["time-to-teleport"] == "300"
    assert (opts["device.rerouting.probability"], opts["device.rerouting.period"],
            opts["device.rerouting.adaptation-interval"], opts["device.rerouting.adaptation-steps"]) == \
           ("1", "60", "10", "18")
    cfg["run"]["allow_teleport"] = False
    _, run_dir = build_run.build(cfg, "closure", 100, 1)
    opts = {el.tag: el.get("value") for el in ET.parse(run_dir / "run.sumocfg").getroot().iter()}
    assert opts["time-to-teleport"] == "-1"


@needs_sumo
@pytest.mark.parametrize("n, ttt", [(150, 300), (600, 30)])
def test_controller_keeps_n_exact_on_the_grid(build_run, n, ttt):
    """150 cars on the base grid for 300 s; and 600 cars teleported after 30 s, so the run has
    many teleports. N stays exact every step, no car arrives, every car has the rerouting
    device, cars get new destinations during the run, and the teleports match SUMO's log."""
    cfg = _cfg()
    cfg["run"].update(end_s=300, warmup_s=100, time_to_teleport_s=ttt)
    _, run_dir = build_run.build(cfg, "base", n, 1)
    gs = _script("grid_sweep", "scripts/grid_sweep.py")
    routing, c = gs.net_routing(cfg, "base"), cfg["controller"]
    ctl = demand.ConstantDensity(n, routing["dests"], 1 + c["seed_offset"], c["retarget_at_remaining_edges"],
                                 near=routing["near"], step_s=cfg["run"]["step_s"])
    device, ends = {}, {f"v{i}": set() for i in range(0, n, 10)}

    def controller(conn, t):
        ctl(conn, t)
        if t == 2:
            device.update({v: conn.vehicle.getParameter(v, "has.rerouting.device") for v in ends})
        if t % 10 == 0:
            for v in ends:
                ends[v].add(conn.vehicle.getRoute(v)[-1])

    log, checks = runner.run_traci(run_dir, controller, allow_teleport=True)
    assert checks == {"sumo_exit_ok": True, "no_collision": True}
    cols, ctl_checks = gs.controller_outputs(cfg, run_dir, ctl, log, wall_s=0.0)
    rec = ctl.record()
    assert ctl_checks == {"n_exact_every_step": True, "teleports_match_log": True}
    assert rec["arrived"] == 0 and rec["reinserted"] == 0 and rec["retarget_failed"] == 0
    assert cols["grid_n_min"] == cols["grid_n_max"] == n and all(k.startswith("grid_") for k in cols)
    assert set(device.values()) == {"true"}
    assert rec["retargets"] > n                                  # beyond the one at departure
    assert sum(len(d) > 1 for d in ends.values()) > len(ends) / 2   # most cars changed destination
    if ttt == 30:
        assert cols["grid_teleports"] == demand.teleport_count(log) > 0
    assert (run_dir / "controller.json").exists()
