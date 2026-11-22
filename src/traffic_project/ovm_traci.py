
"""TraCI controller for Python OVM on the four-edge SUMO ring."""

from traffic_project.ovm_gw import ovm_next_speed


def calculate_ovm_speeds_from_state(
    state,
    ring_length,
    dt=0.1,
    alpha=1.0,
    v_max=30.0,
    h_c=25.0,
    h_scale=5.0,
    min_gap=2.0,
):
    """Calculate one synchronous OVM update from subscribed vehicle state."""
    if len(state) < 2:
        raise RuntimeError("At least two vehicles required")
    state = list(state)
    state.sort(key=lambda car: car["position"])

    updates = {}

    for i, car in enumerate(state):
        leader = state[(i + 1) % len(state)]

        distance = (
            leader["position"] - car["position"]
        ) % ring_length

        physical_gap = distance - leader["length"]

        if physical_gap < -1e-6:
            raise RuntimeError(
                f"Vehicle overlap detected: {car['id']}"
            )

        # Match the convention used by the existing ovm.py.
        effective_gap = max(
            0.0,
            physical_gap - min_gap,
        )

        updates[car["id"]] = ovm_next_speed(
            speed=car["speed"],
            headway=effective_gap,
            dt=dt,
            alpha=alpha,
            v_max=v_max,
            h_c=h_c,
            h_scale=h_scale,
        )

    return updates


def calculate_ovm_speeds(
    conn,
    ring_length,
    dt=0.1,
    alpha=1.0,
    v_max=30.0,
    h_c=25.0,
    h_scale=5.0,
    min_gap=2.0,
    expected_vehicles=None,
):
    """Reference getter-based update, retained for checks and small runs."""
    ids = list(conn.vehicle.getIDList())
    if expected_vehicles is not None and len(ids) != expected_vehicles:
        raise RuntimeError(f"Expected {expected_vehicles} vehicles, found {len(ids)}")

    edge_length = ring_length / 4.0
    state = []
    for vid in ids:
        edge_id = conn.vehicle.getRoadID(vid)
        if edge_id not in ("e0", "e1", "e2", "e3"):
            raise RuntimeError(f"Unexpected edge {edge_id} for {vid}")
        state.append({
            "id": vid,
            "position": (int(edge_id[1:]) * edge_length
                         + conn.vehicle.getLanePosition(vid)) % ring_length,
            "speed": conn.vehicle.getSpeed(vid),
            "length": conn.vehicle.getLength(vid),
        })

    return calculate_ovm_speeds_from_state(
        state, ring_length, dt, alpha, v_max, h_c, h_scale, min_gap,
    )


def make_ovm_controller(
    ring_length,
    dt=0.1,
    alpha=1.0,
    v_max=30.0,
    h_c=25.0,
    h_scale=5.0,
    min_gap=2.0,
    expected_vehicles=None,
):
    """Return a callback compatible with runner.run_traci()."""

    configured = set()
    constants = None

    def controller(conn, time_s):
        nonlocal constants
        if constants is None:
            from traci import constants

        ids = list(conn.vehicle.getIDList())

        if expected_vehicles is not None and len(ids) != expected_vehicles:
            raise RuntimeError(f"Expected {expected_vehicles} vehicles, found {len(ids)}")

        for vid in ids:
            if vid not in configured:
                conn.vehicle.setSpeedMode(vid, 96)
                conn.vehicle.setLaneChangeMode(vid, 0)
                conn.vehicle.subscribe(vid, [
                    constants.VAR_ROAD_ID,
                    constants.VAR_LANEPOSITION,
                    constants.VAR_SPEED,
                    constants.VAR_LENGTH,
                ])
                configured.add(vid)

        edge_length = ring_length / 4.0
        subscribed = conn.vehicle.getAllSubscriptionResults()
        state = []
        for vid in ids:
            values = subscribed.get(vid)
            if values is None:
                # Defensive fallback for a TraCI version that delays the first
                # subscription result until the following simulation step.
                edge_id = conn.vehicle.getRoadID(vid)
                local_pos = conn.vehicle.getLanePosition(vid)
                speed = conn.vehicle.getSpeed(vid)
                length = conn.vehicle.getLength(vid)
            else:
                edge_id = values[constants.VAR_ROAD_ID]
                local_pos = values[constants.VAR_LANEPOSITION]
                speed = values[constants.VAR_SPEED]
                length = values[constants.VAR_LENGTH]

            if edge_id not in ("e0", "e1", "e2", "e3"):
                raise RuntimeError(f"Unexpected edge {edge_id} for {vid}")
            state.append({
                "id": vid,
                "position": (int(edge_id[1:]) * edge_length + local_pos) % ring_length,
                "speed": speed,
                "length": length,
            })

        updates = calculate_ovm_speeds_from_state(
            state=state,
            ring_length=ring_length,
            dt=dt,
            alpha=alpha,
            v_max=v_max,
            h_c=h_c,
            h_scale=h_scale,
            min_gap=min_gap,
        )

        for vid, speed in updates.items():
            conn.vehicle.setSpeed(vid, float(speed))

    return controller
