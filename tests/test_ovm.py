"""OVM theory (traffic_project.ovm) and short runs of sumo/ovm/check_ovm.py.

The theory tests run everywhere; the SUMO tests need A's OVM build and are skipped otherwise.
The full check, with longer runs, is:  python sumo/ovm/check_ovm.py
"""
import importlib.util

import pytest

from traffic_project import ROOT, ovm
from conftest import needs_ovm

P = {"alpha": 1.0, "sc": 18.0, "d": 11.6, "maxSpeed": 25.0, "length": 5.0, "minGap": 0.0}


def test_optimal_speed_limits():
    assert ovm.optimal_speed(0, P) == pytest.approx(0, abs=1e-12)
    assert ovm.optimal_speed(1e4, P) == pytest.approx(P["maxSpeed"])
    assert ovm.optimal_speed(-1, P) < 0


@pytest.mark.parametrize("s", [0, 10, 18, 30, 60])
def test_slope_matches_finite_difference(s):
    h = 1e-5
    numeric = (ovm.optimal_speed(s + h, P) - ovm.optimal_speed(s - h, P)) / (2 * h)
    assert ovm.optimal_speed_slope(s, P) == pytest.approx(numeric, rel=1e-6)


def test_uniform_gap():
    assert ovm.uniform_gap(50, 1000, P) == pytest.approx(15)
    assert ovm.uniform_gap(50, 1000, dict(P, minGap=2)) == pytest.approx(13)


def test_growth_rate_threshold_on_a_long_ring():
    # At the steepest point s = sc, V' = 1.126 /s: unstable for alpha = 1 (alpha/2 = 0.5),
    # stable for alpha = 3 (alpha/2 = 1.5).
    n, s0 = 2000, P["sc"]
    assert ovm.optimal_speed_slope(s0, P) == pytest.approx(1.1260, abs=1e-4)
    assert ovm.growth_rate(n, s0, P) > 0
    assert ovm.growth_rate(n, s0, dict(P, alpha=3.0)) < 0


def test_discrete_rate_approaches_continuous():
    n, s0 = 50, 15.0
    cont = ovm.growth_rate(n, s0, P)
    assert ovm.growth_rate(n, s0, P, dt=1e-3) == pytest.approx(cont, rel=1e-2)
    assert ovm.growth_rate(n, s0, P, dt=0.1) != pytest.approx(cont, rel=1e-2)


def test_integrate_keeps_uniform_flow_and_reaches_v_s0():
    n, ring = 20, 1000.0
    x0 = [i * ring / n for i in range(n)]
    *_, (step, x, v) = ovm.integrate(x0, P, ring, 0.1, 3000)
    target = ovm.optimal_speed(ovm.uniform_gap(n, ring, P), P)
    assert step == 3000
    assert max(abs(s - target) for s in v) < 1e-9


def _check_module():
    spec = importlib.util.spec_from_file_location("check_ovm", ROOT / "sumo" / "ovm" / "check_ovm.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@needs_ovm
def test_sumo_uniform_flow(tmp_path):
    assert _check_module().check_uniform(tmp_path, [10, 100], 200)


@needs_ovm
def test_sumo_matches_reference_integrator(tmp_path):
    # N = 50 is unstable and its vehicles overlap within 100 s; SUMO must log the collisions
    assert _check_module().check_reference(tmp_path, [20, 50], 100)


@needs_ovm
def test_sumo_stability(tmp_path):
    assert _check_module().check_stability(tmp_path, [20, 50], 200)
