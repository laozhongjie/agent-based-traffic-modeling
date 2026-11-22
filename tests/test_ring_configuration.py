"""Pure configuration checks for ring initialization, output and OVM dispatch."""
import importlib.util

import pytest

from traffic_project import ROOT


def load_script(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


build_run = load_script("ring_build_run", ROOT / "scenarios" / "ring" / "build_run.py")
ring_sweep = load_script("ring_sweep", ROOT / "scripts" / "ring_sweep.py")


def test_fcd_sampling_must_align_with_simulation_steps():
    assert build_run.fcd_settings({
        "step_s": 0.1, "end_s": 1800, "fcd_every_s": 1.0, "fcd_begin_s": 0,
    }) == (1.0, 0.0)

    with pytest.raises(ValueError, match="integer multiple"):
        build_run.fcd_settings({
            "step_s": 0.3, "end_s": 1800, "fcd_every_s": 1.0,
        })


def test_ovm_dispatch_validation():
    traci = {
        "model": "OVM",
        "implementation": "traci",
        "vtype": {"carFollowModel": "Krauss"},
        "ovm": {"alpha": 1.0, "h_c": 25.0, "h_scale": 5.0},
    }
    native = {
        "model": "OVM",
        "implementation": "native",
        "vtype": {"carFollowModel": "OVM", "alpha": 1.0, "sc": 25.0, "d": 5.0},
    }

    assert ring_sweep.ovm_implementation(traci) == "traci"
    assert ring_sweep.ovm_implementation(native) == "native"

    native["vtype"].pop("d")
    with pytest.raises(ValueError, match="vtype.d"):
        ring_sweep.ovm_implementation(native)
