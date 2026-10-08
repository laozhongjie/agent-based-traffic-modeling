"""The data interface between the experiments (B, C, D) and the analysis (E).

Every experiment writes two kinds of files into results/<scenario>/, which is in git:

    <name>.csv              summary table, one row per run       write_summary()
    <name>/<run_id>.csv     time series of one run               write_timeseries()

Both writers check the rows against the columns below and raise ValueError
on a missing column, a value outside its range, or an unprefixed extra column.

For analysis and notebooks, load_summary() and load_timeseries() read the same
files back as pandas DataFrames with numeric columns.
The same definitions hold for the ring and the city network: density is the
number of vehicles divided by the total lane length, mean speed is the
space-mean speed of all vehicles, and flow = density * mean speed.
"""
import math

from . import ROOT
from .io import write_csv

# Required summary columns, in file order: (name, unit, check)
SUMMARY = [
    ("run_id", "", None),
    ("scenario", "", None),
    ("model", "", None),
    ("variant", "", None),                  # planning variant; empty when none
    ("seed", "", None),
    ("density_veh_km", "veh/km", lambda x: x > 0),
    ("mean_speed_mps", "m/s", lambda x: x >= 0),
    ("flow_veh_h", "veh/h", lambda x: x >= 0),
    ("congested_fraction", "", lambda x: 0 <= x <= 1),
    ("congested_fraction_var", "", lambda x: x >= 0),
    ("valid", "", None),
]
# Time-series columns, one row per sample time
TIMESERIES = [
    ("time_s", "s", lambda x: x >= 0),
    ("density_veh_km", "veh/km", lambda x: x >= 0),
    ("mean_speed_mps", "m/s", lambda x: x >= 0),
    ("flow_veh_h", "veh/h", lambda x: x >= 0),
    ("congested_fraction", "", lambda x: 0 <= x <= 1),
]


def _check(rows, spec, where, extra_prefix=None):
    names = [n for n, _, _ in spec]
    problems = []
    for i, row in enumerate(rows):
        for name, _, ok in spec:
            if name not in row:
                problems.append(f"row {i}: missing column '{name}'")
            elif ok is not None:
                x = row[name]
                if not isinstance(x, (int, float)) or math.isnan(x) or not ok(x):
                    problems.append(f"row {i}: {name} = {x!r} is out of range")
        if extra_prefix is not None:
            for key in row:
                if key not in names and not key.startswith(extra_prefix):
                    problems.append(f"row {i}: extra column '{key}' must start with '{extra_prefix}'")
    if problems:
        raise ValueError(f"{where} does not match the data interface:\n  " + "\n  ".join(problems[:20]))


def write_summary(rows, cfg):
    """Write results/<scenario>/<name>.csv. Extra columns must start with '<scenario>_'."""
    prefix = cfg["scenario"] + "_"
    rows = [{k: v for k, v in r.items() if k != "checks"} for r in rows]
    _check(rows, SUMMARY, f"summary table '{cfg['name']}'", extra_prefix=prefix)
    names = [n for n, _, _ in SUMMARY]
    extra = sorted({k for r in rows for k in r if k not in names})
    path = ROOT / "results" / cfg["scenario"] / f"{cfg['name']}.csv"
    write_csv(rows, path, names + extra)
    return path


def load_summary(scenario, name):
    """Read results/<scenario>/<name>.csv as a pandas DataFrame.

    Numbers come back as numbers, valid as bool, and an empty variant as "".
    Example: load_summary("ring", "idm_sweep")
    """
    import pandas as pd

    path = ROOT / "results" / scenario / f"{name}.csv"
    text = {"run_id": str, "scenario": str, "model": str, "variant": str}
    df = pd.read_csv(path, dtype=text)
    df["variant"] = df["variant"].fillna("")
    return df


def load_timeseries(scenario, name, run_id):
    """Read results/<scenario>/<name>/<run_id>.csv as a pandas DataFrame.

    Example: load_timeseries("ring", "idm_sweep", "ring_idm_L1000_n50_s1")
    """
    import pandas as pd

    return pd.read_csv(ROOT / "results" / scenario / name / f"{run_id}.csv")


def write_timeseries(run_id, rows, cfg):
    """Write results/<scenario>/<name>/<run_id>.csv."""
    _check(rows, TIMESERIES, f"time series of {run_id}")
    path = ROOT / "results" / cfg["scenario"] / cfg["name"] / f"{run_id}.csv"
    write_csv(rows, path, [n for n, _, _ in TIMESERIES])
    return path
