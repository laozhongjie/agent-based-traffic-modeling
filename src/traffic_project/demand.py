"""Constant-density demand on the city network (task 4, owner C): initial placement and the
TraCI controller that keeps the number of cars N exactly constant, so the density k = N / L
is exact.

Rules (ruled by C 2026-10-27 for the city network and agreed by the group the same day):
  T4-D1   every car gets a random destination edge (uniform over the edges that allow passenger
          cars; for a planning variant, over the baseline's car edges that the variant still has,
          T4-D2) when it departs, again whenever it nears the end of its route, and as soon as
          it is within guard_m (60 m) of its destination by road (rule 2 below); SUMO's
          rerouting device, set in the run's sumocfg, re-plans every route every 60 s on travel
          times averaged over the last 180 s.
  T3-D11  option C: SUMO teleports a car that has been stuck for 300 s. The controller counts
          teleports and the cars in mid-teleport, so every run reports teleports per car-hour.

A car leaves SUMO only by arriving at the end of its route. The controller stops that with
three rules, applied after every simulation step:
  1. Near the end. A car within `remaining_edges` edges of its route end, counted on its live
     route (the rerouting device changes routes), gets a new destination: the fastest path
     from the route's last edge to the new destination is appended, so its next turns do not
     change. This is task 3's re-targeting with two fixes found in C's gridlock diagnosis (not
     in the repo): departing cars are handled in SUMO's order, each gets one destination, and
     a car that departed this step is checked on its live route, not on its one-edge start.
     Cars are checked in the order of their ids (libsumo's order), so the controller gives the
     same runs over TraCI as over libsumo.
  2. Guard. A car whose current edge ends less than `guard_m` of road before its destination,
     by any path, also gets a new destination, and a new destination is never drawn that
     close to the car's current edge. Rule 1 alone lost 2 cars in 18 two-hour runs: the
     rerouting device re-plans from the car's position to the same destination by the
     shortest path, so when the car is on (or just before) its destination edge, because its
     route passes that edge before it ends there, the new route ends right there and the car
     arrives in the same step. A car drives at most maxSpeed x step length per step, so with
     guard_m above that, no car can reach its route end between two checks. A car in
     mid-teleport moves at most one edge per step, so rule 1 extends its route before it can
     pass the end (checked on the ring in tests/test_demand.py).
  3. Fallback. A car that arrives anyway is re-inserted at once, with a new id, on a random
     car edge, and counted. N is then short by one for at least one step, which the N check
     reports.

N counts the cars on a lane plus the cars in mid-teleport (SUMO keeps those out of
vehicle.getIDList()). SUMO's summary output counts both as "running".
"""
import heapq
import os
import random
import re
import sys

VAR_ROUTE_ID = 0x53      # traci.constants.VAR_ROUTE_ID
VAR_ROUTE_INDEX = 0x69   # traci.constants.VAR_ROUTE_INDEX
SUBSCRIBED = (VAR_ROUTE_INDEX, VAR_ROUTE_ID)
STEP_FIELDS = ("time_s", "on_road", "teleporting", "teleport_starts", "arrived")

TELEPORT_START = re.compile(r"Teleporting vehicle '([^']+)'; (.+?), lane='[^']*', time=(\d+(?:\.\d+)?)")
TELEPORT_END = re.compile(r"Vehicle '([^']+)' (?:ends teleporting on edge|teleports beyond arrival edge) "
                          r"'[^']*', time=(\d+(?:\.\d+)?)")


# --- network and initial placement -------------------------------------------------------------

def _sumo_tools():
    """Append $SUMO_HOME/tools to the import path before sumolib or traci is imported, as
    runner._import_traci does, so both load with only SUMO_HOME set (member D's report, 30 Oct
    2026). Appended, so a pip-installed sumolib or traci, if any, still takes precedence."""
    home = os.environ.get("SUMO_HOME")
    if home:
        tools = os.path.join(home, "tools")
        if tools not in sys.path:
            sys.path.append(tools)


def _sumolib():
    """sumolib, after _sumo_tools()."""
    _sumo_tools()
    import sumolib
    return sumolib


def car_lanes(net_path):
    """[(edge id, length m, [lane indices allowing passenger cars])] for the normal edges."""
    sumolib = _sumolib()   # see docs/guide.html, section 1

    out = []
    for e in sumolib.net.readNet(str(net_path)).getEdges():
        lanes = [ln.getIndex() for ln in e.getLanes() if ln.allows("passenger")]
        if lanes:
            out.append((e.getID(), e.getLength(), lanes))
    return out


def baseline_destinations(baseline_lanes, variant_lanes):
    """Destination edges of a planning variant (T4-D2): the baseline's car edges that the
    variant still has, so a variant changes the roads but not the trips.

    baseline_lanes, variant_lanes: car_lanes() of the two nets. Returns (destinations, dropped,
    new), each sorted: dropped = baseline car edges missing from the variant (a closure), new =
    variant car edges missing from the baseline (a new link), which are never destinations.
    Edges are matched by id: a split keeps its first piece (same id) as a destination and its other
    pieces count as new; a renamed edge counts as dropped and its replacement as new.
    """
    base = {e for e, *_ in baseline_lanes}
    var = {e for e, *_ in variant_lanes}
    return sorted(base & var), sorted(base - var), sorted(var - base)


def initial_routes(lanes, n, vehicle, jitter_m, seed):
    """Text of vehicles.rou.xml: n cars at rest, spread evenly over all car lanes at t = 0.

    lanes: car_lanes(); vehicle: the vType attributes (config [vehicle]); jitter_m: each car is
    moved by up to +- jitter_m from its even spacing. The same placement as task 3's pilot
    (scripts/city_pilot_density.py write_run), byte for byte, so runs stay comparable. Every car
    starts with a one-edge route; the controller gives it a destination when it departs.
    """
    lo0 = vehicle["length"] + vehicle["minGap"] + jitter_m
    slots = [(eid, ln, lo0, length - jitter_m) for eid, length, idx in sorted(lanes)
             for ln in idx if length - jitter_m > lo0]
    usable = sum(hi - lo for *_, lo, hi in slots)
    spacing = usable / n
    if spacing - 2 * jitter_m < vehicle["length"] + vehicle["minGap"]:
        raise ValueError(f"{n} vehicles do not fit on {usable:.0f} m of usable lane length")
    rng = random.Random(seed)
    attrs = " ".join(f'{a}="{x}"' for a, x in vehicle.items())
    out = ["<routes>", f'    <vType id="car" {attrs}/>']
    slot, start = 0, 0.0
    for i in range(n):
        s = (i + 0.5) * spacing + rng.uniform(-jitter_m, jitter_m)
        while s > start + (slots[slot][3] - slots[slot][2]):
            start += slots[slot][3] - slots[slot][2]
            slot += 1
        eid, ln, lo, _ = slots[slot]
        out.append(f'    <vehicle id="v{i}" type="car" depart="0" departLane="{ln}" '
                   f'departPos="{lo + (s - start):.3f}" departSpeed="0"><route edges="{eid}"/>'
                   f'</vehicle>')
    out.append("</routes>")
    return "\n".join(out) + "\n"


def near_sets(length, incoming, distance_m):
    """{destination edge: set of edges whose downstream end lies < distance_m before the
    destination's downstream end, by the shortest path}. The destination itself is included.

    length: {edge: m}; incoming: {edge: edges with a connection into it}. Internal (junction)
    lanes are ignored, which shortens every path, so the sets are if anything too large.
    """
    out = {}
    for dest in length:
        dist, heap = {dest: 0.0}, [(0.0, dest)]
        while heap:
            d, e = heapq.heappop(heap)
            if d > dist.get(e, float("inf")):
                continue
            for p in incoming.get(e, ()):
                dp = d + length[e]   # from the end of p across all of e
                if dp < distance_m and dp < dist.get(p, float("inf")):
                    dist[p] = dp
                    heapq.heappush(heap, (dp, p))
        out[dest] = frozenset(dist)
    return out


def net_near_sets(net_path, distance_m):
    """near_sets() for a SUMO net, over all connections between normal edges."""
    sumolib = _sumolib()

    net = sumolib.net.readNet(str(net_path))
    length = {e.getID(): e.getLength() for e in net.getEdges()}
    incoming = {e.getID(): [p.getID() for p in e.getIncoming()] for e in net.getEdges()}
    return near_sets(length, incoming, distance_m)


def car_successors(net_path):
    """{car edge: edges a passenger car can turn into from it} (connections between car lanes)."""
    sumolib = _sumolib()

    out = {}
    for e in sumolib.net.readNet(str(net_path)).getEdges():
        if any(ln.allows("passenger") for ln in e.getLanes()):
            out[e.getID()] = {to.getID() for to, conns in e.getOutgoing().items()
                              if any(c.getFromLane().allows("passenger") and c.getToLane().allows("passenger")
                                     for c in conns)}
    return out


def outside_largest_scc(succ):
    """Nodes of the directed graph succ ({node: successors}) outside its largest strongly
    connected component, sorted. Empty when every node can reach every other one, which a
    destination drawn uniformly over the nodes needs (Kosaraju's algorithm, iterative)."""
    nodes = sorted(set(succ) | {w for ws in succ.values() for w in ws})
    order, seen = [], set()
    for v0 in nodes:                       # pass 1: nodes by finishing time
        if v0 in seen:
            continue
        seen.add(v0)
        stack = [(v0, iter(sorted(succ.get(v0, ()))))]
        while stack:
            v, it = stack[-1]
            w = next((w for w in it if w not in seen), None)
            if w is None:
                stack.pop()
                order.append(v)
            else:
                seen.add(w)
                stack.append((w, iter(sorted(succ.get(w, ())))))
    pred = {v: [] for v in nodes}
    for v, ws in succ.items():
        for w in ws:
            pred[w].append(v)
    comp, comps = {}, []
    for v0 in reversed(order):             # pass 2: components on the reversed graph
        if v0 in comp:
            continue
        comps.append([v0])
        comp[v0] = len(comps) - 1
        stack = [v0]
        while stack:
            for w in pred[stack.pop()]:
                if w not in comp:
                    comp[w] = comp[v0]
                    comps[-1].append(w)
                    stack.append(w)
    largest = set(max(comps, key=len, default=[]))
    return [v for v in nodes if v not in largest]


# --- the controller ----------------------------------------------------------------------------

class ConstantDensity:
    """controller(conn, time_s) for runner.run_traci: keeps N cars in the network (rules 1-3 above).

    n_vehicles: N; dests: destination edges (uniform draw); seed: seed of the destination draws;
    remaining_edges: rule 1; near: net_near_sets(net, guard_m) for rule 2, or None to switch it
    off; step_s: step length (s); verify_routes: also read every car's live route every step and
    count where the cached route differs (slow; for checking the controller).

    After the run, `steps` holds one row per step (STEP_FIELDS; time_s is SUMO's time stamp of
    the step, as in summary.xml and log.txt), `teleport_times` the start time of every teleport,
    and record() / checks() the counts and checks for the run record.
    """

    def __init__(self, n_vehicles, dests, seed, remaining_edges=3, near=None, step_s=1.0,
                 verify_routes=False, traci_exception=None):
        if traci_exception is None:
            _sumo_tools()
            from traci.exceptions import TraCIException as traci_exception
        self.exc = traci_exception
        self.n = n_vehicles
        self.dests = list(dests)
        self.rng = random.Random(seed)
        self.remaining = remaining_edges
        self.near = near
        self.step_s = step_s
        self.verify = verify_routes
        self.routes = {}            # vid -> (route id when read, route edges); id None = re-read
        self.teleporting = set()
        self.steps, self.teleport_times = [], []
        self.reinserted_ids = []
        self.counts = dict(inserted=0, arrived=0, reinserted=0, retargets=0, guard_retargets=0,
                           retarget_failed=0, route_reads=0, route_cache_mismatches=0)

    # the destination draw of task 3's pilot; with near=None identical to it, call for call
    def _retarget(self, conn, vid):
        c = self.counts
        route, idx = conn.vehicle.getRoute(vid), conn.vehicle.getRouteIndex(vid)
        for _ in range(20):
            dest = self.rng.choice(self.dests)
            if dest in (route[-1], route[idx]):
                continue
            if self.near is not None and route[idx] in self.near.get(dest, ()):
                continue   # rule 2: the new route end would lie within guard_m of the car
            try:
                path = conn.simulation.findRoute(route[-1], dest, vType="car").edges
                if len(path) < 2:
                    continue
                conn.vehicle.setRoute(vid, list(route[idx:]) + list(path[1:]))
                c["retargets"] += 1
                self.routes[vid] = (None, None)   # read the new route when it is next needed
                return True
            except self.exc:
                continue
        c["retarget_failed"] += 1
        return False

    def _edges(self, conn, vid, route_id):
        """The car's live route. Re-read only when SUMO gave it a new route id (the rerouting
        device and setRoute both create one) or after the controller changed it."""
        cached_id, edges = self.routes.get(vid, (None, None))
        if self.verify and edges is not None and cached_id == route_id:
            live = tuple(conn.vehicle.getRoute(vid))
            if live != edges:
                self.counts["route_cache_mismatches"] += 1
                self.routes[vid] = (route_id, live)
            return live
        if cached_id != route_id or edges is None:
            edges = tuple(conn.vehicle.getRoute(vid))
            self.counts["route_reads"] += 1
            self.routes[vid] = (route_id, edges)
        return edges

    def _reinsert(self, conn, vid):
        k = self.counts["reinserted"] + 1
        new_id, route_id = f"{vid}~r{k}", f"!reinsert{k}"
        conn.route.add(route_id, [self.rng.choice(self.dests)])
        conn.vehicle.add(new_id, route_id, typeID="car", depart="now", departLane="best",
                         departPos="random_free", departSpeed="0")
        self.counts["reinserted"] = k
        self.reinserted_ids.append(new_id)

    def __call__(self, conn, time_s):
        c = self.counts
        t = time_s - self.step_s
        departed = conn.simulation.getDepartedIDList()   # SUMO's order: fixes who gets which destination
        for vid in departed:
            c["inserted"] += 1
            conn.vehicle.subscribe(vid, SUBSCRIBED)
            self._retarget(conn, vid)
        starting = conn.simulation.getStartingTeleportIDList()
        self.teleporting.update(starting)
        self.teleporting.difference_update(conn.simulation.getEndingTeleportIDList())
        self.teleport_times.extend([t] * len(starting))
        arrived = conn.simulation.getArrivedIDList()
        for vid in arrived:
            self.teleporting.discard(vid)   # a car can teleport beyond its route end
            self.routes.pop(vid, None)
        c["arrived"] += len(arrived)

        results = conn.vehicle.getAllSubscriptionResults()
        for vid in sorted(results):   # libsumo's order (a sorted map), on TraCI too
            res = results[vid]
            if not res:
                continue
            idx = res[VAR_ROUTE_INDEX]
            edges = self._edges(conn, vid, res[VAR_ROUTE_ID])
            if idx >= len(edges) - self.remaining:                       # rule 1
                self._retarget(conn, vid)
            elif self.near is not None and edges[idx] in self.near.get(edges[-1], ()):   # rule 2
                if self._retarget(conn, vid):
                    c["guard_retargets"] += 1
        for vid in arrived:                                              # rule 3
            self._reinsert(conn, vid)
        self.steps.append((t, conn.vehicle.getIDCount(), len(self.teleporting), len(starting), len(arrived)))

    def n_series(self):
        """N in the network after every step: cars on a lane + cars in mid-teleport."""
        return [on + tp for _, on, tp, _, _ in self.steps]

    def record(self):
        n = self.n_series()
        return dict(self.counts, n_vehicles=self.n, n_min=min(n, default=0), n_max=max(n, default=0),
                    n_short_steps=sum(x != self.n for x in n), teleports=len(self.teleport_times),
                    mid_teleport_max=max((s[2] for s in self.steps), default=0),
                    reinserted_ids=self.reinserted_ids)

    def checks(self):
        n = self.n_series()
        return {"n_exact_every_step": bool(n) and min(n) == max(n) == self.n}


# --- teleports and settledness -----------------------------------------------------------------

def teleport_events(log):
    """(start times, end times) of the teleports in a SUMO log (s). A teleport beyond the
    route end counts as an end: that car leaves the network."""
    starts = [float(m.group(3)) for m in TELEPORT_START.finditer(log)]
    ends = [float(m.group(2)) for m in TELEPORT_END.finditer(log)]
    return starts, ends


def teleport_count(log):
    """Number of teleports in a SUMO log: SUMO warns 'Teleporting vehicle ...' once per teleport.
    A plain text count, so it cross-checks teleport_events(), which parses each line."""
    return log.count("Teleporting vehicle '")


def mid_teleport_counts(starts, ends, times):
    """Cars in mid-teleport after the step at each time: teleports started minus ended so far."""
    s, e = sorted(starts), sorted(ends)
    out, i, j = [], 0, 0
    for t in times:
        while i < len(s) and s[i] <= t:
            i += 1
        while j < len(e) and e[j] <= t:
            j += 1
        out.append(i - j)
    return out


def block_means(times, values, block_s, end_s):
    """Mean of values per block [b*block_s, (b+1)*block_s), for the complete blocks before end_s."""
    n_blocks = int(end_s // block_s)
    sums, counts = [0.0] * n_blocks, [0] * n_blocks
    for t, v in zip(times, values):
        b = int(t // block_s)
        if 0 <= b < n_blocks:
            sums[b] += v
            counts[b] += 1
    return [s / k if k else float("nan") for s, k in zip(sums, counts)]


def teleports_per_car_hour(start_times, n_vehicles, t0, t1):
    """Teleports that started in [t0, t1), per car and per hour of that window."""
    count = sum(t0 <= t < t1 for t in start_times)
    return count / (n_vehicles * (t1 - t0) / 3600)


def settle_window_ok(end_s, warmup_s, block_s):
    """True when the last two complete blocks before end_s cover the run's tail and lie inside
    the measurement window, so settle_ratio() measures what T3-D9 says (last 30 min / the 30
    min before, both after the warm-up): end_s is a whole number of blocks and
    end_s - 2 x block_s >= warmup_s."""
    return bool(end_s % block_s == 0 and end_s - 2 * block_s >= warmup_s)


def settle_ratio(block_flows):
    """T3-D9 trial: flow in the last block / flow in the block before (NaN if fewer than 2)."""
    if len(block_flows) < 2 or not block_flows[-2] > 0:
        return float("nan")
    return block_flows[-1] / block_flows[-2]


def is_settled(ratio, lo=0.9, hi=1.1):
    """True when the settledness ratio lies within [lo, hi]."""
    return bool(lo <= ratio <= hi)
