import json

import pytest

from traffic_project import config, export_web, results


def setup_experiment(root, commits=("abc1234", "abc1234"), valid=(True, False)):
    """A config, a summary table with one row per commit, and a run record for each run."""
    path = root / "configs" / "ring" / "t.toml"
    path.parent.mkdir(parents=True)
    path.write_text('name = "t"\nscenario = "ring"\nmodel = "IDM"\n')
    cfg = config.load(path)
    rows = []
    for i, (commit, ok) in enumerate(zip(commits, valid)):
        run_id = f"ring_idm_L1000_n{10 * (i + 1)}_s1"
        rows.append({"run_id": run_id, "scenario": "ring", "model": "IDM", "variant": "", "seed": 1,
                     "density_veh_km": 10.0 * (i + 1), "mean_speed_mps": 28.123456789,
                     "flow_veh_h": 1012.2, "congested_fraction": 0.0,
                     "congested_fraction_var": 1.23456789e-7, "valid": ok, "ring_vehicles": 10 * (i + 1)})
        run_dir = root / "runs" / run_id
        run_dir.mkdir(parents=True)
        (run_dir / "manifest.json").write_text(json.dumps(
            {"config_sha256": cfg["_sha256"], "sumo_version": "Eclipse SUMO sumo 1.27.1",
             "git_commit": commit}))
    results.write_summary(rows, cfg)
    return cfg


def read_export(path):
    line = path.read_text().splitlines()[-1]
    prefix = 'window.RESULTS["ring/t"] = '
    assert line.startswith(prefix) and line.endswith(";")
    return json.loads(line[len(prefix):-1])


def test_export_valid_runs(tmp_root):
    cfg = setup_experiment(tmp_root)
    out = export_web.export(cfg)
    assert out == tmp_root / "docs" / "data" / "ring" / "t.js"
    data = read_export(out)
    assert data["draft"] is False
    assert data["git_commit"] == "abc1234"
    assert data["config_sha256"] == cfg["_sha256"]
    assert data["excluded_invalid"] == 1
    assert "valid" not in data["columns"] and "scenario" not in data["columns"]
    assert data["units"]["density_veh_km"] == "veh/km"
    [run] = data["rows"]
    rec = dict(zip(data["columns"], run))
    assert rec["run_id"] == "ring_idm_L1000_n10_s1"
    assert rec["variant"] == ""
    assert rec["seed"] == 1 and rec["ring_vehicles"] == 10
    assert rec["mean_speed_mps"] == 28.1235            # 6 significant digits
    assert rec["congested_fraction_var"] == 1.23457e-7


def test_export_is_reproducible(tmp_root):
    cfg = setup_experiment(tmp_root)
    first = export_web.export(cfg).read_bytes()
    assert export_web.export(cfg).read_bytes() == first


def test_export_refuses_dirty_runs_unless_draft(tmp_root):
    cfg = setup_experiment(tmp_root, commits=("abc1234-dirty", "abc1234-dirty"))
    with pytest.raises(ValueError, match="uncommitted code"):
        export_web.export(cfg)
    assert read_export(export_web.export(cfg, allow_dirty=True))["draft"] is True


def test_export_refuses_changed_config(tmp_root):
    cfg = setup_experiment(tmp_root)
    path = tmp_root / cfg["_path"]
    path.write_text(path.read_text() + "# edited after the runs\n")
    with pytest.raises(ValueError, match="changed after the runs"):
        export_web.export(config.load(path))


def test_export_refuses_mixed_commits(tmp_root):
    cfg = setup_experiment(tmp_root, commits=("abc1234", "def5678"), valid=(True, True))
    with pytest.raises(ValueError, match="runs differ in git commit"):
        export_web.export(cfg)


def test_export_refuses_missing_run_record(tmp_root):
    cfg = setup_experiment(tmp_root)
    (tmp_root / "runs" / "ring_idm_L1000_n10_s1" / "manifest.json").unlink()
    with pytest.raises(ValueError, match="missing run record"):
        export_web.export(cfg)


def test_export_refuses_no_valid_runs(tmp_root):
    cfg = setup_experiment(tmp_root, valid=(False, False))
    with pytest.raises(ValueError, match="no valid runs"):
        export_web.export(cfg)
