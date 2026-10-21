"""Check SUMO's NaSch (carFollowModel="NaSch", SUMO >= 1.28.0) at p = 0 against the exact result.

Usage (from the repository root, with sumo and SUMO_HOME set; the release 1.28.0 is enough):
    python sumo/check_nasch.py
Builds a 750 m ring (100 cells of 7.5 m) in a temporary folder, runs SUMO with sigma = 0 at several
densities, prints two checks and exits with 1 if any fails:
1. Reference: at every step, every vehicle's cell and speed equal those of
   traffic_project.nasch.integrate, which implements the NaSch rules independently.
2. Fundamental diagram: after the transient, the mean speed and flow equal the exact
   J = min(rho vmax, 1 - rho), and every run passes the common run checks.
Vehicles start on cell boundaries, so the lattice conditions in traffic_project.nasch hold.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

from traffic_project import ROOT, io, nasch, runner

CELL_M = 7.5
N_CELLS = 100
VMAX = 4                       # cells per step; maxSpeed = 30 m/s = the ring's speed limit
EDGES = 4
RING_M = CELL_M * N_CELLS
# sigma = 0 makes the model deterministic; NaSch may stop within one step, so decel is set high
# enough that SUMO does not warn about emergency braking
VTYPE = {"carFollowModel": "NaSch", "sigma": 0, "accel": CELL_M, "decel": VMAX * CELL_M,
         "emergencyDecel": VMAX * CELL_M, "length": CELL_M, "minGap": 0, "maxSpeed": VMAX * CELL_M,
         "speedDev": 0, "speedFactor": 1}


def build_ring(folder):
    """750 m ring with the scenario's own generator, written into folder."""
    stem = folder / f"ring_{int(RING_M)}"
    subprocess.run([sys.executable, str(ROOT / "scenarios" / "ring" / "build_net.py"),
                    "--length", f"{RING_M:g}", "--speed", f"{VMAX * CELL_M:g}", "--out", str(stem)],
                   check=True, capture_output=True)
    return stem.with_suffix(".net.xml")


def start_cells(n):
    """N vehicles spread as evenly as whole cells allow."""
    return [i * N_CELLS // n for i in range(n)]


def run(run_dir, net, n, end_s):
    """Run SUMO; return ({step: {id: (cell, speed in cells/step)}}, common checks)."""
    run_dir.mkdir(parents=True, exist_ok=True)
    edge_m = RING_M / EDGES
    attrs = " ".join(f'{k}="{v}"' for k, v in VTYPE.items())
    lines = ["<routes>", f'  <vType id="car" {attrs}/>']
    laps = int(end_s * VMAX * CELL_M / RING_M) + 2
    for k in range(EDGES):
        edges = " ".join(f"e{(k + j) % EDGES}" for j in range(EDGES))
        lines.append(f'  <route id="r{k}" edges="{edges}" repeat="{laps}"/>')
    for i, c in enumerate(start_cells(n)):
        # a vehicle in cell c has its front at the end of the cell
        s = (c + 1) * CELL_M % RING_M
        e = min(int(s // edge_m), EDGES - 1)
        lines.append(f'  <vehicle id="v{i}" type="car" route="r{e}" depart="0" '
                     f'departPos="{s - e * edge_m:g}" departSpeed="0"/>')
    (run_dir / "vehicles.rou.xml").write_text("\n".join(lines + ["</routes>"]) + "\n")
    (run_dir / "run.sumocfg").write_text(f"""<configuration>
  <input><net-file value="{net}"/><route-files value="vehicles.rou.xml"/></input>
  <time><begin value="0"/><end value="{end_s}"/><step-length value="1"/></time>
  <processing><collision.action value="warn"/><time-to-teleport value="-1"/></processing>
  <output><fcd-output value="fcd.xml"/><precision value="6"/></output>
</configuration>
""")
    _, checks = runner.run_sumo(run_dir)
    states = {}
    if checks["sumo_exit_ok"]:
        for t, vehicles in io.iter_fcd(run_dir / "fcd.xml"):
            states[round(t)] = {
                v["id"]: ((int(v["lane"][1]) * edge_m + v["pos"]) / CELL_M - 1, v["speed"] / CELL_M)
                for v in vehicles}
    return states, checks


def check(tmp, ns, end_s, warmup_s):
    net = build_ring(tmp)
    ok_ref = ok_fd = True
    rows = []
    for n in ns:
        states, checks = run(tmp / f"n{n}", net, n, end_s)
        ref = {step: dict(zip((f"v{i}" for i in range(n)), zip(x, v)))
               for step, x, v in nasch.integrate(start_cells(n), N_CELLS, VMAX, end_s)}
        err = max((max(abs((states[t][i][0] - ref[t][i][0] + N_CELLS / 2) % N_CELLS - N_CELLS / 2),
                       abs(states[t][i][1] - ref[t][i][1]))
                   for t in states for i in states[t]), default=float("inf"))
        counts_ok = all(len(s) == n for s in states.values())
        speeds = [sum(v for _, v in s.values()) / n for t, s in states.items() if t >= warmup_s]
        v_mean = sum(speeds) / len(speeds) if speeds else float("nan")
        rho = n / N_CELLS
        good_ref = checks["sumo_exit_ok"] and err < 1e-6
        v_min = min((v for s in states.values() for _, v in s.values()), default=-1)
        good_fd = (all(checks.values()) and counts_ok and v_min >= 0
                   and abs(v_mean - nasch.mean_speed(rho, VMAX)) < 1e-9)
        ok_ref &= good_ref
        ok_fd &= good_fd
        rows.append((n, rho, err, good_ref, v_mean, good_fd, checks))
    print(f"1. SUMO vs reference automaton, every step for {end_s} s")
    for n, rho, err, good, *_ in rows:
        print(f"   N={n:3d}  rho={rho:.2f}  max |SUMO - reference| = {err:.1e} cells  {'OK' if good else 'FAIL'}")
    print(f"2. Fundamental diagram, mean over {warmup_s}-{end_s} s, vmax = {VMAX} cells/step")
    for n, rho, _, _, v_mean, good, checks in rows:
        failed = [k for k, passed in checks.items() if not passed]
        print(f"   N={n:3d}  rho={rho:.2f}  speed {v_mean:.6f} (exact {nasch.mean_speed(rho, VMAX):.6f}) cells/step  "
              f"flow {rho * v_mean:.6f} (exact {nasch.flow(rho, VMAX):.6f}) veh/step"
              f"{'  failed: ' + ', '.join(failed) if failed else ''}  {'OK' if good else 'FAIL'}")
    return ok_ref and ok_fd


def main():
    with tempfile.TemporaryDirectory() as tmp:
        ok = check(Path(tmp), [5, 10, 20, 25, 30, 40, 50, 75, 90], 300, 200)
    print("All checks passed." if ok else "Some checks FAILED.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
