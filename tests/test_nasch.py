"""NaSch theory at p = 0 (traffic_project.nasch) and a short run of sumo/check_nasch.py.

The theory tests run everywhere; the SUMO test needs SUMO 1.28.0 or later and is skipped otherwise.
The full check is:  python sumo/check_nasch.py
"""
import importlib.util

import pytest

from traffic_project import ROOT, nasch
from conftest import needs_nasch


def test_flow_peaks_at_one_over_vmax_plus_one():
    vmax = 4
    assert nasch.flow(1 / (vmax + 1), vmax) == pytest.approx(vmax / (vmax + 1))
    assert nasch.flow(0.1, vmax) == pytest.approx(0.4)    # free flow: rho * vmax
    assert nasch.flow(0.5, vmax) == pytest.approx(0.5)    # jammed: 1 - rho
    assert nasch.mean_speed(0.4, vmax) == pytest.approx(1.5)


def test_automaton_rules():
    # two cars on 10 cells: the rear one is blocked by the gap, the front one accelerates freely
    steps = list(nasch.integrate([0, 2], 10, 3, 2))
    assert steps[1] == (1, [1, 3], [1, 1])
    assert steps[2] == (2, [2, 5], [1, 2])


@pytest.mark.parametrize("n", [5, 20, 25, 40, 75])
def test_automaton_reaches_the_exact_result(n):
    cells, vmax = 100, 4
    *_, (_, x, v) = nasch.integrate([i * cells // n for i in range(n)], cells, vmax, 300)
    assert sorted(set(x)) == sorted(x)                        # one vehicle per cell
    assert sum(v) / n == pytest.approx(nasch.mean_speed(n / cells, vmax))


@needs_nasch
def test_sumo_matches_reference_and_exact_result(tmp_path):
    spec = importlib.util.spec_from_file_location("check_nasch", ROOT / "sumo" / "check_nasch.py")
    check_nasch = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(check_nasch)
    assert check_nasch.check(tmp_path, [10, 25, 40, 75], 200, 150)
