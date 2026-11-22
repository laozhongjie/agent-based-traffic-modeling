# Agent-Based Modeling of Traffic Congestion on Road Networks

[English](README.md) | [中文](README_zh.md)

We treat the onset of traffic congestion as a nonequilibrium phase transition and follow it from a single-lane ring road to the road network of Singapore's Bugis district, and to planning changes of that network. All simulations are agent-based and run in [SUMO](https://eclipse.dev/sumo/) with three car-following models: Nagel–Schreckenberg (NaSch), the optimal velocity model (OVM, implemented by us in C++) and the intelligent driver model (IDM).

**[Project website](https://laozhongjie.github.io/agent-based-traffic-modeling/)**: interactive model explanations and all ring, city and planning results, in English and Chinese.

## Research questions

1. **Highway.** What is the critical density on a road without traffic lights, and does the transition behave like a phase transition? How does it depend on the model, randomness and system size, and does it match real highway data?
2. **City network.** Does a city network have a density at which total throughput peaks and then falls? Do local jams merge into large congested regions, and how does network structure decide where congestion starts?
3. **Planning.** Do road closures or new links raise or lower the network's critical density and maximum flow? Can adding a road make things worse (Braess's paradox)?

## Main results

- **Ring road.** Free flow breaks into backward-moving stop-and-go waves above a critical density of about 20–25 veh/km (NaSch), 25 veh/km (OVM) and 30–35 veh/km (IDM), with no visible dependence on ring length between 600 and 4800 m. Linear stability analysis places the IDM threshold at 32.9 veh/km. Less randomness or faster driver response moves the onset to higher density. Freeway data (PeMS) peak in flow at 19–21 veh/km per lane and show signs of hysteresis.
- **City network.** The mean speed of the Bugis network halves at 13.3 veh/km per lane, while the flow levels off at about 171 veh/h per lane. Neither fluctuations nor recovery time peak there, so it is a smooth crossover rather than a critical point. Local jams merge into one large cluster between 20 and 25 veh/km; edge betweenness barely predicts where congestion starts once traffic load is controlled for.
- **Planning.** Closing the most central removable road segment lowers the critical density by 0.45 veh/km (3.4%). A lane cut and a new link change it by less than the seed-to-seed spread, and no network-wide Braess paradox is found.

## Team

| Member | Main work |
|---|---|
| A | Project lead: research plan, shared framework and pipeline, SUMO build and OVM implementation, model validation, website |
| B | Vehicle models; ring-road experiments |
| C | City network: MFD, clusters, spreading and critical-point analyses; LTA data |
| D | Planning scenarios and Braess test |
| E | IDM equilibrium and linear stability; PeMS freeway analysis; discussion |

## Repository layout

```text
.
├── sumo/                 # Pinned SUMO version, OVM source files, patch, validation checks
├── src/traffic_project/  # Shared Python package: configs, runner, measurements, controller
├── configs/              # One TOML file per experiment (parameters, densities, seeds)
├── scenarios/            # Ring, grid and Bugis networks and the scripts that build them
├── scripts/              # Command-line entry points for sweeps, analyses and figures
├── results/              # Summary tables, time series and figures of all valid runs
├── data/processed/       # Processed external data (LTA speed bands)
├── notebooks/            # Analysis notebooks of the members
├── tests/                # Automated tests (pytest)
└── docs/                 # Project website (GitHub Pages)
```

Run directories (`runs/`) and raw data are not tracked because of their size. Every row in `results/` keeps the ID of the run it came from, and each run can be repeated from its configuration file and seed. The shared conventions (units, run IDs, checks) are in [GUIDE.md](GUIDE.md).

## Reproducing the results

```bash
conda env create -f environment.yml
conda activate traffic
```

NaSch and IDM need the official SUMO 1.28.0 release. The C++ OVM needs SUMO 1.28.0 built with the files in `sumo/ovm/` and `sumo/patches/register-ovm.patch` (see `sumo/version.txt`).

```bash
# Model validation
python sumo/check_nasch.py
python sumo/ovm/check_ovm.py
pytest

# City network
python scripts/city_sweep.py    --config configs/city/bugis_all_controller.toml
python scripts/city_measures.py --config configs/city/bugis_all_controller.toml

# Planning scenarios (after sweeping each bugis_all_<variant>_controller.toml)
python scripts/planning_figures.py \
    --extra base=bugis_all_base_controller_seeds4to10 \
    --extra newlink=bugis_all_newlink_controller_seeds4to10
```

The ring-road sweeps are on the branch `gw/self-experiment`, and the IDM stability and PeMS notebooks on `add-critical-density-analysis`. The report's appendix lists every command in full.

## Data sources

- Road network: © [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors, ODbL.
- Singapore speed bands: contains information from Traffic Speed Bands accessed from LTA DataMall, made available under the [Singapore Open Data Licence 1.0](https://data.gov.sg/open-data-licence).
- Freeway detector data: Caltrans Performance Measurement System (PeMS).
