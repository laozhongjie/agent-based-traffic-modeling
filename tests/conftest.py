"""Shared fixtures. Run all tests from the repository root with:  pytest

Tests that need SUMO are skipped when sumo is not on PATH or SUMO_HOME is not set;
tests of NaSch need SUMO 1.28.0 or later, and tests of OVM need A's OVM build.
"""
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from traffic_project import ROOT, config, export_web, results, runner

needs_sumo = pytest.mark.skipif(shutil.which("sumo") is None or "SUMO_HOME" not in os.environ,
                                reason="SUMO is not installed (see docs/guide.html, section 1)")


def _sumo_has_model(model):
    """True if the sumo on PATH accepts carFollowModel=model."""
    if shutil.which("sumo") is None or "SUMO_HOME" not in os.environ:
        return False
    with tempfile.TemporaryDirectory() as tmp:
        vtype = Path(tmp) / "ovm.add.xml"
        vtype.write_text(f'<additional><vType id="car" carFollowModel="{model}"/></additional>\n')
        net = ROOT / "scenarios" / "ring" / "ring_1000.net.xml"
        r = subprocess.run(["sumo", "-n", str(net), "-a", str(vtype), "--end", "1", "--no-step-log"],
                           capture_output=True, text=True)
    return r.returncode == 0


needs_nasch = pytest.mark.skipif(not _sumo_has_model("NaSch"),
                                 reason="sumo on PATH has no NaSch (needs SUMO 1.28.0 or later)")
needs_ovm = pytest.mark.skipif(not _sumo_has_model("OVM"),
                               reason="sumo on PATH has no OVM (build it from sumo/version.txt)")


@pytest.fixture
def tmp_root(tmp_path, monkeypatch):
    """Point the package at an empty repository in tmp_path, so tests never touch
    the real configs/, results/, runs/ or docs/data/."""
    for module in (config, export_web, results, runner):
        monkeypatch.setattr(module, "ROOT", tmp_path)
    return tmp_path


@pytest.fixture
def ring_net():
    """The committed 1000 m ring network."""
    return ROOT / "scenarios" / "ring" / "ring_1000.net.xml"


def write_fcd(path, steps):
    """Write a minimal SUMO FCD file. steps: {time_s: [(id, speed), ...]}."""
    lines = ["<fcd-export>"]
    for t, vehicles in steps.items():
        lines.append(f'  <timestep time="{t:.2f}">')
        for i, (vid, speed) in enumerate(vehicles):
            lines.append(f'    <vehicle id="{vid}" lane="e0_0" pos="{10 * i}" speed="{speed}"/>')
        lines.append("  </timestep>")
    lines.append("</fcd-export>")
    path.write_text("\n".join(lines) + "\n")
    return path
