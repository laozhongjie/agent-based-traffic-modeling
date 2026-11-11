"""scripts/city_critical.py: the network critical point (member E's half-speed density) and capacity, written
as the site's CRITICAL entry. Small made-up tables test the method, the file and its checks; the committed
tables of the frozen sweep and of member D's baseline test that the script gives the numbers the group
recorded (13.34 veh/km, 95 % 12.97-13.62; 13.35 veh/km, 12.98-13.59; capacity 170.7, 168.6-172.9 veh/h
with seeds 4-6). Needs no SUMO and no runs/."""
import importlib.util
import json
import math

import numpy as np
import pandas as pd
import pytest

from traffic_project import ROOT, config, results


def _script():
    spec = importlib.util.spec_from_file_location("city_critical", ROOT / "scripts" / "city_critical.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cc = _script()
SETTINGS = dict(sweep_config="configs/city/s.toml", extra_configs=[], near_empty_density_veh_km=2.5,
                speed_ratio=0.5, capacity_window_veh_km=[20, 40], interval=0.95, bootstrap_draws=2000,
                bootstrap_seed_k_c=1, bootstrap_seed_q_max=2)


# ---------------------------------------------------------------- the method

def test_crossing_is_linear_between_neighbours_and_takes_the_first_fall():
    k, v = [2.5, 5, 10, 15], [6.0, 5.0, 3.0, 2.0]
    assert cc.crossing(k, v, 4.0) == pytest.approx(7.5)        # between 5 (v 5) and 10 (v 3)
    assert cc.crossing(k, v, 5.0) == pytest.approx(5.0)        # exactly on a point
    assert math.isnan(cc.crossing(k, v, 1.0))                  # never falls that low
    assert math.isnan(cc.crossing(k, v, 7.0))                  # already below at the lowest density
    # speed falls below, recovers, falls again: the first fall (between 2.5 and 5) counts
    assert cc.crossing(k, [6, 3, 4, 2], 3.5) == pytest.approx(2.5 + 2.5 * 2.5 / 3)


def test_stretched_deviations():
    m, dev, n = cc.stretched([1.0, 2.0, 3.0])
    assert (m, n) == (2.0, 3)
    assert dev == pytest.approx(np.array([-1.0, 0.0, 1.0]) * math.sqrt(1.5))
    assert cc.stretched([4.0])[1] == pytest.approx([0.0])       # one run: nothing to resample


def test_critical_density_range_and_bracket():
    flat = {2.5: [6.0] * 3, 5: [5.0] * 3, 10: [2.0] * 3}       # no seed spread: every resample is the curve
    r = cc.critical_density(flat, 6.0, 0.5, 500, 1, 0.95)
    assert r["k_c"] == pytest.approx(5 + 2 / 3 * 5)             # half of 6 is 3: two thirds of the way 5 -> 10
    assert r["k_c_low"] == pytest.approx(r["k_c"]) and r["k_c_high"] == pytest.approx(r["k_c"])
    assert r["bracket"] == [5, 10] and r["draws_without_crossing"] == 0
    spread = {2.5: [6.0, 6.2, 5.8], 5: [5.0, 5.4, 4.6], 10: [2.0, 2.6, 1.4]}
    a, b = (cc.critical_density(spread, 6.0, 0.5, 2000, 7, 0.95) for _ in range(2))
    assert a == b                                               # a fixed seed gives the same range
    assert a["k_c_low"] < a["k_c"] < a["k_c_high"]
    never = cc.critical_density({2.5: [6.0], 5: [5.0]}, 6.0, 0.5, 50, 1, 0.95)
    assert math.isnan(never["k_c"]) and never["bracket"] is None and never["draws_without_crossing"] == 50
    assert math.isnan(never["k_c_low"])


def _quadratic_runs(seeds=(1, 2, 3), noise=(0.0, 2.0, -2.0)):
    """q = 100 + 6 k - 0.1 k^2 (top 190 veh/h at 30 veh/km) at the window's densities, with seed noise that
    sums to zero at each density, plus two runs below the window that must not count."""
    rows = []
    for k in (20, 25, 30, 35, 40):
        for seed, e in zip(seeds, noise):
            rows.append((k, 100 + 6 * k - 0.1 * k * k + e))
    rows += [(2.5, 999.0), (10, 999.0)]
    return np.array(rows).T


def test_capacity_is_the_top_of_the_quadratic_over_the_window():
    k, q = _quadratic_runs()
    c = cc.capacity(k, q, [20, 40], 2000, 2, 0.95)
    assert c["q_max"] == pytest.approx(190.0) and c["density"] == pytest.approx(30.0)
    assert (c["runs"], c["dof"], c["densities"]) == (15, 10, [20.0, 25.0, 30.0, 35.0, 40.0])
    assert c["q_max_low"] < 190 < c["q_max_high"]
    assert c["q_max_high"] - 190 == pytest.approx(190 - c["q_max_low"])   # symmetric: t x standard error
    assert c == cc.capacity(k, q, [20, 40], 2000, 2, 0.95)                # fixed seed


def test_capacity_needs_three_densities_and_spread():
    k, q = _quadratic_runs(seeds=(1,), noise=(0.0,))
    one = cc.capacity(k, q, [20, 40], 200, 2, 0.95)              # one run per density: a top, no range
    assert one["q_max"] == pytest.approx(190.0) and one["dof"] == 0 and math.isnan(one["q_max_low"])
    two = cc.capacity(np.array([20.0, 25, 25]), np.array([1.0, 2, 3]), [20, 40], 200, 2, 0.95)
    assert math.isnan(two["q_max"])                             # two densities: no quadratic


def _table(speed=lambda k: 7 - 0.2 * k, flow=None, seeds=(1, 2, 3)):
    rows = []
    for k in (2.5, 5, 10, 20, 25, 30, 35, 40):
        for seed in seeds:
            v = speed(k) + 0.05 * (seed - 2)
            rows.append(dict(city_k_target=k, seed=seed, mean_speed_mps=v,
                             flow_veh_h=flow(k, seed) if flow else 3.6 * k * v))
    return pd.DataFrame(rows)


def test_estimate_half_speed_density_and_seed_mean_flow():
    e = cc.estimate(_table(), SETTINGS)
    assert e["v0"] == pytest.approx(6.5)                        # seed mean at 2.5 veh/km
    # half of 6.5 is 3.25; the seed means are 5.0 at 10 and 3.0 at 20 veh/km: 10 + 10 x 1.75 / 2
    assert e["k_c"] == pytest.approx(18.75)
    assert e["bracket"] == [10, 20] and e["seeds"] == [1, 2, 3] and e["n_runs"] == 24
    assert e["k_seed_mean"] == 20 and e["q_seed_mean"] == pytest.approx(3.6 * 20 * 3.0)


def test_estimate_stops_without_a_near_empty_run():
    with pytest.raises(ValueError, match="near-empty density 2.5"):
        cc.estimate(_table()[lambda d: d.city_k_target > 2.5], SETTINGS)
    low = pd.concat([_table(), pd.DataFrame([dict(city_k_target=1.0, seed=1, mean_speed_mps=7.0, flow_veh_h=25.0)])])
    with pytest.raises(ValueError, match="not the lowest"):
        cc.estimate(low, SETTINGS)


# ---------------------------------------------------------------- the file and its checks

SWEEP = """name = "{name}"
scenario = "city"
model = "IDM"
[network]
net_file = "scenarios/city/x.net.xml"
tag = "x"
{network}
[sweep]
densities_veh_km = {densities}
seeds = {seeds}
run_prefix = "{prefix}"
[run]
end_s = 7200
"""


def write_sweep(root, name="s", prefix="ctl_s", seeds=(1, 2, 3), densities=(2.5, 5, 10, 20, 25, 30, 35, 40),
                invalid=("ctl_s_k35_s2",), commit="abc1234", network="", smoke=False,
                speed=lambda k: 7 - 0.2 * min(k, 20) - 0.05 * max(k - 20, 0)):
    path = root / "configs" / "city" / f"{name}.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(SWEEP.format(name=name, prefix=prefix, network=network, densities=list(densities),
                                 seeds=list(seeds)))
    cfg = config.load(path)
    rows = []
    for k in densities:
        for seed in seeds:
            run_id = f"{prefix}_k{k:g}_s{seed}"
            v = speed(k) + 0.05 * (seed - 2)
            rows.append({"run_id": run_id, "scenario": "city", "model": "IDM", "variant": "", "seed": seed,
                         "density_veh_km": k, "mean_speed_mps": v, "flow_veh_h": 3.6 * k * v,
                         "congested_fraction": 0.1, "congested_fraction_var": 0.01,
                         "valid": run_id not in invalid, "city_k_target": k})
            run_dir = root / "runs" / run_id
            run_dir.mkdir(parents=True, exist_ok=True)
            params = {"overrides": {"smoke_run": True}} if smoke else {"overrides": {}}
            (run_dir / "manifest.json").write_text(json.dumps(
                {"config_sha256": cfg["_sha256"], "sumo_version": "Eclipse SUMO sumo 1.28.0",
                 "git_commit": commit, "parameters": params}))
    results.write_summary(rows, cfg)
    return cfg


def write_critical(root, sweep="configs/city/s.toml", extra=(), draws=500):
    path = root / "configs" / "city" / "c.toml"
    s = dict(SETTINGS, sweep_config=sweep, bootstrap_draws=draws)
    lines = ['name = "c"', 'scenario = "city"', 'model = "IDM"', "[critical]"]
    lines += [f"{k} = {json.dumps(v)}" for k, v in s.items() if k != "extra_configs"]
    lines.append(f"extra_configs = {json.dumps(list(extra))}")
    path.write_text("\n".join(lines) + "\n")
    return path


@pytest.fixture
def repo(tmp_root, monkeypatch):
    monkeypatch.setattr(cc, "ROOT", tmp_root)
    return tmp_root


def read_entry(path, key="network/s"):
    lines = path.read_text().splitlines()
    assert len(lines) == 3
    assert lines[1] == "window.CRITICAL = window.CRITICAL || {};"
    prefix = f'window.CRITICAL["{key}"] = '
    assert lines[2].startswith(prefix) and lines[2].endswith(";")
    return lines[0], json.loads(lines[2][len(prefix):-1])


def test_writes_the_entry_where_the_network_page_reads_it(repo):
    write_sweep(repo)
    out = cc.main(["--config", str(write_critical(repo))])
    assert out == repo / "docs" / "data" / "network" / "critical_s.js"
    head, d = read_entry(out)
    assert head == "// Generated by scripts/city_critical.py from results/city/s.csv; do not edit."
    for key in ("k_c", "k_c_low", "k_c_high", "q_max", "q_max_low", "q_max_high", "method", "run_ids"):
        assert key in d
    assert d["k_c_low"] <= d["k_c"] <= d["k_c_high"] and d["q_max_low"] < d["q_max"] < d["q_max_high"]
    assert (d["scenario"], d["page"], d["name"], d["config"]) == ("city", "network", "s", "configs/city/s.toml")
    assert d["config_sha256"] == config.load(repo / "configs/city/s.toml")["_sha256"]
    assert (d["git_commit"], d["draft"], d["sumo_version"]) == ("abc1234", False, "Eclipse SUMO sumo 1.28.0")
    assert d["critical_config"] == "configs/city/c.toml" and d["extra_configs"] == []
    assert d["excluded_invalid"] == 1 and d["excluded_run_ids"] == ["ctl_s_k35_s2"]
    assert len(d["run_ids"]) == 23 and "ctl_s_k35_s2" not in d["run_ids"]
    assert d["units"]["k_c"] == "veh/km" and d["units"]["q_max"] == "veh/h"
    assert d["near_empty_speed_mps"] == pytest.approx(6.5) and d["k_c_bracket_veh_km"] == [10, 20]
    assert all(len(f"{x:.15g}".replace(".", "").lstrip("-0")) <= 6
               for x in (d["k_c"], d["k_c_low"], d["k_c_high"], d["q_max"], d["q_max_low"], d["q_max_high"]))
    first = out.read_bytes()
    cc.main(["--config", str(repo / "configs/city/c.toml")])
    assert out.read_bytes() == first                            # same inputs, same file: no timestamp


def test_extra_sweep_joins_and_is_named(repo):
    write_sweep(repo)
    write_sweep(repo, name="s46", prefix="x46", seeds=(4, 5, 6), densities=(25, 30, 35), invalid=())
    out = cc.main(["--config", str(write_critical(repo, extra=["configs/city/s46.toml"]))])
    head, d = read_entry(out)
    assert head.endswith("from results/city/s.csv and results/city/s46.csv; do not edit.")
    assert d["seeds"] == [1, 2, 3, 4, 5, 6] and len(d["run_ids"]) == 32
    assert d["extra_configs"][0]["config"] == "configs/city/s46.toml"


@pytest.mark.parametrize("change, message", [
    ("config", "changed after the runs"),
    ("dirty", "uncommitted code"),
    ("manifest", "missing run record"),
    ("smoke", "smoke run"),
    ("commits", "differ in git commit"),
])
def test_refuses_runs_that_fail_a_check(repo, change, message):
    write_sweep(repo, commit="abc1234-dirty" if change == "dirty" else "abc1234", smoke=change == "smoke")
    if change == "config":
        p = repo / "configs/city/s.toml"
        p.write_text(p.read_text() + "# edited after the runs\n")
    if change == "manifest":
        (repo / "runs/ctl_s_k10_s1/manifest.json").unlink()
    if change == "commits":
        p = repo / "runs/ctl_s_k10_s1/manifest.json"
        p.write_text(p.read_text().replace("abc1234", "def5678"))
    crit = write_critical(repo)
    with pytest.raises(SystemExit, match=message):
        cc.main(["--config", str(crit)])
    assert not (repo / "docs").exists()
    out = cc.main(["--config", str(crit), "--preview"])         # a preview lists the problem instead
    assert out == repo / "runs" / "critical_preview_s.js"
    head, d = read_entry(out)
    assert head.startswith("// Preview by scripts/city_critical.py") and "not for the site" in head
    assert any(message in p for p in d["preview_problems"])


def test_allow_dirty_writes_a_draft(repo):
    write_sweep(repo, commit="abc1234-dirty")
    _, d = read_entry(cc.main(["--config", str(write_critical(repo)), "--allow-dirty"]))
    assert d["draft"] is True and d["git_commit"] == "abc1234-dirty"


def test_refuses_what_the_method_cannot_judge(repo):
    write_sweep(repo, speed=lambda k: 7 - 0.01 * k)             # speed never halves
    with pytest.raises(SystemExit, match="no k_c"):
        cc.main(["--config", str(write_critical(repo))])
    write_sweep(repo, name="v", prefix="v", network='baseline_net_file = "scenarios/city/base.net.xml"\nvariant = "closure"')
    with pytest.raises(SystemExit, match="planning variant"):
        cc.main(["--config", str(write_critical(repo, sweep="configs/city/v.toml"))])


def test_refuses_extra_sweeps_that_differ_or_overlap(repo):
    write_sweep(repo)
    write_sweep(repo, name="o", prefix="o", seeds=(3,), densities=(25,), invalid=())   # k 25, seed 3 twice
    with pytest.raises(SystemExit, match="in two tables"):
        cc.main(["--config", str(write_critical(repo, extra=["configs/city/o.toml"]))])
    p = repo / "configs/city/d.toml"
    write_sweep(repo, name="d", prefix="d", seeds=(4,), densities=(25,), invalid=())
    p.write_text(p.read_text().replace("end_s = 7200", "end_s = 3600"))
    with pytest.raises(SystemExit, match="differs from configs/city/s.toml in run"):
        cc.main(["--config", str(write_critical(repo, extra=["configs/city/d.toml"]))])


def test_preview_options_need_preview(repo):
    write_sweep(repo)
    with pytest.raises(SystemExit):
        cc.main(["--config", str(write_critical(repo)), "--from", str(repo)])


# ---------------------------------------------------------------- the group's recorded numbers

def _committed(*names):
    return pd.concat([cc.read_table(ROOT / "results" / "city" / f"{n}.csv")[0] for n in names], ignore_index=True)


@pytest.fixture(scope="module")
def ruled():
    return cc.settings_of(config.load(ROOT / "configs" / "city" / "bugis_all_critical.toml"))


def test_frozen_sweep_gives_the_recorded_critical_point(ruled):
    """results/city/bugis_all_controller.csv, the frozen sweep (seeds 1-3, 32 valid runs): 24.40 km/h,
    13.34 veh/km (95 % 12.97-13.62), the numbers of C's half-speed script of 31 Oct; highest seed-mean
    flow 172.7 at 30 veh/km; quadratic top 172.37 (seeds 1-3 only: 168.42-176.32)."""
    e = cc.estimate(_committed("bugis_all_controller"), ruled)
    assert e["n_runs"] == 32 and e["v0"] * 3.6 == pytest.approx(24.40, abs=0.005)
    assert (e["k_c"], e["k_c_low"], e["k_c_high"]) == pytest.approx((13.3350, 12.9735, 13.6206), abs=5e-5)
    assert e["bracket"] == [12.5, 15]
    assert (e["q_seed_mean"], e["k_seed_mean"]) == (pytest.approx(172.72, abs=0.005), 30)
    c = e["cap"]
    assert (c["q_max"], c["q_max_low"], c["q_max_high"]) == pytest.approx((172.372, 168.423, 176.320), abs=5e-4)
    assert (c["runs"], c["dof"]) == (14, 9)


def test_frozen_sweep_with_seeds_4_to_6_gives_the_recorded_capacity(ruled):
    """With bugis_all_controller_seeds4to6.csv (41 valid runs): capacity 170.7 veh/h (168.6-172.9), as the
    message to member E of 30 Oct gave it; highest seed-mean flow 171.06 at 35 veh/km; k_c unchanged."""
    e = cc.estimate(_committed("bugis_all_controller", "bugis_all_controller_seeds4to6"), ruled)
    c = e["cap"]
    assert (c["q_max"], c["q_max_low"], c["q_max_high"]) == pytest.approx((170.742, 168.621, 172.862), abs=5e-4)
    assert (c["runs"], c["dof"]) == (23, 18)
    assert (e["q_seed_mean"], e["k_seed_mean"]) == (pytest.approx(171.06, abs=0.005), 35)
    assert (e["k_c"], e["k_c_low"], e["k_c_high"]) == pytest.approx((13.3350, 12.9735, 13.6206), abs=5e-5)


def test_member_d_baseline_gives_the_recorded_critical_point(ruled):
    """results/city/bugis_all_base_controller.csv, member D's baseline (31 valid runs): 24.38 km/h,
    13.35 veh/km (12.98-13.59), not to be confused with the frozen sweep's 13.34; capacity 172.5."""
    e = cc.estimate(_committed("bugis_all_base_controller"), ruled)
    assert e["n_runs"] == 31 and e["v0"] * 3.6 == pytest.approx(24.38, abs=0.005)
    assert (round(e["k_c"], 2), round(e["k_c_low"], 2), round(e["k_c_high"], 2)) == (13.35, 12.98, 13.59)
    # capacity 172.5 (169.7-175.3) veh/h, as C's course-map page R8 of 10 Nov gives it (there with another seed)
    c = e["cap"]
    assert (round(c["q_max"], 1), round(c["q_max_low"], 1), round(c["q_max_high"], 1)) == (172.5, 169.7, 175.3)
