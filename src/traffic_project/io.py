"""Read SUMO outputs and write result tables."""
import csv
import xml.etree.ElementTree as ET
from pathlib import Path


def iter_fcd(path):
    """Yield (time_s, vehicles) for every time step of an FCD output file.

    Each vehicle is a dict with id, lane, pos (m from the lane start) and speed (m/s).
    The file is streamed, so large outputs do not need to fit in memory.
    """
    for _, el in ET.iterparse(path):
        if el.tag == "timestep":
            vehicles = [{"id": v.get("id"), "lane": v.get("lane"),
                         "pos": float(v.get("pos")), "speed": float(v.get("speed"))} for v in el]
            yield float(el.get("time")), vehicles
            el.clear()


def iter_summary(path):
    """Yield (time_s, running) for every step of a SUMO summary-output file.

    running counts the vehicles inserted and not yet arrived, including a vehicle in
    mid-teleport, which the FCD output leaves out until the teleport ends.
    """
    for _, el in ET.iterparse(path):
        if el.tag == "step":
            yield float(el.get("time")), int(el.get("running"))
            el.clear()


def write_csv(rows, path, columns):
    """Write rows (dicts) to a CSV file with the given column order."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def read_csv(path):
    with Path(path).open() as f:
        return list(csv.DictReader(f))
