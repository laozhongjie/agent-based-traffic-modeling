"""Utilities for converting SUMO FCD XML trajectories into speed heatmaps.

Example
-------
from pathlib import Path
from fcd_heatmap import load_fcd_for_heatmap, make_speed_matrix

root = Path('/path/to/project')
df = load_fcd_for_heatmap(600, 30, 1, root=root,
                          time_start=100, time_end=500)
speed_matrix = make_speed_matrix(df, 600, time_start=100,
                                 time_end=500, spatial_bin=50,
                                 temporal_bin=10)
"""

from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd


def iter_fcd(fcd_path):
    """Yield (time, vehicles) from a SUMO FCD XML file, streaming timesteps.

    Vehicle records contain lane, pos, and speed fields.
    """
    context = ET.iterparse(str(fcd_path), events=("start", "end"))
    _, root = next(context)
    for event, elem in context:
        if event == "end" and elem.tag == "timestep":
            t = float(elem.attrib["time"])
            vehicles = [
                {
                    "lane": vehicle.attrib["lane"],
                    "pos": float(vehicle.attrib["pos"]),
                    "speed": float(vehicle.attrib["speed"]),
                }
                for vehicle in elem.iter("vehicle")
            ]
            yield t, vehicles
            root.clear()


def load_fcd_for_heatmap(length, n_vehicles, seed, *, root, time_start, time_end):
    """Load vehicle observations from a four-edge SUMO ring road.

    Parameters
    ----------
    length : float
        Total ring length in meters.
    n_vehicles : int
        Number of vehicles used in the run name.
    seed : int
        Random seed used in the run name.
    root : str or pathlib.Path
        Project directory containing the ``runs`` folder.
    time_start, time_end : float
        Inclusive start and exclusive end of the observation window (seconds).

    Returns
    -------
    pandas.DataFrame
        Columns: time (s), position (m), speed (m/s).
    """
    if length <= 0 or time_end <= time_start:
        raise ValueError("Require length > 0 and time_end > time_start")

    run_id = f"ring_nasch_L{length}_n{n_vehicles}_s{seed}"
    fcd_path = Path(root) / "runs" / run_id / "fcd.xml"
    if not fcd_path.exists():
        raise FileNotFoundError(
            f"Missing FCD file:\n{fcd_path}\nCheck the seed and run directory."
        )

    records = []
    edge_length = length / 4
    for t, vehicles in iter_fcd(fcd_path):
        if not (time_start <= t < time_end):
            continue
        for vehicle in vehicles:
            edge_id = vehicle["lane"].rsplit("_", 1)[0]
            if edge_id not in {"e0", "e1", "e2", "e3"}:
                raise ValueError(f"Unexpected edge ID: {edge_id}")
            edge_index = int(edge_id[1:])
            x = (edge_index * edge_length + vehicle["pos"]) % length
            records.append({"time": t, "position": x, "speed": vehicle["speed"]})

    if not records:
        raise ValueError(f"No trajectory observations in {fcd_path}")
    return pd.DataFrame.from_records(records)


def make_speed_matrix(df, length, *, time_start, time_end,
                      spatial_bin=50, temporal_bin=10):
    """Return a time-by-position matrix of mean speeds (m/s).

    Rows represent time bins, columns represent position bins.
    Empty bins are NaN. Time is measured in seconds, distance in meters.
    """
    if length <= 0 or spatial_bin <= 0 or temporal_bin <= 0:
        raise ValueError("length, spatial_bin, and temporal_bin must be positive")
    if time_end <= time_start:
        raise ValueError("time_end must be greater than time_start")

    n_space = int(np.ceil(length / spatial_bin))
    n_time = int(np.ceil((time_end - time_start) / temporal_bin))
    df = df.copy()
    df["space_idx"] = np.floor(df["position"] / spatial_bin).astype(int).clip(0, n_space - 1)
    df["time_idx"] = np.floor((df["time"] - time_start) / temporal_bin).astype(int).clip(0, n_time - 1)

    matrix = (
        df.groupby(["time_idx", "space_idx"])["speed"]
        .mean()
        .unstack()
        .reindex(index=range(n_time), columns=range(n_space))
    )
    return matrix.to_numpy()
