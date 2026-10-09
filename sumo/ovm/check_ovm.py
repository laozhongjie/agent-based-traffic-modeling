"""Check SUMO's OVM (carFollowModel="OVM") against theory and an independent integrator.

Usage (from the repository root, with sumo and SUMO_HOME pointing at the OVM build, see sumo/version.txt):
    python sumo/ovm/check_ovm.py
Runs SUMO on the 1000 m ring in a temporary folder, prints three checks and exits with 1 if any fails:
1. Uniform flow: with no perturbation every vehicle settles at V(s0).
2. Reference: with a small seeded perturbation, SUMO's positions and speeds equal those of
   traffic_project.ovm.integrate, which implements the same scheme independently.
3. Stability: the perturbation decays where the discrete-time growth rate is negative and grows
   where it is positive. Unstable points whose growth is too slow to show within the run are skipped.
The check case is fixed below; it is a test of the build, not an experiment.
"""
import math
import random
import sys
import tempfile
from pathlib import Path

from traffic_project import ROOT, io, ovm, runner

NET = ROOT / "scenarios" / "ring" / "ring_1000.net.xml"
RING_M, EDGES = 1000.0, 4
STEP_S = 0.1
# decel and emergencyDecel do not bound OVM; set high so SUMO does not warn about emergency braking
VTYPE = {"carFollowModel": "OVM", "length": 5, "minGap": 0, "maxSpeed": 25, "speedDev": 0,
         "speedFactor": 1, "alpha": 1.0, "sc": 18.0, "d": 11.6, "decel": 50, "emergencyDecel": 50}
JITTER_M = 0.5


def start_positions(n, jitter, seed):
    """(edge index, position on edge as written to the route file) of N evenly spaced vehicles."""
    rng = random.Random(seed)
    edge_len = RING_M / EDGES
    out = []
    for i in range(n):
        s = (i * RING_M / n + rng.uniform(-jitter, jitter)) % RING_M
        e = min(int(s // edge_len), EDGES - 1)
        out.append((e, f"{s - e * edge_len:.6f}"))
    return out


def ring_positions(starts):
    return [e * RING_M / EDGES + float(pos) for e, pos in starts]


def run(run_dir, n, jitter, seed, end_s):
    """Run SUMO; return ({time_s: {id: (x, v)}}, common checks). Output every 1 s, 8 decimals."""
    run_dir.mkdir(parents=True, exist_ok=True)
    attrs = " ".join(f'{k}="{v}"' for k, v in VTYPE.items())
    lines = ["<routes>", f'  <vType id="car" {attrs}/>']
    laps = int(end_s * VTYPE["maxSpeed"] / RING_M) + 2
    for k in range(EDGES):
        edges = " ".join(f"e{(k + j) % EDGES}" for j in range(EDGES))
        lines.append(f'  <route id="r{k}" edges="{edges}" repeat="{laps}"/>')
    for i, (e, pos) in enumerate(start_positions(n, jitter, seed)):
        lines.append(f'  <vehicle id="v{i}" type="car" route="r{e}" depart="0" departPos="{pos}" departSpeed="0"/>')
    (run_dir / "vehicles.rou.xml").write_text("\n".join(lines + ["</routes>"]) + "\n")
    (run_dir / "run.sumocfg").write_text(f"""<configuration>
  <input><net-file value="{NET}"/><route-files value="vehicles.rou.xml"/></input>
  <time><begin value="0"/><end value="{end_s:g}"/><step-length value="{STEP_S:g}"/></time>
  <processing><collision.action value="warn"/><time-to-teleport value="-1"/></processing>
  <output><fcd-output value="fcd.xml"/><device.fcd.period value="1"/><precision value="8"/></output>
</configuration>
""")
    _, checks = runner.run_sumo(run_dir)
    states = {}
    if checks["sumo_exit_ok"]:
        for t, vehicles in io.iter_fcd(run_dir / "fcd.xml"):
            states[round(t)] = {v["id"]: (int(v["lane"][1]) * RING_M / EDGES + v["pos"], v["speed"])
                                for v in vehicles}
    return states, checks


def speed_sd(state):
    sp = [v for _, v in state.values()]
    m = sum(sp) / len(sp)
    return math.sqrt(sum((v - m) ** 2 for v in sp) / len(sp))


def min_gap(state):
    pos = sorted(x for x, _ in state.values())
    return min((pos[(i + 1) % len(pos)] - pos[i]) % RING_M - VTYPE["length"] for i in range(len(pos)))


def check_uniform(tmp, ns, end_s):
    """Every vehicle at V(s0) at the end of an unperturbed run."""
    ok = True
    print(f"1. Uniform flow, no perturbation, {end_s:g} s")
    for n in ns:
        states, checks = run(tmp / f"uniform_n{n}", n, 0.0, 1, end_s)
        target = ovm.optimal_speed(ovm.uniform_gap(n, RING_M, VTYPE), VTYPE)
        last = states[max(states)] if states else {}
        err = max((abs(v - target) for _, v in last.values()), default=math.inf)
        good = all(checks.values()) and len(last) == n and err < 1e-6
        ok &= good
        print(f"   N={n:3d}  V(s0)={target:.6f} m/s  max |v - V(s0)| = {err:.1e}  {'OK' if good else 'FAIL'}")
    return ok


def check_reference(tmp, ns, end_s):
    """SUMO equals the reference integrator at every output second."""
    ok = True
    print(f"2. SUMO vs reference integrator, {JITTER_M} m perturbation, {end_s:g} s")
    for n in ns:
        states, checks = run(tmp / f"reference_n{n}", n, JITTER_M, 1, end_s)
        x0 = ring_positions(start_positions(n, JITTER_M, 1))
        per_s = round(1 / STEP_S)
        ref = {step // per_s: dict(zip((f"v{i}" for i in range(n)), zip(x, v)))
               for step, x, v in ovm.integrate(x0, VTYPE, RING_M, STEP_S, round(end_s / STEP_S))
               if step % per_s == 0}
        err = max(max(abs((states[t][i][0] - ref[t][i][0] + RING_M / 2) % RING_M - RING_M / 2),
                      abs(states[t][i][1] - ref[t][i][1]))
                  for t in states for i in states[t])
        gap_sumo = min(min_gap(s) for s in states.values())
        gap_ref = min(min_gap(ref[t]) for t in states)
        # overlaps are allowed (they belong to the model) but SUMO must report them
        good = checks["sumo_exit_ok"] and err < 1e-5 and checks["no_collision"] == (gap_sumo >= 0)
        ok &= good
        print(f"   N={n:3d}  max |SUMO - reference| = {err:.1e}  min gap SUMO {gap_sumo:.4f} m, "
              f"reference {gap_ref:.4f} m  collisions logged: {not checks['no_collision']}  "
              f"{'OK' if good else 'FAIL'}")
    return ok


def check_stability(tmp, ns, end_s, t0=30):
    """Speed spread shrinks from t0 to the end where the discrete growth rate is negative, else grows."""
    ok = True
    print(f"3. Stability of uniform flow, {JITTER_M} m perturbation, spread of speeds from {t0} s to {end_s:g} s")
    for n in ns:
        s0 = ovm.uniform_gap(n, RING_M, VTYPE)
        rate = ovm.growth_rate(n, s0, VTYPE, dt=STEP_S)
        states, _ = run(tmp / f"stability_n{n}", n, JITTER_M, 1, end_s)
        a, b = speed_sd(states[t0]), speed_sd(states[max(states)])
        line = (f"   N={n:3d}  s0={s0:6.2f} m  V'(s0)={ovm.optimal_speed_slope(s0, VTYPE):.3f}  "
                f"alpha/2={VTYPE['alpha'] / 2:g}  growth rate {rate:+.4f}/s "
                f"(continuous {ovm.growth_rate(n, s0, VTYPE):+.4f}/s)  sd {a:.1e} -> {b:.1e}")
        if 0 < rate * (max(states) - t0) < 2:
            print(line + "  grows too slowly to show in this run, not judged")
            continue
        good = (b > a) == (rate > 0)
        ok &= good
        print(line + f"  {'OK' if good else 'FAIL'}")
    return ok


def main():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        results = [check_uniform(tmp, [10, 20, 100, 150], 600),
                   check_reference(tmp, [20, 50, 100], 300),
                   check_stability(tmp, [20, 30, 40, 50, 60, 80, 100, 150], 600)]
    print("All checks passed." if all(results) else "Some checks FAILED.")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
