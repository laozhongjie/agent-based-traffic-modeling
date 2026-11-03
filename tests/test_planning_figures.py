"""scripts/planning_figures.py: critical density (half-speed rule agreed with E), capacity (C's
definition), the paired comparison with the baseline (partners of left-out runs dropped, as C does),
and the per-km-of-baseline-lane density, on small made-up tables. Needs no SUMO and no city code."""
import importlib.util
import math

import pandas as pd
import pytest

from traffic_project import ROOT


def _script():
    spec = importlib.util.spec_from_file_location("planning_figures", ROOT / "scripts" / "planning_figures.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pf = _script()


def test_half_speed_density_interpolates_the_first_crossing():
    k, v = [2.5, 5, 10, 15], [6.0, 5.0, 3.0, 2.0]
    assert pf.half_speed_density(k, v, 4.0) == pytest.approx(7.5)     # between 5 (v 5) and 10 (v 3)
    assert pf.half_speed_density(k, v, 5.0) == pytest.approx(5.0)     # exactly on a point
    assert math.isnan(pf.half_speed_density(k, v, 1.0))               # never below
    assert math.isnan(pf.half_speed_density(k, v, 7.0))               # already below at the lowest density
    # speed dips below, recovers, and falls again: the first crossing (between 2.5 and 5) counts
    assert pf.half_speed_density([2.5, 5, 10, 15], [6, 3, 4, 2], 3.5) == pytest.approx(2.5 + 2.5 * 2.5 / 3)


def _runs(drop=()):
    """v = 7 - 0.2 k + shift + noise; q = 3.6 k v peaks at k = 17.5 + 2.5 (shift + noise)."""
    rows = []
    for variant, shift in (("base", 0.0), ("closure", -0.5), ("newlink", 0.3)):
        for seed, noise in ((1, 0.0), (2, 0.1), (3, -0.1)):
            for k in (2.5, 5, 10, 20, 30):
                if (variant, k, seed) in drop:
                    continue
                v = 7 - 0.2 * k + shift + noise
                rows.append(dict(variant=variant, seed=seed, k_target=k, k=k, v=v, q=3.6 * k * v))
    return pd.DataFrame(rows)


def test_near_empty_speed_and_paired_comparison():
    runs = _runs()
    v0, k_low = pf.near_empty_speed(runs)
    assert k_low == 2.5 and v0 == pytest.approx(7 - 0.5)              # mean of the three seeds
    table, seeds = pf.compare(runs, v0 / 2, ["base", "closure", "newlink"])
    # base seed 1: v = 7 - 0.2 k crosses 3.25 at k = 18.75, between the sweep points 10 and 20 (linear)
    assert seeds.set_index(["variant", "seed"]).loc[("base", 1), "k_half"] == pytest.approx(18.75)
    t = table.set_index("variant")
    # closure: speed 0.5 lower everywhere -> crosses 2.5 veh/km earlier on every seed
    assert t.loc["closure", "d_k_half"] == pytest.approx(-2.5)
    assert t.loc["closure", "same_sign_k_half"] and t.loc["closure", "n_seeds_paired"] == 3
    assert t.loc["newlink", "d_k_half"] == pytest.approx(1.5)
    assert t.loc["newlink", "d_k_half_pct"] == pytest.approx(100 * 1.5 / t.loc["base", "k_half"])
    assert math.isnan(t.loc["base", "d_k_half"])


def test_capacity_is_the_highest_seed_mean_flow():
    runs = _runs()
    cap, k, at_top = pf.capacity(runs, "base")
    curve = runs[runs.variant == "base"].groupby("k_target").q.mean()
    assert (cap, k, at_top) == (pytest.approx(curve.max()), 20.0, False)
    table, _ = pf.compare(runs, 3.25, ["base", "closure"])
    t = table.set_index("variant")
    assert t.loc["closure", "d_capacity"] == pytest.approx(t.loc["closure", "capacity"] - cap)
    # paired flow change at the closure's capacity density (20): 3.6 x 20 x (-0.5) on every seed
    assert t.loc["closure", "d_q_at_cap_mean"] == pytest.approx(-36.0)
    assert t.loc["closure", "same_sign_q_at_cap"]
    assert pf.capacity(runs[runs.k <= 10], "base")[2]                  # still rising: at the top


def test_a_left_out_run_drops_its_partner():
    runs = _runs(drop={("closure", 20, 1)})                           # e.g. an invalid closure run
    v, b = pf.paired(runs, "closure")
    assert len(v) == len(b) == 14 and not ((b.k_target == 20) & (b.seed == 1)).any()
    ch = pf.speed_change(runs, ["base", "closure"]).set_index("k_target")
    assert ch.loc[20, "n_pairs"] == 2 and ch.loc[10, "n_pairs"] == 3
    # closure speed 0.5 lower at k = 10, seed 1: base 5.0, closure 4.5 -> -10 %
    seed1 = 100 * (4.5 / 5.0 - 1)
    assert ch.loc[10, "pct_min"] <= seed1 <= ch.loc[10, "pct_max"]
    # seed 1's paired k_half uses the baseline without its k = 20 run too: both curves cross between 10 and 30
    table, _ = pf.compare(runs, 3.25, ["base", "closure"])
    assert table.set_index("variant").loc["closure", "n_seeds_paired"] == 3


def test_same_sign_is_false_when_seeds_disagree():
    runs = _runs()
    flip = (runs.variant == "closure") & (runs.seed == 2)
    runs.loc[flip, "v"] += 1.0                                        # seed 2 of the closure now faster than base
    runs.loc[flip, "q"] = 3.6 * runs.loc[flip, "k"] * runs.loc[flip, "v"]
    t = pf.compare(runs, 3.25, ["base", "closure"])[0].set_index("variant")
    assert not t.loc["closure", "same_sign_k_half"]
    assert t.loc["closure", "d_k_half_seed_min"] < 0 < t.loc["closure", "d_k_half_seed_max"]


def _sweep_csv(tmp_path, variant, n_vehicles, valid=True, baseline_len=180000.0, own_len=None):
    d = pd.DataFrame(dict(run_id=[f"p_{variant}_k10_s1"], variant=[variant], seed=[1], city_k_target=[10.0],
                          city_n_vehicles=[n_vehicles], mean_speed_mps=[4.0], flow_veh_h=[144.5], valid=[valid],
                          city_lane_length_m=[own_len or baseline_len], city_baseline_lane_length_m=[baseline_len]))
    d.to_csv(tmp_path / f"t_{variant}.csv", index=False)


def test_load_sweeps_uses_the_baseline_lane_length_and_drops_invalid_runs(tmp_path):
    _sweep_csv(tmp_path, "base", 1800)
    _sweep_csv(tmp_path, "closure", 1800, own_len=179800.0)
    _sweep_csv(tmp_path, "newlink", 1800, valid=False)
    names = {v: f"t_{v}" for v in ("base", "closure", "newlink")}
    runs, notes = pf.load_sweeps(names, {v: tmp_path for v in names})
    assert set(runs.variant) == {"base", "closure"} and "1 invalid runs left out" in notes[0]
    assert runs.k.tolist() == pytest.approx([10.0, 10.0])             # N / baseline length, not the variant's
    assert runs.q.tolist() == pytest.approx([144.5, 144.5])           # the summary's flow_veh_h, as in C's results
    runs, _ = pf.load_sweeps(names, {v: tmp_path for v in names}, include_invalid=True)
    assert len(runs) == 3


def test_load_sweeps_stops_on_a_wrong_variant_or_baseline(tmp_path):
    _sweep_csv(tmp_path, "base", 1800)
    _sweep_csv(tmp_path, "closure", 1800)
    with pytest.raises(SystemExit, match="not 'newlink'"):
        pf.load_sweeps({"base": "t_base", "newlink": "t_closure"}, {"base": tmp_path, "newlink": tmp_path})
    _sweep_csv(tmp_path, "closure", 1800, baseline_len=170000.0)
    with pytest.raises(SystemExit, match="baseline lane lengths"):
        pf.load_sweeps({"base": "t_base", "closure": "t_closure"}, {"base": tmp_path, "closure": tmp_path})


def test_map_densities_round_to_sweep_points():
    summary = pd.DataFrame(dict(variant=["base"], k_half=[12.2], k_at_capacity=[28.7]))
    assert pf.map_densities(summary, [2.5, 5, 10, 12.5, 15, 25, 30, 35]) == [12.5, 30.0]


def test_site_export_follows_export_web_and_takes_provenance_from_the_sweep_exports(tmp_path):
    import json
    runs = _runs()
    table, _ = pf.compare(runs, 3.25, ["base", "closure"])
    change = pf.speed_change(runs, ["base", "closure"])
    names = {"base": "sweep_base", "closure": "sweep_closure"}
    (tmp_path / "sweep_base.js").write_text(          # what scripts/export_web.py writes for the base sweep
        '// Generated by scripts/export_web.py\nwindow.RESULTS = window.RESULTS || {};\n'
        'window.RESULTS["city/sweep_base"] = {"name":"sweep_base","config":"configs/city/b.toml",'
        '"config_sha256":"abc","sumo_version":"1.28.0","git_commit":"1234567","draft":false,"rows":[]};\n')
    out = pf.export_site(tmp_path, table, pf.mfd_table(runs), change, 6.5, 3.25, 2.5, names, "IDM", 2)
    text = out.read_text()
    assert text.splitlines()[1] == "window.RESULTS = window.RESULTS || {};" and "NaN" not in text
    d = json.loads(text[text.index('= {') + 2:].strip().rstrip(";"))
    assert (d["scenario"], d["name"], d["excluded_invalid"]) == ("city", "planning", 2)
    assert d["sources"][0]["git_commit"] == "1234567" and d["sources"][1] is None
    assert d["draft"]                                  # the closure sweep is not exported yet
    assert d["columns"][:3] == ["variant", "label", "n_seeds"] and len(d["rows"]) == 2
    base = dict(zip(d["columns"], d["rows"][0]))
    assert base["d_k_half"] is None and isinstance(base["capacity_at_top"], bool)
    assert d["speed_change"]["units"]["pct_mean"] == "%" and len(d["mfd"]["rows"]) == 15   # 3 variants x 5 densities
    assert out.read_text() == pf.export_site(tmp_path, table, pf.mfd_table(runs), change, 6.5, 3.25, 2.5,
                                             names, "IDM", 2).read_text()   # no timestamp: same input, same file


def test_critical_density_comes_from_the_seed_mean_curve():
    """C's method: a missing run thins the mean at its density instead of making its seed's curve
    jump across the gap (base seed 1 without k = 20 would cross between 10 and 30)."""
    runs = _runs(drop={("base", 20, 1)})
    curve = runs[runs.variant == "base"].groupby("k_target").agg(k=("k", "mean"), v=("v", "mean"))
    expect = pf.half_speed_density(curve.k, curve.v, 3.25)
    assert pf.curve_k_half(runs, "base", 3.25) == pytest.approx(expect)
    t = pf.compare(runs, 3.25, ["base", "closure"])[0].set_index("variant")
    assert t.loc["base", "k_half"] == pytest.approx(expect)
    assert t.loc["closure", "d_k_half"] == pytest.approx(t.loc["closure", "k_half"] - expect)


def test_extra_seed_tables_join_the_main_sweep(tmp_path):
    _sweep_csv(tmp_path, "base", 1800)
    _sweep_csv(tmp_path, "closure", 1800)
    extra = pd.read_csv(tmp_path / "t_base.csv").assign(seed=4, run_id="p_base_k10_s4")
    extra.to_csv(tmp_path / "t_base_more.csv", index=False)
    names = {"base": ["t_base", "t_base_more"], "closure": "t_closure"}
    runs, _ = pf.load_sweeps(names, {v: tmp_path for v in names})
    assert sorted(runs[runs.variant == "base"].seed) == [1, 4]
    assert set(runs.table) == {"t_base", "t_base_more", "t_closure"}
    extra.assign(seed=1).to_csv(tmp_path / "t_base_more.csv", index=False)   # same density and seed again
    with pytest.raises(SystemExit, match="in two tables"):
        pf.load_sweeps(names, {v: tmp_path for v in names})


def test_extra_tables_must_share_the_run_settings():
    main = {"run": {"end_s": 7200, "time_to_teleport_s": 300}, "vehicle": {"tau": 1.5},
            "controller": {}, "rerouting": {}, "network": {"net_file": "a", "baseline_net_file": "b"},
            "sweep": {"seeds": [1, 2, 3]}}
    seeds = dict(main, sweep={"seeds": [4, 5]})                     # other seeds and densities: fine
    assert pf.check_same_settings(main, seeds) == {}
    tp = dict(main, run={"end_s": 7200, "time_to_teleport_s": 1200})  # a teleport-sensitivity set
    assert pf.check_same_settings(main, tp) == {"run.time_to_teleport_s": (300, 1200)}
    other_net = dict(main, network={"net_file": "c", "baseline_net_file": "b"})
    assert "network.net_file" in pf.check_same_settings(main, other_net)
