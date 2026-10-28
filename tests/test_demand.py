"""Task 4's constant-density controller (traffic_project.demand) and the runner's teleport flag.

The controller tests drive a synthetic stand-in for SUMO (FakeSim): a directed ring of edges,
cars that drive up to vmax m per step along their routes and arrive past their route end, a
rerouting "device" that re-plans a car's route to the same destination along the shortest path
(SUMO's semantics: the passed edges stay in the route, the route gets a new id), and teleports
that move a car one edge per step out of sight. The SUMO tests at the end use the 1000 m ring.
"""
import inspect
import math
import os
import random

import pytest

from traffic_project import ROOT, demand, runner
from conftest import needs_sumo

if "SUMO_HOME" in os.environ:   # demand imports sumolib and traci from $SUMO_HOME/tools, as runner.run_traci does
    runner._import_traci()


class FakeTraCIException(Exception):
    pass


class _Path:
    def __init__(self, edges):
        self.edges = edges


class FakeSim:
    """Just enough of a TraCI connection for demand.ConstantDensity (see the module doc)."""

    def __init__(self, lengths, n, seed, p_reroute=0.0, p_teleport=0.0, vmax=30.0):
        self.edges = [f"e{i}" for i in range(len(lengths))]
        self.length = dict(zip(self.edges, lengths))
        self.rng = random.Random(seed)
        self.p_reroute, self.p_teleport, self.vmax = p_reroute, p_teleport, vmax
        self.cars, self.snap, self.subs, self.routes = {}, {}, set(), {}
        self.pending = [(f"v{i}", self.edges[(3 * i) % len(lengths)]) for i in range(n)]
        self.time = 0.0
        self.departed, self.arrived, self.tp_start, self.tp_end = [], [], [], []
        self.n_arrived, self.first_arrival = 0, None
        self.simulation, self.vehicle, self.route = self, _Vehicle(self), _Route(self)

    # helpers
    def ring_path(self, a, b):
        i, out = self.edges.index(a), [a]
        while out[-1] != b:
            i = (i + 1) % len(self.edges)
            out.append(self.edges[i])
        return out

    def _new_route(self, car, edges):
        car["route"] = edges
        car["var"] = 2 if car["var"] == 1 else 1   # SUMO: the smallest free "!<id>!var#<k>"
        car["rid"] = f"!{car['id']}!var#{car['var']}"

    def _values(self, vid):
        car = self.cars[vid]
        return {demand.VAR_ROUTE_INDEX: car["idx"], demand.VAR_ROUTE_ID: car["rid"]}

    def n_in_network(self):
        return len(self.cars)   # on a lane or in mid-teleport

    def step(self):
        self.time += 1
        self.arrived, self.tp_start, self.tp_end = [], [], []
        for vid in list(self.cars):   # cars inserted in this step do not move yet (as in SUMO)
            car = self.cars[vid]
            if car["tp"]:                                   # in mid-teleport: one edge per step
                car["idx"] += 1
                if car["idx"] >= len(car["route"]):         # teleports beyond its route end
                    self._arrive(vid)
                    continue
                car["tp"] -= 1
                if not car["tp"]:
                    self.tp_end.append(vid)
                    car["pos"] = 0.0
                continue
            if self.rng.random() < self.p_reroute:          # device: same destination, shortest path
                r, i = car["route"], car["idx"]
                self._new_route(car, r[:i] + self.ring_path(r[i], r[-1]))
            if self.rng.random() < self.p_teleport:
                car["tp"] = self.rng.randint(1, 4)
                self.tp_start.append(vid)
                continue
            car["pos"] += self.rng.uniform(0, self.vmax)
            while car["pos"] >= self.length[car["route"][car["idx"]]]:
                car["pos"] -= self.length[car["route"][car["idx"]]]
                car["idx"] += 1
                if car["idx"] >= len(car["route"]):
                    self._arrive(vid)
                    break
        self.departed = []
        for vid, edge in self.pending:
            self.cars[vid] = dict(id=vid, route=[edge], idx=0, pos=0.0, tp=0, var=0, rid=f"!{vid}")
            self.departed.append(vid)
        self.pending = []
        self.snap = {vid: self._values(vid) for vid in self.subs if vid in self.cars}

    def _arrive(self, vid):
        del self.cars[vid]
        self.subs.discard(vid)
        self.arrived.append(vid)
        self.n_arrived += 1
        if self.first_arrival is None:
            self.first_arrival = self.time

    # conn.simulation
    def getDepartedIDList(self):
        return tuple(self.departed)

    def getArrivedIDList(self):
        return tuple(self.arrived)

    def getStartingTeleportIDList(self):
        return tuple(self.tp_start)

    def getEndingTeleportIDList(self):
        return tuple(self.tp_end)

    def findRoute(self, a, b, vType=""):
        return _Path(tuple(self.ring_path(a, b)))


class _Vehicle:
    def __init__(self, sim):
        self.s = sim
        self.set_route_log = []

    def subscribe(self, vid, variables):
        self.s.subs.add(vid)
        self.s.snap[vid] = self.s._values(vid)   # SUMO answers a subscribe with the current values

    def getAllSubscriptionResults(self):
        return dict(self.s.snap)

    def getRoute(self, vid):
        return tuple(self.s.cars[vid]["route"])

    def getRouteIndex(self, vid):
        return self.s.cars[vid]["idx"]

    def setRoute(self, vid, edges):
        car = self.s.cars[vid]
        if edges[0] != car["route"][car["idx"]]:
            raise FakeTraCIException("route must start at the current edge")
        self.s._new_route(car, car["route"][:car["idx"]] + list(edges))
        self.set_route_log.append((self.s.time, vid, tuple(edges)))

    def getIDCount(self):
        return sum(1 for c in self.s.cars.values() if not c["tp"])

    def add(self, vid, route_id, **kw):
        self.s.pending.append((vid, self.s.routes[route_id][0]))


class _Route:
    def __init__(self, sim):
        self.s = sim

    def add(self, route_id, edges):
        self.s.routes[route_id] = list(edges)


SHORT = [5, 8, 3, 60, 4, 100, 2, 7, 150, 6, 12, 90, 3, 4, 40, 200, 9, 2, 75, 5]   # m: many short edges


def ring_near(sim, guard_m):
    incoming = {e: [sim.edges[i - 1]] for i, e in enumerate(sim.edges)}
    return demand.near_sets(sim.length, incoming, guard_m)


def drive(sim, ctl, steps, assert_n=None):
    for _ in range(steps):
        sim.step()
        ctl(sim, sim.time)
        if assert_n is not None:
            assert sim.n_in_network() == assert_n, f"N = {sim.n_in_network()} at t = {sim.time}"
            assert ctl.n_series()[-1] == assert_n


def make(lengths=SHORT, n=25, seed=3, guard_m=40.0, **kw):
    sim = FakeSim(lengths, n, seed, **kw)
    near = ring_near(sim, guard_m) if guard_m else None
    ctl = demand.ConstantDensity(n, sim.edges, seed + 7919, 3, near=near, traci_exception=FakeTraCIException)
    return sim, ctl


# --- the controller on the synthetic network ----------------------------------------------------

@pytest.mark.parametrize("seed", range(40))
def test_n_exact_every_step_under_reroutes_and_teleports(seed):
    # without the guard on new destinations, 17 of these 40 seeds lost a car
    sim, ctl = make(seed=seed, p_reroute=1 / 20, p_teleport=1 / 200)
    drive(sim, ctl, 3000, assert_n=25)
    rec = ctl.record()
    assert sim.n_arrived == 0 and rec["reinserted"] == 0 and rec["arrived"] == 0
    assert ctl.checks() == {"n_exact_every_step": True}
    assert rec["n_min"] == rec["n_max"] == 25 and rec["n_short_steps"] == 0
    assert rec["teleports"] > 20 and rec["guard_retargets"] > 0   # the run exercised both


def test_retarget_never_lands_within_the_guard():
    """Every route the controller sets ends at least guard_m of road beyond the car's edge, so
    a re-plan by the rerouting device in the next step cannot bring the car to its end."""
    sim, ctl = make(p_reroute=1 / 5, p_teleport=1 / 200)
    set_route, n_calls = sim.vehicle.setRoute, [0]

    def checked(vid, edges):
        assert edges[0] not in ctl.near[edges[-1]], f"{vid}: destination {edges[-1]} within the guard of {edges[0]}"
        n_calls[0] += 1
        set_route(vid, edges)

    sim.vehicle.setRoute = checked
    drive(sim, ctl, 3000, assert_n=25)
    assert n_calls[0] > 1000 and ctl.record()["retarget_failed"] == 0


def test_without_the_guard_cars_arrive_and_are_reinserted():
    """The same network loses cars with rule 1 alone, as 2 of 18 two-hour Bugis runs did: the
    fallback puts each one back, and the N check reports the short steps."""
    sim, ctl = make(guard_m=0, p_reroute=1 / 20, p_teleport=1 / 200)
    drive(sim, ctl, 3000)
    rec = ctl.record()
    assert rec["arrived"] > 0 and rec["reinserted"] == rec["arrived"]
    assert ctl.checks() == {"n_exact_every_step": False}
    assert rec["n_short_steps"] > 0 and rec["n_min"] < 25
    assert sim.n_in_network() + len(sim.pending) == 25   # nobody is lost for good


def test_teleport_beyond_route_end_cannot_happen():
    # teleports only: each moves a car one edge per step, so rule 1 keeps 3 edges ahead
    sim, ctl = make(guard_m=0, p_teleport=1 / 10, vmax=0.0)
    drive(sim, ctl, 1500, assert_n=25)
    assert ctl.record()["teleports"] > 1000 and sim.n_arrived == 0


def test_mid_teleport_count_follows_starts_and_ends():
    sim, ctl = make(p_teleport=1 / 50)
    for _ in range(400):
        sim.step()
        ctl(sim, sim.time)
        assert ctl.steps[-1][2] == sum(1 for c in sim.cars.values() if c["tp"])
        assert ctl.steps[-1][1] == sim.vehicle.getIDCount()


def test_route_cache_matches_live_routes():
    sim, ctl = make(p_reroute=1 / 10, p_teleport=1 / 100)
    ctl.verify = True
    drive(sim, ctl, 1500, assert_n=25)
    c = ctl.record()
    assert c["route_cache_mismatches"] == 0 and c["route_reads"] > 0


def run_live_reference(conn, rng, dests, remaining, steps):
    """The fixed re-targeting loop of C's gridlock diagnosis (not in the repo), on the stand-in:
    departing cars in SUMO's order, live route length, cars in libsumo's (sorted) order."""
    def retarget(vid):
        route, idx = conn.vehicle.getRoute(vid), conn.vehicle.getRouteIndex(vid)
        for _ in range(20):
            dest = rng.choice(dests)
            if dest in (route[-1], route[idx]):
                continue
            try:
                path = conn.simulation.findRoute(route[-1], dest, vType="car").edges
                if len(path) < 2:
                    continue
                conn.vehicle.setRoute(vid, list(route[idx:]) + list(path[1:]))
                return
            except FakeTraCIException:
                continue

    for _ in range(steps):
        conn.step()
        departed_list = conn.simulation.getDepartedIDList()
        departed = set(departed_list)
        for vid in departed_list:
            conn.vehicle.subscribe(vid, None)
            retarget(vid)
        results = conn.vehicle.getAllSubscriptionResults()
        for vid in sorted(results):
            res = results[vid]
            n_edges = len(conn.vehicle.getRoute(vid))   # live: = VAR_EDGES, or getRoute for a car that departed now
            if res and res[demand.VAR_ROUTE_INDEX] >= n_edges - remaining:
                retarget(vid)


def test_rule_1_reproduces_the_diagnosis_run_live():
    """Same route changes as run_live, call for call, until run_live first loses a car (after
    that the controller re-inserts it and the runs part)."""
    long_edges = [120, 250, 90, 300, 150, 80, 200, 110]   # m
    ref = FakeSim(long_edges, 12, 5, p_reroute=1 / 60, p_teleport=1 / 300)
    run_live_reference(ref, random.Random(5 + 7919), ref.edges, 3, 2000)
    sim = FakeSim(long_edges, 12, 5, p_reroute=1 / 60, p_teleport=1 / 300)
    ctl = demand.ConstantDensity(12, sim.edges, 5 + 7919, 3, near=None, traci_exception=FakeTraCIException)
    drive(sim, ctl, 2000)
    until = ref.first_arrival or float("inf")
    log_ref = [x for x in ref.vehicle.set_route_log if x[0] < until]
    log_ctl = [x for x in sim.vehicle.set_route_log if x[0] < until]
    assert len(log_ref) > 200 and log_ctl == log_ref


def test_departing_car_with_a_short_route_is_retargeted_again():
    # a one-edge start plus a 2-edge path leaves 2 edges: within 3 of the end, so rule 1 fires again
    sim = FakeSim([100, 100, 100], 1, 0)
    ctl = demand.ConstantDensity(1, sim.edges, 0, 3, traci_exception=FakeTraCIException)
    sim.step()
    ctl(sim, sim.time)
    assert ctl.record()["retargets"] == 2   # at departure, then rule 1 in the same step
    assert len(sim.cars["v0"]["route"]) >= 3


def test_near_sets():
    # a -> b -> c -> d, and x -> c; lengths in m
    length = {"a": 10, "b": 30, "c": 25, "d": 40, "x": 5}
    incoming = {"b": ["a"], "c": ["b", "x"], "d": ["c"]}
    near = demand.near_sets(length, incoming, 70)
    assert near["d"] == {"d", "c", "b", "x"}   # c: 40, b and x: 40 + 25 = 65; a: 65 + 30 = 95
    assert near["c"] == {"c", "b", "x", "a"}   # b, x: 25; a: 55
    assert demand.near_sets(length, incoming, 30)["d"] == {"d"}


# --- teleports, blocks and settledness ----------------------------------------------------------

LOG = """Warning: Teleporting vehicle 'v1'; waited too long (jam), lane='e0_0', time=302.00.
Warning: Vehicle 'v1' ends teleporting on edge 'e3', time=302.00.
Warning: Teleporting vehicle 'v2'; waited too long (yield), lane=':j_1_0', time=310.00.
Warning: Teleporting vehicle 'v7'; waited too long (wrong lane), lane='e2_1', time=320.00.
Warning: Vehicle 'v7' ends teleporting on edge 'e5', time=325.00.
Warning: Vehicle 'v2' teleports beyond arrival edge 'e9', time=330.00.
Warning: Vehicle 'v3' performs emergency braking on lane 'e1_0' with decel=9.00, time=331.00.
"""


def test_teleport_events_and_mid_teleport_counts():
    starts, ends = demand.teleport_events(LOG)
    assert starts == [302.0, 310.0, 320.0] and ends == [302.0, 325.0, 330.0]
    assert demand.teleport_count(LOG) == 3
    assert demand.mid_teleport_counts(starts, ends, [301, 302, 310, 320, 325, 330]) == [0, 0, 1, 2, 1, 0]


def test_teleports_per_car_hour():
    # 1,000 cars; 30 teleports in the second hour, 6 in the first; one at the window end is outside
    times = [100.0] * 6 + [3600.0 + 100 * i for i in range(30)] + [7200.0]
    assert demand.teleports_per_car_hour(times, 1000, 3600, 7200) == pytest.approx(30 / 1000)
    assert demand.teleports_per_car_hour(times, 1000, 0, 7200) == pytest.approx(36 / 2000)
    # a 30 min block: 10 teleports among 500 cars = 10 / (500 x 0.5 h) = 0.04 per car-hour
    assert demand.teleports_per_car_hour([1800.0 + i for i in range(10)], 500, 1800, 3600) == pytest.approx(0.04)


def test_block_means_keep_complete_blocks_only():
    times = list(range(0, 7201))
    values = [1.0 if t < 3600 else 2.0 for t in times]
    assert demand.block_means(times, values, 1800, 7200) == [1.0, 1.0, 2.0, 2.0]   # t = 7200 is outside
    assert demand.block_means([0, 1], [3, 5], 1800, 1200) == []


def test_settledness_check():
    assert demand.settle_ratio([150.0, 160.0, 150.0, 144.0]) == pytest.approx(0.96)
    assert demand.is_settled(0.96) and demand.is_settled(0.9) and demand.is_settled(1.1)
    assert not demand.is_settled(0.89) and not demand.is_settled(1.11)
    assert not demand.is_settled(float("nan"))
    assert math.isnan(demand.settle_ratio([150.0]))
    assert math.isnan(demand.settle_ratio([0.0, 10.0]))


def test_settle_window():
    assert demand.settle_window_ok(7200, 3600, 1800)          # the config: blocks 3,600-5,400-7,200
    assert demand.settle_window_ok(1200, 600, 300)            # the smoke run
    assert not demand.settle_window_ok(7200, 3600, 2400)      # previous block starts at 2,400 < warm-up
    assert not demand.settle_window_ok(7000, 3000, 1800)      # 7,000 s is not whole blocks: tail dropped


def test_outside_largest_scc():
    ring = {"a": {"b"}, "b": {"c"}, "c": {"a"}}
    assert demand.outside_largest_scc(ring) == []
    assert demand.outside_largest_scc(dict(ring, c={"a", "d"})) == ["d"]              # d: a dead end
    assert demand.outside_largest_scc(dict(ring, x={"a"}, y={"x"})) == ["x", "y"]     # cannot be entered


def test_initial_routes_spread_cars_and_refuse_too_many():
    lanes = [("a", 100.0, [0]), ("b", 50.0, [0, 1])]
    vtype = {"length": 5, "minGap": 2}
    text = demand.initial_routes(lanes, 10, vtype, 0.5, seed=1)
    assert text.count("<vehicle ") == 10 and text == demand.initial_routes(lanes, 10, vtype, 0.5, seed=1)
    assert '<vType id="car" length="5" minGap="2"/>' in text
    with pytest.raises(ValueError, match="do not fit"):
        demand.initial_routes(lanes, 40, vtype, 0.5, seed=1)


def test_subscription_variable_ids_match_traci():
    tc = pytest.importorskip("traci.constants")
    assert (demand.VAR_ROUTE_ID, demand.VAR_ROUTE_INDEX) == (tc.VAR_ROUTE_ID, tc.VAR_ROUTE_INDEX)


# --- runner flag ---------------------------------------------------------------------------------

def test_runner_teleport_flag_default_unchanged():
    log = "Warning: Teleporting vehicle 'v1'; waited too long (jam), lane='e0_0', time=30.00.\n"
    assert runner._common_checks(True, log) == {"sumo_exit_ok": True, "no_collision": True, "no_teleport": False}
    assert runner._common_checks(True, "") == {"sumo_exit_ok": True, "no_collision": True, "no_teleport": True}
    assert runner._common_checks(True, log, allow_teleport=True) == {"sumo_exit_ok": True, "no_collision": True}
    assert runner._common_checks(False, log, allow_teleport=True) == {"sumo_exit_ok": False, "no_collision": True}
    for f in (runner.run_sumo, runner.run_traci):   # the flag can only be passed by name
        p = inspect.signature(f).parameters["allow_teleport"]
        assert p.kind is inspect.Parameter.KEYWORD_ONLY and p.default is False


def ring_run(run_dir, n=10, end_s=300, ttt=20, one_edge=True, blocker=False):
    """A run on the 1000 m ring: n cars at rest on e0..e3; v0 stops 100 s on e1 if blocker."""
    run_dir.mkdir(parents=True, exist_ok=True)
    net = ROOT / "scenarios" / "ring" / "ring_1000.net.xml"
    edges = ["e0", "e1", "e2", "e3"]
    lines = ['<routes>', '  <vType id="car" carFollowModel="IDM" length="5" minGap="2" maxSpeed="30"/>']
    for k in range(4):   # looping routes that start on each edge
        lines.append(f'  <route id="r{k}" edges="{" ".join(edges[k:] + edges[:k])}" repeat="20"/>')
    for i in range(n):
        s = i * 1000 / n
        k, pos = int(s // 250), s % 250
        stop = '<stop lane="e1_0" endPos="200" duration="100"/>' if blocker and i == 0 else ""
        route = f'<route edges="e{k}"/>' if one_edge else ""
        attr = "" if one_edge else f' route="r{k}"'
        lines.append(f'  <vehicle id="v{i}" type="car"{attr} depart="0" departPos="{pos:.1f}" '
                     f'departSpeed="0">{route}{stop}</vehicle>')
    (run_dir / "vehicles.rou.xml").write_text("\n".join(lines + ["</routes>"]) + "\n")
    (run_dir / "run.sumocfg").write_text(f"""<configuration>
  <input><net-file value="{net}"/><route-files value="vehicles.rou.xml"/></input>
  <time><begin value="0"/><end value="{end_s}"/><step-length value="1"/></time>
  <processing><collision.action value="warn"/><time-to-teleport value="{ttt}"/></processing>
  <output><summary-output value="summary.xml"/></output>
</configuration>
""")
    return run_dir


@needs_sumo
def test_run_sumo_teleport_flag(tmp_path):
    a = ring_run(tmp_path / "a", n=40, one_edge=False, blocker=True)
    log, checks = runner.run_sumo(a)
    assert demand.teleport_count(log) > 0
    assert checks == {"sumo_exit_ok": True, "no_collision": True, "no_teleport": False}
    b = ring_run(tmp_path / "b", n=40, one_edge=False, blocker=True)
    log_b, checks_b = runner.run_sumo(b, allow_teleport=True)
    assert checks_b == {"sumo_exit_ok": True, "no_collision": True}
    assert demand.teleport_count(log_b) == demand.teleport_count(log)


@needs_sumo
def test_controller_keeps_n_exact_in_sumo_with_teleports(tmp_path):
    """Ten cars on the ring, one held at 0 m/s from 5 s to 120 s, so SUMO teleports it."""
    run_dir = ring_run(tmp_path / "r", n=10, end_s=300, ttt=20)
    net = ROOT / "scenarios" / "ring" / "ring_1000.net.xml"
    ctl = demand.ConstantDensity(10, ["e0", "e1", "e2", "e3"], 1, 3, near=demand.net_near_sets(net, 60))
    n_each_step = []

    def controller(conn, t):
        ctl(conn, t)
        if t == 5:
            conn.vehicle.setSpeed("v0", 0)
        if t == 120:
            conn.vehicle.setSpeed("v0", -1)
        n_each_step.append(conn.vehicle.getIDCount() + len(ctl.teleporting))

    log, checks = runner.run_traci(run_dir, controller, allow_teleport=True)
    assert checks == {"sumo_exit_ok": True, "no_collision": True}
    rec = ctl.record()
    assert n_each_step == [10] * 300 and ctl.checks() == {"n_exact_every_step": True}
    assert rec["arrived"] == 0 and rec["reinserted"] == 0
    assert rec["teleports"] == demand.teleport_count(log) > 0
    starts, ends = demand.teleport_events(log)
    assert [s[2] for s in ctl.steps] == demand.mid_teleport_counts(starts, ends, [s[0] for s in ctl.steps])
    assert runner._common_checks(True, log)["no_teleport"] is False   # the default still fails it


@needs_sumo
def test_controller_retargets_cars_in_mid_teleport_in_sumo(tmp_path):
    """N stays exact through teleports only because SUMO (1) lists cars in mid-teleport in the
    subscription results, (2) accepts setRoute on them and (3) moves them at most one edge per
    step. Forty cars on the ring, v0 held at 0 m/s from 5 s to 300 s, teleport after 10 s: the
    jam keeps a car in mid-teleport for many steps. With remaining_edges = 1 a car is
    re-targeted only on its last edge, so a teleport that passed two edges in one step would
    carry it beyond its route end."""
    run_dir = ring_run(tmp_path / "r", n=40, end_s=600, ttt=10)
    net = ROOT / "scenarios" / "ring" / "ring_1000.net.xml"
    ctl = demand.ConstantDensity(40, ["e0", "e1", "e2", "e3"], 1, 1, near=demand.net_near_sets(net, 60))
    retarget, in_teleport = ctl._retarget, [0]

    def counting(conn, vid):
        ok = retarget(conn, vid)
        in_teleport[0] += ok and vid in ctl.teleporting
        return ok

    ctl._retarget = counting

    def controller(conn, t):
        ctl(conn, t)
        if t == 5:
            conn.vehicle.setSpeed("v0", 0)
        if t == 300:
            conn.vehicle.setSpeed("v0", -1)

    log, checks = runner.run_traci(run_dir, controller, allow_teleport=True)
    rec = ctl.record()
    assert checks == {"sumo_exit_ok": True, "no_collision": True}
    assert rec["teleports"] > 0 and in_teleport[0] > 0, (rec["teleports"], in_teleport[0])
    assert rec["arrived"] == 0 and rec["retarget_failed"] == 0 and ctl.checks() == {"n_exact_every_step": True}
    assert "beyond arrival" not in log


def test_baseline_destinations_keep_the_trips_of_the_baseline():
    """T4-D2: a closed edge stops being a destination, and a new link never becomes one."""
    base = [("a", 100.0, [0]), ("b", 50.0, [0, 1]), ("c", 80.0, [0])]
    closure = [("a", 100.0, [0]), ("c", 80.0, [0])]
    new_link = base + [("n", 40.0, [0])]
    assert demand.baseline_destinations(base, closure) == (["a", "c"], ["b"], [])
    assert demand.baseline_destinations(base, new_link) == (["a", "b", "c"], [], ["n"])
    assert demand.baseline_destinations(base, base) == (["a", "b", "c"], [], [])
