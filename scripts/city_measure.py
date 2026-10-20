"""Measure finished city-network runs with the Task 3 congestion criterion.

One config, one command:
    python scripts/city_measure.py --config configs/city/criterion_check.toml

For every run folder matching [inputs] runs_glob it reads meta.json, the edgeData file at
the criterion period and summary.xml; the reference run is the folder on the same net with
seed = [measure] reference_seed. Writes
    results/city/<name>.csv                summary, one row per run (GUIDE columns + city_*)
    results/city/<name>_sensitivity.csv    all [measure.sensitivity] variants per run
    results/city/<name>/<run_id>.csv       time series (if [inputs] write_timeseries)
The reference runs themselves are not measured.
"""
import argparse
import glob
import json
from pathlib import Path

import pandas as pd

from traffic_project import ROOT, config, results
from traffic_project import congestion as cg
from traffic_project.measurements import city_summary


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", required=True)
    cfg = config.load(ap.parse_args().config)
    inp, m, warmup = cfg["inputs"], cfg["measure"], cfg["run"]["warmup_s"]
    runs = []
    for d in sorted(glob.glob(str(ROOT / inp["runs_glob"]))):
        meta = json.loads((Path(d) / inp["meta_file"]).read_text())
        runs.append((Path(d), meta))
    refs, nets = {}, {}
    for d, meta in runs:
        if meta["seed"] == m["reference_seed"] and meta["k_target"] == m["reference_density_veh_km"]:
            refs[meta["net"]] = d
    rows, sens = [], []
    for d, meta in runs:
        if d in refs.values():
            continue
        net_path = meta["net"]
        if net_path not in nets:
            nets[net_path] = cg.cycle_period(cg.read_net(net_path), m["period_s"])
        name = inp["edgedata_file"].format(period=nets[net_path])
        ref = refs[net_path]
        meas, checks, series = city_summary(d / name, ref / name, net_path, d / inp["summary_file"],
                                            m, warmup, ref_summary_xml=ref / inp["summary_file"],
                                            n_vehicles=meta.get("n_vehicles"))
        run_id = d.name
        row = dict(run_id=run_id, scenario=cfg["scenario"], model=cfg["model"], variant="",
                   seed=meta["seed"], **meas, city_net=meta.get("tag", Path(net_path).stem),
                   valid=all(checks.values()), checks=checks)
        rows.append(row)
        if inp.get("write_timeseries"):
            results.write_timeseries(run_id, series, cfg)
        t = cg.sensitivity_table(cg.read_edgedata(d / name), cg.read_edgedata(ref / name),
                                 cg.read_net(net_path), warmup, m)
        t.insert(0, "density_veh_km", meas["density_veh_km"])
        t.insert(0, "seed", meta["seed"])
        t.insert(0, "run_id", run_id)
        sens.append(t)
        print(run_id, "ok" if row["valid"] else f"INVALID: {[k for k, v in checks.items() if not v]}",
              flush=True)
    path = results.write_summary(rows, cfg)
    spath = path.with_name(f"{cfg['name']}_sensitivity.csv")
    pd.concat(sens).to_csv(spath, index=False)
    print("wrote", path.relative_to(ROOT), "and", spath.relative_to(ROOT))


if __name__ == "__main__":
    main()
