"""The grid's run rules (T4-D1 routing, T3-D11 teleports): scenarios/grid/build_run.py writes
one-edge start routes and a sumocfg with the rerouting device and the teleport time, and
scripts/grid_sweep.py runs the constant-density controller (traffic_project.demand) on the
grid nets, which are built without internal junction lanes. Destinations on every variant are
the base grid's car edges that the variant still has (T4-D2).
"""
import contextlib
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import types
import xml.etree.ElementTree as ET

import pytest

from traffic_project import ROOT, config, demand, results, runner
from conftest import needs_sumo

if "SUMO_HOME" in os.environ:   # demand imports sumolib and traci from $SUMO_HOME/tools, as runner.run_traci does
    runner._import_traci()

VARIANTS = ("base", "closure", "newlink")
# The base grid's 48 car edges: one each way between neighbouring junctions n<i>_<j> of the 4x4 grid
GRID_EDGES = {f"n{i}_{j}-n{k}_{l}" for i in range(4) for j in range(4)
              for k, l in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)) if 0 <= k < 4 and 0 <= l < 4}
# T4-D2 on each variant: (number of destinations, base edges the variant lacks, its new edges)
DESTINATIONS = {"base": (48, set(), set()),
                "closure": (46, {"n1_1-n1_2", "n1_2-n1_1"}, set()),
                "newlink": (48, set(), {"n1_1-n2_2", "n2_2-n1_1"})}


def _script(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _cfg():
    return config.load(ROOT / "configs" / "validation" / "grid_smoke.toml")


def _net(variant):
    return ROOT / "scenarios" / "grid" / f"grid4x4_L200_{variant}.net.xml"


def _meta(variant):
    return json.loads((ROOT / "scenarios" / "grid" / f"grid4x4_L200_{variant}.meta.json").read_text())


@pytest.fixture
def build_run(tmp_path, monkeypatch):
    """build_run.py writing into tmp_path/runs/, with the grid nets and their meta.json copied to tmp_path."""
    mod = _script("build_run", "scenarios/grid/build_run.py")
    (tmp_path / "scenarios" / "grid").mkdir(parents=True)
    for v in VARIANTS:
        shutil.copy(_net(v), tmp_path / "scenarios" / "grid")
        shutil.copy(_net(v).with_name(f"grid4x4_L200_{v}.meta.json"), tmp_path / "scenarios" / "grid")
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    return mod


@pytest.mark.parametrize("variant", VARIANTS)
def test_grid_nets_meet_the_controller_assumptions(variant):
    """No internal lanes, destinations from the base grid (T4-D2), every car edge reachable from every other one,
    and every edge longer than guard_m, so a near set holds only the destination itself and
    is exact (near_sets ignores internal lanes, of which these nets have none)."""
    cfg = _cfg()
    net = _net(variant)
    assert not [e for e in ET.parse(net).getroot().iter("edge") if e.get("function") == "internal"]
    gs = _script("grid_sweep", "scripts/grid_sweep.py")
    routing = gs.net_routing(cfg, variant)
    lanes = demand.car_lanes(net)
    count, dropped, new = DESTINATIONS[variant]
    # the net is the variant its meta.json describes: the base grid less a closed road, plus a new link
    assert len(GRID_EDGES) == 48
    assert {e for e, *_ in lanes} == (GRID_EDGES - dropped) | new
    assert set(_meta(variant)["change"].get("edges", [])) == dropped | new
    # T4-D2: the base grid's car edges this variant still has; a closed road or a new link is never one
    assert len(routing["dests"]) == count and set(routing["dests"]) == GRID_EDGES - dropped
    assert routing["dests"] == sorted(routing["dests"])
    assert not set(routing["dests"]) & (dropped | new)
    assert demand.outside_largest_scc(demand.car_successors(net)) == []
    assert min(length for _, length, _ in lanes) > cfg["controller"]["guard_m"]
    assert all(s == {d} for d, s in routing["near"].items())


def test_net_routing_guards(tmp_path, monkeypatch):
    """The T4-D2 guards of city_sweep.py: the sweep stops when more base edges than [grid]
    max_dropped_edges are missing from a variant, and when a lane bans passenger cars."""
    gs = _script("grid_sweep", "scripts/grid_sweep.py")
    cfg = _cfg()
    cfg["grid"]["max_dropped_edges"] = 1                       # the closure lacks 2 base edges
    with pytest.raises(SystemExit, match="max_dropped_edges"):
        gs.net_routing(cfg, "closure")
    grid = tmp_path / "scenarios" / "grid"
    grid.mkdir(parents=True)
    for v in VARIANTS:
        shutil.copy(_net(v), grid)
    net = grid / "grid4x4_L200_newlink.net.xml"
    lane = '<lane id="n1_1-n2_2_0"'                           # the new link's lane one way
    assert net.read_text().count(lane) == 1
    net.write_text(net.read_text().replace(lane, lane + ' disallow="passenger"'))
    monkeypatch.setattr(gs, "GRID", grid)
    with pytest.raises(SystemExit, match="ban passenger cars"):
        gs.net_routing(_cfg(), "newlink")


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
    first = (run_dir / "run.sumocfg").read_text().splitlines()[0]       # plain sumo would let every car leave
    assert first.startswith("<!--") and "scripts/grid_sweep.py" in first and "sumo-gui" in first
    opts = {el.tag: el.get("value") for el in ET.parse(run_dir / "run.sumocfg").getroot().iter()}
    assert opts["time-to-teleport"] == "300"
    assert (opts["device.rerouting.probability"], opts["device.rerouting.period"],
            opts["device.rerouting.adaptation-interval"], opts["device.rerouting.adaptation-steps"]) == \
           ("1", "60", "10", "18")
    cfg["run"]["allow_teleport"] = False
    _, run_dir = build_run.build(cfg, "closure", 100, 1)
    opts = {el.tag: el.get("value") for el in ET.parse(run_dir / "run.sumocfg").getroot().iter()}
    assert opts["time-to-teleport"] == "-1"


def test_build_run_main_prints_only_the_run_id_on_stdout(build_run, monkeypatch, capsys):
    """grid_sweep.py reads build_run.py's stdout as the run id; the note that the run needs the
    controller goes to stderr."""
    monkeypatch.setattr(sys, "argv", ["build_run.py", "--config", str(ROOT / "configs/validation/grid_smoke.toml"),
                                      "--variant", "newlink", "--vehicles", "50", "--seed", "3"])
    build_run.main()
    out, err = capsys.readouterr()
    assert out == "grid4_idm_newlink_n50_s3\n"
    assert "scripts/grid_sweep.py" in err


@needs_sumo
@pytest.mark.parametrize("variant, n, ttt", [("base", 150, 300), ("base", 600, 30),
                                             ("closure", 150, 300), ("newlink", 150, 300)])
def test_controller_keeps_n_exact_on_the_grid(build_run, variant, n, ttt):
    """150 cars for 300 s on each variant; and 600 cars on the base grid teleported after 30 s,
    so the run has many teleports. N stays exact every step, no car arrives, every car has the
    rerouting device, cars get new destinations during the run, every route ends on a
    destination (never on a closed road or a new link, T4-D2), and the teleports match SUMO's log."""
    cfg = _cfg()
    cfg["run"].update(end_s=300, warmup_s=100, time_to_teleport_s=ttt)
    _, run_dir = build_run.build(cfg, variant, n, 1)
    gs = _script("grid_sweep", "scripts/grid_sweep.py")
    routing, c = gs.net_routing(cfg, variant), cfg["controller"]
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
    assert cols["grid_n_short_steps"] == 0 and cols["grid_retarget_failed"] == 0
    assert set(device.values()) == {"true"}
    assert rec["retargets"] > n                                  # beyond the one at departure
    assert sum(len(d) > 1 for d in ends.values()) > len(ends) / 2   # most cars changed destination
    assert set().union(*ends.values()) <= set(routing["dests"])
    if ttt == 30:
        assert cols["grid_teleports"] == demand.teleport_count(log) > 0
        assert cols["grid_mid_teleport_max"] > 0
    assert (run_dir / "controller.json").exists()


@needs_sumo
def test_sweep_writes_a_valid_summary_table(build_run, tmp_root, monkeypatch, capsys):
    """grid_sweep.main() end to end on a tiny copy of the smoke config (60 cars, one seed, 300 s,
    all three variants), into tmp_path: every run valid with N exact and no arrival, and the
    summary table passes the data interface (results._check), which a column without the grid_
    prefix fails. The measurement window 120-300 s holds two whole 90 s signal cycles, the
    fewest that give chi a value (measurements.network_summary). build_run.py runs in this
    process, with its ROOT on tmp_path, since a subprocess would write into the repo's runs/."""
    text = (ROOT / "configs" / "validation" / "grid_smoke.toml").read_text()
    for old, new in (('name = "grid_smoke"', 'name = "grid_e2e"'), ("end_s = 1800", "end_s = 300"),
                     ("warmup_s = 600 ", "warmup_s = 120 "), ("seeds = [1, 2]", "seeds = [1]"),
                     ("vehicles = [50, 150, 300, 450, 600, 750, 900]", "vehicles = [60]")):
        assert text.count(old) == 1
        text = text.replace(old, new)
    cfg_path = tmp_root / "configs" / "validation" / "grid_e2e.toml"
    cfg_path.parent.mkdir(parents=True)
    cfg_path.write_text(text)

    def build_run_here(cmd, cwd, capture_output, text):
        argv = list(cmd[1:])                                    # [build_run.py, --config, <path>, ...]
        i = argv.index("--config") + 1
        argv[i] = str(cwd / argv[i])
        out, err = io.StringIO(), io.StringIO()
        with monkeypatch.context() as m, contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            m.setattr(sys, "argv", argv)
            build_run.main()
        return subprocess.CompletedProcess(cmd, 0, out.getvalue(), err.getvalue())

    gs = _script("grid_sweep", "scripts/grid_sweep.py")
    monkeypatch.setattr(gs, "ROOT", tmp_root)
    monkeypatch.setattr(gs, "GRID", tmp_root / "scenarios" / "grid")
    monkeypatch.setattr(gs, "subprocess", types.SimpleNamespace(run=build_run_here))
    monkeypatch.setattr(sys, "argv", ["grid_sweep.py", "--config", str(cfg_path)])
    gs.main()
    assert "wrote results/grid/grid_e2e.csv and 3 time series" in capsys.readouterr().out

    df = results.load_summary("grid", "grid_e2e")
    results._check(df.to_dict("records"), results.SUMMARY, "grid_e2e.csv", extra_prefix="grid_")
    assert list(df.variant) == list(VARIANTS) and df.valid.all()
    assert (df.grid_n_min == 60).all() and (df.grid_n_max == 60).all() and (df.grid_n_short_steps == 0).all()
    assert (df.grid_retarget_failed == 0).all() and (df.grid_reinserted == 0).all()
    assert {"grid_mid_teleport_mean_window", "grid_mid_teleport_max"} <= set(df.columns)
    for run_id in df.run_id:
        run_dir = tmp_root / "runs" / run_id
        rec = json.loads((run_dir / "controller.json").read_text())
        assert rec["arrived"] == 0 and all(rec["checks"].values())
        assert not (run_dir / "fcd.xml").exists()               # [run] keep_fcd = false
        assert (tmp_root / "results" / "grid" / "grid_e2e" / f"{run_id}.csv").exists()
