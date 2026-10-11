"""NaSch theory at p = 0 and a reference cellular automaton, for checking SUMO's carFollowModel="NaSch".

Units are cells and time steps. In SUMO (from 1.28.0) a cell is `accel` metres with step-length 1 s;
each vehicle fills one cell (length = cell, minGap = 0) and vmax = maxSpeed / cell. SUMO follows these
rules only on a lattice: the ring is a whole number of cells, vehicles start on cell boundaries,
speedDev = 0, and maxSpeed is no higher than the lane speed limit.
"""


def flow(rho, vmax):
    """Flow in vehicles per step at p = 0: J = min(rho vmax, 1 - rho), rho = vehicles per cell."""
    return min(rho * vmax, 1 - rho)


def mean_speed(rho, vmax):
    """Mean speed in cells per step at p = 0: J / rho = min(vmax, (1 - rho) / rho)."""
    return min(vmax, (1 - rho) / rho)


def integrate(cells, n_cells, vmax, steps):
    """Run the deterministic (p = 0) NaSch automaton from rest on a ring of n_cells.

    cells: the occupied cell of each vehicle. Each step, all vehicles update in parallel:
    v = min(v + 1, vmax), v = min(v, empty cells ahead), then move v cells.
    Yields (step, cells, speeds) for step = 0 .. steps.
    """
    n = len(cells)
    x = list(cells)
    v = [0] * n
    order = sorted(range(n), key=lambda i: x[i])
    leader = {order[j]: order[(j + 1) % n] for j in range(n)}
    yield 0, list(x), list(v)
    for step in range(1, steps + 1):
        gaps = [(x[leader[i]] - x[i] - 1) % n_cells for i in range(n)]
        v = [min(v[i] + 1, vmax, gaps[i]) for i in range(n)]
        x = [(x[i] + v[i]) % n_cells for i in range(n)]
        yield step, list(x), list(v)
