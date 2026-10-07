"""Run SUMO for one run folder and write its record.

Every scenario uses the same three calls:

    log, ok = run_sumo(run_dir)                        # writes log.txt
    write_manifest(run_dir, run_id, cfg, parameters)   # writes manifest.json
    finish(run_dir, run_id, summary, checks)           # writes summary.json, sets valid

The checks that apply to every run (SUMO exit status, collisions, teleports) are
computed here; scenario-specific checks are added by the caller.
"""
import json
import subprocess
from datetime import datetime, timezone

from . import ROOT


def _sh(*cmd):
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)


def sumo_version():
    return _sh("sumo", "--version").stdout.splitlines()[0]


def git_commit():
    """Short commit hash, with -dirty if tracked files have uncommitted changes."""
    commit = _sh("git", "rev-parse", "--short", "HEAD").stdout.strip()
    dirty = _sh("git", "status", "--porcelain", "--untracked-files=no").stdout.strip()
    return commit + ("-dirty" if dirty else "")


def run_sumo(run_dir, sumocfg="run.sumocfg"):
    """Run SUMO on run_dir/sumocfg, save log.txt and return (log, common checks)."""
    r = _sh("sumo", "-c", str(run_dir / sumocfg), "--no-step-log")
    log = r.stdout + r.stderr
    (run_dir / "log.txt").write_text(log)
    checks = {
        "sumo_exit_ok": r.returncode == 0,
        "no_collision": "collision" not in log.lower(),
        "no_teleport": "teleport" not in log.lower(),
    }
    return log, checks


def write_manifest(run_dir, run_id, cfg, parameters):
    manifest = {
        "run_id": run_id,
        "scenario": cfg["scenario"],
        "model": cfg["model"],
        "config": cfg["_path"],
        "config_sha256": cfg["_sha256"],
        "parameters": parameters,
        "sumo_version": sumo_version(),
        "git_commit": git_commit(),
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def finish(run_dir, run_id, summary, checks):
    """Write summary.json; the run is valid only if every check passed."""
    summary = dict(summary, run_id=run_id, valid=all(checks.values()), checks=checks)
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary
