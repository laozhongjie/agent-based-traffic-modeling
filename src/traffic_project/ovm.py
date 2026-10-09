"""OVM theory and a reference integrator, matching SUMO's carFollowModel="OVM" (sumo/ovm/).

Parameters are a dict with the SUMO vType attribute names: alpha (1/s), sc (m), d (m),
maxSpeed (m/s), length (m) and optionally minGap (m, default 0). A config's [vtype] table
can be passed directly.

s is SUMO's gap: bumper to bumper minus minGap, so V(0) = 0 means a jam stops at minGap.
On a ring of length L with N vehicles, the uniform gap is s0 = L/N - length - minGap.
"""
import cmath
import math


def optimal_speed(s, p):
    """V(s) = maxSpeed * (tanh((s - sc)/d) + tanh(sc/d)) / (1 + tanh(sc/d))."""
    t = math.tanh(p["sc"] / p["d"])
    return p["maxSpeed"] * (math.tanh((s - p["sc"]) / p["d"]) + t) / (1 + t)


def optimal_speed_slope(s, p):
    """V'(s), in 1/s."""
    t = math.tanh(p["sc"] / p["d"])
    return p["maxSpeed"] / (p["d"] * (1 + t)) / math.cosh((s - p["sc"]) / p["d"]) ** 2


def uniform_gap(n, ring_length, p):
    """Gap s0 of N evenly spaced vehicles on a ring."""
    return ring_length / n - p["length"] - p.get("minGap", 0)


def growth_rate(n, s0, p, dt=None):
    """Largest growth rate (1/s) of a small perturbation of uniform flow on a ring of N vehicles.

    A positive value means uniform flow is unstable. The ring's modes are k = 2 pi m / N, m = 1..N-1.
    dt=None gives the continuous model, dv/dt = alpha (V(s) - v): for long rings the rate becomes
    positive at V'(s0) = alpha/2. A step length dt gives the discrete scheme SUMO integrates
    (see integrate), whose threshold differs near V'(s0) = alpha/2.
    """
    alpha, slope = p["alpha"], optimal_speed_slope(s0, p)
    best = -math.inf
    for m in range(1, n):
        c = alpha * slope * (cmath.exp(2j * math.pi * m / n) - 1)
        if dt is None:
            # z^2 + alpha z - c = 0 for a perturbation exp(i k n + z t)
            roots = [(-alpha + sign * cmath.sqrt(alpha ** 2 + 4 * c)) / 2 for sign in (1, -1)]
            best = max(best, *(z.real for z in roots))
        else:
            # one step maps (x, v) to (x + dt v', v'), v' = (1 - alpha dt) v + dt c x
            b = 1 - alpha * dt
            trace, det = 1 + dt * dt * c + b, b
            disc = cmath.sqrt(trace ** 2 - 4 * det)
            best = max(best, *(math.log(abs((trace + sign * disc) / 2)) / dt for sign in (1, -1)))
    return best


def integrate(x, p, ring_length, dt, steps):
    """Integrate N vehicles on a ring from rest, the way SUMO does by default.

    x: front positions in m along the ring. Each step, every vehicle computes
    v' = max(0, v + dt alpha (V(s) - v)) from the current gaps, then x' = x + dt v'.
    Yields (step, x, v) for step = 0 .. steps, with positions wrapped to [0, ring_length).
    """
    n = len(x)
    x = list(x)
    v = [0.0] * n
    order = sorted(range(n), key=lambda i: x[i])
    leader = {order[j]: order[(j + 1) % n] for j in range(n)}
    off = p["length"] + p.get("minGap", 0)
    yield 0, list(x), list(v)
    for step in range(1, steps + 1):
        gaps = [(x[leader[i]] - x[i]) % ring_length - off for i in range(n)]
        v = [max(0.0, v[i] + dt * p["alpha"] * (optimal_speed(gaps[i], p) - v[i])) for i in range(n)]
        x = [(x[i] + dt * v[i]) % ring_length for i in range(n)]
        yield step, list(x), list(v)
