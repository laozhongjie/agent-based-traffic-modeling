"""
Creating a Bando-style OVM
1. 
"""
import cmath
import math
import numpy as np


def optimal_velocity(h, v_max=30.0, h_c=25.0, h_scale=5.0):
    """Bando-style optimal velocity, in m/s."""

    if h_scale <= 0: raise ValueError("h_scale must be positive")
    h = np.maximum(np.asarray(h, dtype=float), 0.0)
    return v_max * (np.tanh((h - h_c) / h_scale) + np.tanh(h_c / h_scale)) / (1.0 + np.tanh(h_c / h_scale))


def acceleration(v, h, alpha=1.0, v_max=30.0, h_c=25.0, h_scale=5.0):
    """OVM acceleration, in m/s²."""
    return alpha * (optimal_velocity(h, v_max, h_c, h_scale) - v)


def next_speed(v, h, dt, alpha=1.0, v_max=30.0, h_c=25.0, h_scale=5.0):
    """Forward-Euler velocity update."""
    a = acceleration(v, h, alpha, v_max, h_c, h_scale)
    return float(np.clip(v + dt * a, 0.0, v_max))


def ovm_acceleration(speed, headway, alpha=1.0, v_max=30.0, h_c=25.0, h_scale=5.0,):
    """Calculate OVM acceleration in m/s²."""

    desired_speed = optimal_velocity(headway, v_max=v_max, h_c=h_c, h_scale=h_scale,)

    return alpha * (desired_speed - speed)


def ovm_next_speed(speed, headway, dt=0.1, alpha=1.0, v_max=30.0, h_c=25.0, h_scale=5.0,):
    """Advance vehicle speed by one Euler time step."""

    if dt <= 0:
        raise ValueError("dt must be positive")

    acceleration = ovm_acceleration(speed=speed, headway=headway, alpha=alpha, v_max=v_max, h_c=h_c, h_scale=h_scale,)
    new_speed = speed + acceleration * dt

    return float(np.clip(new_speed, 0.0, v_max))

