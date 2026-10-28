"""Run SUMO for one run folder and write its record.

Every scenario uses the same three calls:

    log, ok = run_sumo(run_dir)                        # writes log.txt
    write_manifest(run_dir, run_id, cfg, parameters)   # writes manifest.json
    finish(run_dir, run_id, summary, checks)           # writes summary.json, sets valid

A scenario that changes the simulation while it runs, such as the constant-density
controller on the city network, calls run_traci(run_dir, controller) instead of
run_sumo(run_dir). It returns the same log and checks.

The checks that apply to every run (SUMO exit status, collisions, teleports) are
computed here; scenario-specific checks are added by the caller. A scenario whose config
sets [run] allow_teleport = true (the city network under T3-D11, agreed by the group
2026-10-27, and the grid, agreed by member D: teleport a car stuck for 300 s) passes
allow_teleport=True: the no_teleport check
is then left out, and the caller reports the teleport count instead. Every other run keeps the
no_teleport check.
"""
import contextlib
import io
import json
import os
import subprocess
import sys
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


def _common_checks(exit_ok, log, allow_teleport=False):
    checks = {
        "sumo_exit_ok": exit_ok,
        "no_collision": "collision" not in log.lower(),
    }
    if not allow_teleport:
        checks["no_teleport"] = "teleport" not in log.lower()
    return checks


def run_sumo(run_dir, sumocfg="run.sumocfg", *, allow_teleport=False):
    """Run SUMO on run_dir/sumocfg, save log.txt and return (log, common checks)."""
    r = _sh("sumo", "-c", str(run_dir / sumocfg), "--no-step-log")
    log = r.stdout + r.stderr
    (run_dir / "log.txt").write_text(log)
    return log, _common_checks(r.returncode == 0, log, allow_teleport)


def _import_traci():
    """Import TraCI from the SUMO installation in use, so client and server versions match."""
    if "SUMO_HOME" not in os.environ:
        raise RuntimeError("SUMO_HOME is not set; see docs/guide.html, section 1")
    tools = os.path.join(os.environ["SUMO_HOME"], "tools")
    if tools not in sys.path:
        sys.path.append(tools)
    import sumolib
    import traci
    return traci, sumolib


def run_traci(run_dir, controller, sumocfg="run.sumocfg", *, allow_teleport=False):
    """Run SUMO on run_dir/sumocfg step by step and call controller after every step.

    controller(conn, time_s) receives the TraCI connection (conn.vehicle, conn.simulation, ...)
    and the simulation time after the step. The run ends at the <end> time of the sumocfg,
    which must be set. Saves log.txt and returns (log, common checks), as run_sumo does.
    An exception raised by the controller stops SUMO and is raised again: it is a bug in
    the controller, not an invalid run.
    """
    traci, sumolib = _import_traci()
    port = sumolib.miscutils.getFreeSocketPort()
    log_path = run_dir / "log.txt"
    with log_path.open("w") as log_file:
        proc = subprocess.Popen(["sumo", "-c", str(run_dir / sumocfg), "--no-step-log",
                                 "--remote-port", str(port)],
                                cwd=ROOT, stdout=log_file, stderr=subprocess.STDOUT)
        try:
            # SUMO needs a moment to open the port; connect() prints a line per retry.
            with contextlib.redirect_stdout(io.StringIO()):
                conn = traci.connect(port, numRetries=600, proc=proc, waitBetweenRetries=0.05)
        except (traci.TraCIException, traci.FatalTraCIError):
            # SUMO stopped before the run started (e.g. a broken sumocfg) or never opened the port
            if proc.poll() is None:
                proc.kill()
            proc.wait()
            log = log_path.read_text()
            return log, _common_checks(False, log, allow_teleport)
        sumo_failed = False
        try:
            end = conn.simulation.getEndTime()
            if end < 0:
                raise ValueError(f"{sumocfg} must set <end>: a controlled run never empties")
            while conn.simulation.getTime() < end:
                conn.simulationStep()
                controller(conn, conn.simulation.getTime())
        except traci.FatalTraCIError:
            sumo_failed = True  # SUMO stopped during the run; its message is in log.txt
        finally:
            try:
                conn.close(wait=False)
            except traci.FatalTraCIError:
                pass  # the connection is already broken
            try:
                proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
    log = log_path.read_text()
    return log, _common_checks(proc.returncode == 0 and not sumo_failed, log, allow_teleport)


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
