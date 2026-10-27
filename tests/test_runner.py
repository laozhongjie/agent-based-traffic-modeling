"""SUMO runs on a short 1000 m ring with 10 vehicles. Skipped without SUMO."""
import importlib.util
import shutil
import subprocess

import pytest

from traffic_project import ROOT, config, measurements, runner
from conftest import needs_sumo

pytestmark = needs_sumo


def make_run(run_dir, net, end_s=120, n=10, with_end=True):
    """Write a minimal run folder: n vehicles at rest, evenly spaced on edge e0..e3."""
    run_dir.mkdir(parents=True, exist_ok=True)
    edges = ["e0", "e1", "e2", "e3"]
    lines = ['<routes>', '  <vType id="car" carFollowModel="IDM" length="5" minGap="2" maxSpeed="30"/>']
    for k in range(4):
        lines.append(f'  <route id="r{k}" edges="{" ".join(edges[k:] + edges[:k])}" repeat="20"/>')
    for i in range(n):
        s = i * 1000 / n
        lines.append(f'  <vehicle id="v{i}" type="car" route="r{int(s // 250)}" depart="0" '
                     f'departPos="{s % 250:.1f}" departSpeed="0"/>')
    (run_dir / "vehicles.rou.xml").write_text("\n".join(lines + ["</routes>"]) + "\n")
    end = f'<end value="{end_s}"/>' if with_end else ""
    (run_dir / "run.sumocfg").write_text(f"""<configuration>
  <input><net-file value="{net}"/><route-files value="vehicles.rou.xml"/></input>
  <time><begin value="0"/>{end}<step-length value="1"/></time>
  <processing><collision.action value="warn"/><time-to-teleport value="-1"/></processing>
  <output><fcd-output value="fcd.xml"/></output>
</configuration>
""")
    return run_dir


def fcd_body(run_dir):
    """FCD output without its header, which holds a timestamp and the run's paths."""
    text = (run_dir / "fcd.xml").read_text()
    return text[text.index("<fcd-export"):]


ALL_OK = {"sumo_exit_ok": True, "no_collision": True, "no_teleport": True}


def test_run_sumo(tmp_path, ring_net):
    run_dir = make_run(tmp_path / "a", ring_net)
    log, checks = runner.run_sumo(run_dir)
    assert checks == ALL_OK
    assert (run_dir / "log.txt").read_text() == log
    assert fcd_body(run_dir).count("<timestep") == 120  # t = 0 ... 119; the end time is exclusive


def test_run_traci_matches_run_sumo(tmp_path, ring_net):
    a = make_run(tmp_path / "a", ring_net)
    b = make_run(tmp_path / "b", ring_net)
    runner.run_sumo(a)
    times = []
    _, checks = runner.run_traci(b, lambda conn, t: times.append(t))
    assert checks == ALL_OK
    assert times == [float(t) for t in range(1, 121)]
    assert fcd_body(b) == fcd_body(a)


def test_run_traci_controller_changes_the_run(tmp_path, ring_net):
    run_dir = make_run(tmp_path / "a", ring_net)
    counts = {}

    def controller(conn, t):
        if t == 50:
            conn.vehicle.remove("v0")
        counts[t] = conn.vehicle.getIDCount()

    _, checks = runner.run_traci(run_dir, controller)
    assert checks == ALL_OK
    assert counts[49] == 10 and counts[50] == 9 and counts[120] == 9
    _, ring_checks, _ = measurements.ring_summary(run_dir / "fcd.xml", 10, 1000, 0, 5, 10)
    assert ring_checks["all_vehicles_present"] is False


def no_sumo_running(run_dir):
    r = subprocess.run(["pgrep", "-f", str(run_dir)], capture_output=True, text=True)
    return r.stdout.strip() == ""


def test_run_traci_reraises_controller_errors(tmp_path, ring_net):
    run_dir = make_run(tmp_path / "a", ring_net)

    def controller(conn, t):
        if t == 10:
            raise KeyError("bug in controller")

    with pytest.raises(KeyError, match="bug in controller"):
        runner.run_traci(run_dir, controller)
    assert no_sumo_running(run_dir)


def test_run_traci_sumo_crash_is_an_invalid_run(tmp_path, ring_net):
    run_dir = make_run(tmp_path / "a", ring_net)

    def controller(conn, t):
        if t == 10:
            subprocess.run(["pkill", "-9", "-f", str(run_dir / "run.sumocfg")])

    _, checks = runner.run_traci(run_dir, controller)
    assert checks["sumo_exit_ok"] is False
    assert no_sumo_running(run_dir)


def test_broken_config_is_an_invalid_run(tmp_path, ring_net):
    for run in (runner.run_sumo, lambda d: runner.run_traci(d, lambda conn, t: None)):
        run_dir = make_run(tmp_path / f"r{id(run)}", tmp_path / "missing.net.xml")
        log, checks = run(run_dir)
        assert checks["sumo_exit_ok"] is False
        assert "missing.net.xml" in log


def test_run_traci_needs_end_time(tmp_path, ring_net):
    run_dir = make_run(tmp_path / "a", ring_net, with_end=False)
    with pytest.raises(ValueError, match="must set <end>"):
        runner.run_traci(run_dir, lambda conn, t: None)
    assert no_sumo_running(run_dir)


def test_ring_example_reproduces_idm_equilibrium(tmp_root, monkeypatch):
    """The guide's expected result: IDM at 30 veh/km on the 1000 m ring runs at 16.6 m/s."""
    spec = importlib.util.spec_from_file_location("build_run", ROOT / "scenarios" / "ring" / "build_run.py")
    build_run = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build_run)
    monkeypatch.setattr(build_run, "ROOT", tmp_root)
    net_dir = tmp_root / "scenarios" / "ring"
    net_dir.mkdir(parents=True)
    shutil.copy(ROOT / "scenarios" / "ring" / "ring_1000.net.xml", net_dir)
    cfg_path = tmp_root / "idm_sweep.toml"
    shutil.copy(ROOT / "configs" / "ring" / "idm_sweep.toml", cfg_path)

    cfg = config.load(cfg_path)
    run_id, run_dir = build_run.build(cfg, 30, 1)
    assert run_id == "ring_idm_L1000_n30_s1"
    _, checks = runner.run_sumo(run_dir)
    m = cfg["measure"]
    measured, ring_checks, _ = measurements.ring_summary(
        run_dir / "fcd.xml", 30, 1000, cfg["run"]["warmup_s"], m["jam_speed_mps"], m["timeseries_every_s"])
    assert all({**checks, **ring_checks}.values())
    assert measured["mean_speed_mps"] == pytest.approx(16.6, abs=0.1)
    assert measured["congested_fraction"] == 0


def test_allow_teleport_drops_only_the_no_teleport_check():
    log = "Warning: Teleporting vehicle 'v1'; waited too long (jam), lane='e0_0', time=301.00.\n"
    assert runner._common_checks(True, log) == {"sumo_exit_ok": True, "no_collision": True, "no_teleport": False}
    assert runner._common_checks(True, log, allow_teleport=True) == {"sumo_exit_ok": True, "no_collision": True}
