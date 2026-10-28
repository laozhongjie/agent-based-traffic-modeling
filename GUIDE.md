# How we run experiments

[English](GUIDE.md) | [中文](GUIDE_zh.md)

This file is the Markdown version of the guide page [`docs/guide.html`](docs/guide.html), with the same content, for reading offline or giving to an AI as context. The Chinese version is [`GUIDE_zh.md`](GUIDE_zh.md). The three must stay in sync: when you change a convention, update the page and both Markdown files in the same PR.

This guide is the single reference for how every member sets up SUMO, where code and files go, how to build a new experiment, how runs are named and checked, and how code reaches the main branch. The ring-road example in the repository follows every rule here and serves as the template.

Project background: the project uses SUMO to study the transition from free flow to congestion as a nonequilibrium phase transition. It first compares the NaSch, OVM and IDM models on a single-lane ring road, then extends to a city road network and planning variants. Members are referred to by the letters A–E.

Items marked **(To decide)** still need group agreement. A maintains this guide; propose changes at the group meeting before relying on them.

## Contents

1. [Set up SUMO and Python](#1-set-up-sumo-and-python)
2. [Where code and files go](#2-where-code-and-files-go)
3. [Run the ring-road example](#3-run-the-ring-road-example)
4. [Build a new experiment](#4-build-a-new-experiment)
5. [Run IDs and run records](#5-run-ids-and-run-records)
6. [Result data format](#6-result-data-format)
7. [Checks every run must pass](#7-checks-every-run-must-pass)
8. [Units and measurements](#8-units-and-measurements)
9. [Still to decide](#9-still-to-decide)
10. [Working with Git](#10-working-with-git)

## 1. Set up SUMO and Python

Use the official SUMO release **1.28.0**. It includes IDM and NaSch. OVM is added by this project, so OVM runs and the formal runs use A's build: the same version with OVM compiled in. The release is enough for everything else: learning the workflow, developing scenarios, and running IDM and NaSch.

1. Install SUMO 1.28.0 from the [SUMO installation page](https://sumo.dlr.de/docs/Installing/index.html) for your system. If you installed 1.27.1 earlier, install 1.28.0 the same way and check it with step 3.
2. Set `SUMO_HOME` and add the SUMO `bin` folder to `PATH`:
   - **Windows:** the `.msi` installer sets both. Close and reopen the terminal afterwards.
   - **macOS:** the installer sets neither. Run these three lines in the terminal. They add both settings to the end of `~/.zshrc` and load them:

     ```bash
     echo 'export SUMO_HOME="/Library/Frameworks/EclipseSUMO.framework/Versions/Current/EclipseSUMO/share/sumo"' >> ~/.zshrc
     echo 'export PATH="/Library/Frameworks/EclipseSUMO.framework/Versions/Current/EclipseSUMO/bin:$PATH"' >> ~/.zshrc
     source ~/.zshrc
     ```

   - **Linux:** run these two lines in the terminal. `/usr/share/sumo` is the usual path after installing with apt on Ubuntu; apt already puts the programs on `PATH`.

     ```bash
     echo 'export SUMO_HOME="/usr/share/sumo"' >> ~/.bashrc
     source ~/.bashrc
     ```

3. Check the installation. The first line must read `Eclipse SUMO sumo 1.28.0`.

   ```bash
   sumo --version
   ```

4. **Optional:** `sumo-gui` shows a run in a window, so you can watch vehicles move and see where jams form. It helps when you check that a new scenario is built correctly. Experiments do not need it: every command in this guide except one optional step in section 3 runs without a window. On Windows `sumo-gui` works after installing SUMO. On macOS it needs XQuartz: install it (with Homebrew as below, or from [xquartz.org](https://www.xquartz.org/)), then log out and in again. Without XQuartz, `sumo-gui` stops with `unable to open display`. `Fontconfig warning` lines printed by `sumo-gui` are harmless.

   ```bash
   brew install --cask xquartz
   ```

5. Create the shared Python environment once, from the repository root. It installs fixed versions of Python and the packages, and installs the project code in `src/traffic_project` so that every script can import it.

   ```bash
   conda env create -f environment.yml
   ```

   If you created the environment before 9 Oct, when pandas, JupyterLab and pytest were added, update it instead:

   ```bash
   conda env update -f environment.yml --prune
   ```

6. Activate the environment in every new terminal before running project commands:

   ```bash
   conda activate traffic
   ```

## 2. Where code and files go

Code is organised by what it does, not by who wrote it. Each kind of code has one place and one owner.

| Location | What goes in it | Owner |
| --- | --- | --- |
| `scenarios/ring/` | Ring network files (`ring_<length>.net.xml` and its sources), `build_net.py` that generates them, and `build_run.py` that places the vehicles for one run | B |
| `scenarios/grid/` | Network files of the 4×4 test grid and the script that generates them; planning prototypes on the grid | D |
| `scenarios/city/` | City-district network converted from OSM data; its variants with a closed road or a new link | C; D |
| `configs/<scenario>/` | One TOML file per experiment with every parameter | Scenario owner |
| `scripts/` | Entry points, one per task: `<scenario>_sweep.py`, `plot_<scenario>.py` | Scenario owner |
| `src/traffic_project/` `config.py`, `io.py`, `runner.py` | Load configs, read SUMO outputs, run SUMO, write run records, common checks | A |
| `src/traffic_project/results.py` | Result data format (section 6): required columns, checks and writers | A |
| `src/traffic_project/export_web.py`, `scripts/export_web.py` | Export validated results to the website (section 3, step 6) | A |
| `src/traffic_project/nasch.py` | NaSch theory at $p = 0$ and a reference automaton | A |
| `src/traffic_project/ovm.py` | OVM theory: optimal speed, stability of uniform flow, reference integrator | A |
| `sumo/` | The SUMO build with OVM: version, OVM source, patch, and the checks `sumo/check_nasch.py` and `sumo/ovm/check_ovm.py` | A |
| `tests/` | Automated checks of the shared code, run with `pytest` | A |
| `src/traffic_project/measurements.py` | Measured quantities, one function per scenario | A; B ring; C network |
| `src/traffic_project/demand.py` | Constant-density TraCI controller for the city network (planned) | C |
| `src/traffic_project/analysis/` | Critical points, fluctuations, error bars (planned) | E |
| `results/<scenario>/` | Tables that collect many runs, and figures; keep files small | Scenario owner |
| `data/raw/`, `data/processed/` | External data: OSM, PeMS, highD, LTA | E |
| `runs/<run-id>/` | One folder per run, written by the scripts; never edited by hand | — |
| `sandbox/<your-name>/` | Your own experiments and notebooks | You |
| `notebooks/<your-name>/` | Read-only notebook copies for teammates, released by date (rule 6) | You |
| `docs/data/<scenario>/` | Results exported for the website; written by `scripts/export_web.py`, never edited by hand | — |
| `docs/` | The project website | A |

### Network files in `scenarios/`

A SUMO road network is a set of XML text files:

| File | Contents |
| --- | --- |
| `<name>.nod.xml` | Nodes (junctions): ID and x, y coordinates in m. Written by a script or by hand. |
| `<name>.edg.xml` | Edges (road segments): from which node to which node, number of lanes, speed limit (m/s), length (m) and shape. Written by a script or by hand. |
| `<name>.net.xml` | The complete network that SUMO reads: lanes, junctions, the connections between lanes, and traffic lights. Generated by `netconvert` or `netgenerate`; never edited by hand. |

For example, one node in `ring_1000.nod.xml` and one edge in `ring_1000.edg.xml`:

```xml
<node id="n0" x="159.155" y="0.000" type="priority"/>
<edge id="e0" from="n0" to="n1" numLanes="1" speed="30.0" length="250.000" shape="…"/>
```

Each scenario gets its network from a different source:

- **Ring:** `build_net.py` writes the `.nod.xml` and `.edg.xml` files, then calls `netconvert` to produce `ring_<length>.net.xml`.
- **4×4 grid** (planned): SUMO's `netgenerate --grid` can produce the `.net.xml` directly. D decides the details.
- **City district** (planned): the raw OpenStreetMap data (an `.osm` file) stays in `data/raw/`. `netconvert --osm-files` converts it into a `.net.xml` stored in `scenarios/city/`. Each planning variant from D, such as a closed road or a new link, is another `.net.xml` derived from it.

Vehicles and routes are not part of the network. They change with every run, so the scenario script writes them into `runs/<run-id>/vehicles.rou.xml`.

Git ignores `runs/`, `data/raw/`, `sandbox/` and every `*.fcd.xml`. Everything else in the table is committed.

### Rules

1. **Do not copy shared code.** To run SUMO, read outputs or write records, import `traffic_project`. If something is missing, ask A or open a pull request that adds it there.
2. **Keep parameters out of code.** Every model parameter, density, seed and duration lives in the experiment's TOML file in `configs/`.
3. **One experiment is one config file and one command.** Anyone can reproduce it from a clean commit.
4. **`sandbox/` never produces a reported result.** Move the code into the places above before its output goes into the report or onto the website.
5. **Start every script with a docstring** that says what it does and how to run it.
6. **Notebooks are for exploring and plotting, not for formal runs.** Keep them in `sandbox/<your-name>/`; that folder is not in git, so a notebook stays on your computer. Exception: executed, read-only copies of a notebook, written for teammates to read, may be committed under `notebooks/<your-name>/`, with the release date in the file name (for example `task1-district-import-2026-10-21.ipynb`); working notebooks never go there. Read results with `load_summary` and `load_timeseries` (section 6), and import `traffic_project` as a script would. Formal runs always use a config file and a script in `scripts/`, so that every result has a run record. When a notebook's analysis or figure is going into the report, move its code into `scripts/` or `src/traffic_project/analysis/` (rule 4).

## 3. Run the ring-road example

Run every command from the repository root, with the `traffic` environment active. The example runs IDM on a 1000 m single-lane ring; all its parameters are in `configs/ring/idm_sweep.toml`.

1. Build the ring network. This writes `scenarios/ring/ring_1000.net.xml`, which is already in git.

   ```bash
   python scenarios/ring/build_net.py --length 1000
   ```

2. Generate the inputs for one run with 30 vehicles and seed 1. This creates `runs/ring_idm_L1000_n30_s1/`.

   ```bash
   python scenarios/ring/build_run.py --config configs/ring/idm_sweep.toml --vehicles 30 --seed 1
   ```

3. Run SUMO. Choose one of the two commands:
   - Run without a window:

     ```bash
     sumo -c runs/ring_idm_L1000_n30_s1/run.sumocfg
     ```

   - Watch the run in `sumo-gui`. Keep `--delay 100`: without it the 1800 s run finishes in under a second and shows nothing.

     ```bash
     sumo-gui -c runs/ring_idm_L1000_n30_s1/run.sumocfg --delay 100 --start
     ```

4. Run the whole sweep in the config. For each run the script builds the inputs, runs SUMO, applies the checks in section 7 and writes the run record. It then writes `results/ring/idm_sweep.csv`.

   ```bash
   python scripts/ring_sweep.py --config configs/ring/idm_sweep.toml
   ```

5. Plot the fundamental diagram and the space–time diagrams into `results/ring/`.

   ```bash
   python scripts/plot_ring.py --config configs/ring/idm_sweep.toml
   ```

6. Export the valid runs to the website. This writes `docs/data/ring/idm_sweep.js` with each run's config hash, SUMO version and git commit. It stops when the runs came from uncommitted code or the config changed after the runs; `--allow-dirty` writes a draft for previewing. Run it on the computer that ran the sweep, because it reads the run records in `runs/`.

   ```bash
   python scripts/export_web.py --config configs/ring/idm_sweep.toml
   ```

**Expected result:** at 30 veh/km the mean speed is 16.6 m/s, the IDM equilibrium speed for that spacing. Flow peaks near 30 veh/km. Stop-and-go waves appear between about 40 and 80 veh/km; above 100 veh/km traffic is uniformly slow. If your numbers differ, check your SUMO version first.

## 4. Build a new experiment

Follow these steps for every experiment, including a variation of an existing one. Copy the matching ring-road file as a starting point.

1. **Create a branch** for the experiment (section 10).
2. **Write the config** `configs/<scenario>/<name>.toml`. Start from `configs/ring/idm_sweep.toml`. The top-level keys `name`, `scenario` and `model` are required; `name` also names the result files. Give every number a comment with its unit.
3. **Build the scenario inputs** with a script in `scenarios/<scenario>/`, like `scenarios/ring/build_run.py`. It reads the config, writes one folder `runs/<run-id>/` and prints the run ID. The `.sumocfg` it writes uses relative paths, sets `collision.action` to `warn`, and sets `time-to-teleport` to `-1` unless the scenario keeps SUMO's teleport (section 7).
4. **Add the measurements** as one function in `src/traffic_project/measurements.py`, like `ring_summary`. It reads one run's outputs and returns `(measurements, checks, timeseries)` in the format of section 6. This changes shared code, so A must approve the pull request.
5. **Write the entry script** `scripts/<scenario>_sweep.py`, like `scripts/ring_sweep.py`. It takes `--config`, loops over the sweep and uses the shared calls below. It writes the summary table and the time series with `results.write_summary` and `results.write_timeseries`.
6. **Run it and read the output.** Every run prints `ok` or `INVALID` with the failed checks. Fix the cause of every invalid run before using the results.
7. **Plot** with `scripts/plot_<scenario>.py --config …` into `results/<scenario>/`.
8. **Commit** the config, code and results together and open a pull request.

The shared calls every entry script uses, shown as an outline (not runnable as it is):

```python
from traffic_project import config, measurements, results, runner

cfg = config.load(args.config)
for each run in the sweep:
    run_id, run_dir = …                      # from scenarios/<scenario>/build_*.py
    runner.write_manifest(run_dir, run_id, cfg, parameters)
    _, checks = runner.run_sumo(run_dir)
    measured, more_checks, series = measurements.<scenario>_summary(…)
    results.write_timeseries(run_id, series, cfg)
    row = dict(measured, scenario=…, model=…, variant=…, seed=…)
    rows.append(runner.finish(run_dir, run_id, row, {**checks, **more_checks}))
results.write_summary(rows, cfg)
```

A scenario that changes the simulation while it runs, such as the constant-density controller on the city network, calls `runner.run_traci(run_dir, controller)` instead of `runner.run_sumo(run_dir)`. SUMO then advances one step at a time and calls `controller(conn, time_s)` after every step, where `conn` is the TraCI connection, for example `conn.vehicle.add` or `conn.vehicle.remove`. It writes the same `log.txt` and returns the same checks. The run's `.sumocfg` must set an end time.

## 5. Run IDs and run records

A run ID names the scenario, the model, the parameters that vary and the seed, joined by underscores, with no spaces. The ring example uses `ring_idm_L1000_n30_s1`: ring, IDM, length 1000 m, 30 vehicles, seed 1. Owners of other scenarios follow the same pattern and add their format here.

| File in `runs/<run-id>/` | Contents |
| --- | --- |
| `run.sumocfg` | SUMO configuration: network, routes, duration, step length, seed and outputs. Paths are relative, so the run works on any computer. |
| `vehicles.rou.xml` | Vehicle type with its model parameters, routes and start positions |
| `fcd.xml` | Position and speed of every vehicle at every step; large |
| `log.txt` | SUMO messages, used by the collision and teleport checks |
| `manifest.json` | Run ID, scenario, model, config file and its hash, all parameters, SUMO version, git commit and creation time |
| `summary.json` | Measurements and the result of every check, with `valid` = true or false |

Every number in the report or on the website keeps the run IDs it came from. The config hash shows whether the config file changed after the run. A git commit ending in `-dirty` means the code had uncommitted changes; formal results must come from a clean commit.

## 6. Result data format

E analyses every experiment with the same scripts, so B, C and D write their results in one format. `runs/` is not in git, so everything E needs must be in the two files below, in `results/<scenario>/`. Both are written by `traffic_project.results`, which stops with an error when a column is missing, a value is out of range, or an extra column lacks its prefix.

### Summary table: `results/<scenario>/<name>.csv`

One row per run. Every scenario has these columns, with these names and units:

| Column | Meaning | Unit |
| --- | --- | --- |
| `run_id` | Run ID | — |
| `scenario`, `model` | Scenario and model, as in the config | — |
| `variant` | Planning variant, such as baseline, closure or new link; empty when there is none | — |
| `seed` | Random seed | — |
| `density_veh_km` | Density $k$: number of vehicles ÷ total lane length | veh/km |
| `mean_speed_mps` | Space-mean speed $\bar v$, averaged over the measurement window | m/s |
| `flow_veh_h` | Flow $q = k\,\bar v$ | veh/h |
| `congested_fraction` | Congested fraction $\phi$, with the scenario's own criterion | — |
| `congested_fraction_var` | Variance of $\phi$ over time, the fluctuation $\chi$ | — |
| `valid` | `True` if the run passed every check in section 7 | — |

Scenario-specific columns come after these and start with the scenario name, for example `ring_vehicles` or `city_largest_cluster`.

### Time series: `results/<scenario>/<name>/<run_id>.csv`

One file per run, with one row of instantaneous values every 10 s over the whole run, warm-up included. The columns are `time_s`, `density_veh_km`, `mean_speed_mps`, `flow_veh_h` and `congested_fraction`. E uses it to check the warm-up length and to estimate fluctuations and error bars. One run of 1800 s is about 8 KB.

The definitions are the same on the ring and in the city network, so E can compare the highway and network critical densities directly.

### Reading the results in Python or a notebook

Both files read back as pandas tables, from any folder, with numbers as numbers and `valid` as `True`/`False`:

```python
from traffic_project.results import load_summary, load_timeseries

df = load_summary("ring", "idm_sweep")                               # one row per run
ts = load_timeseries("ring", "idm_sweep", "ring_idm_L1000_n50_s1")   # one run over time
df = df[df.valid]                                                     # keep runs that passed every check
```

## 7. Checks every run must pass

SUMO does not stop on several problems that silently change the experiment. Every run therefore records these checks in `summary.json`. The first three come from `runner.run_sumo` (or `runner.run_traci`), the others from the scenario's measurement function. Keep invalid runs for diagnosis, but leave them out of every table and figure.

| Check | What it catches |
| --- | --- |
| `sumo_exit_ok` | SUMO stopped with an error |
| `no_teleport` | By default SUMO removes a vehicle that waits more than 300 s and puts it back further on. Ring runs set `time-to-teleport` to `-1` to turn this off. City runs keep the 300 s teleport, because without it the city network drifts into gridlock (T3-D11, agreed by the group 2026-10-27), and grid runs keep it too, so that grid and city runs compare (member D agreed): their config sets `[run] allow_teleport = true`, which leaves this check out, and every city and grid run reports its teleports per car-hour instead. |
| `no_collision` | Vehicles overlapping. Every run sets `collision.action` to `warn` so collisions appear in the log. |
| `all_vehicles_present` | SUMO delays inserting a vehicle that would start too close to another, without an error. The vehicle count, and so the density, is then wrong. On the ring, `build_run.py` also refuses a vehicle count that cannot fit. On a network, the count comes from `summary.xml` (`running`), which still counts a vehicle in mid-teleport; the FCD output leaves that vehicle out. |
| `no_negative_speed` | Model errors, especially in the new OVM code |

Two more rules apply to the ring. Set each edge's `length` explicitly and build the network with `--no-internal-links`, so that density = vehicles ÷ ring length exactly. When a model has a known result, compare with it: the IDM equilibrium speed, the NaSch result at $p = 0$ and the OVM stability condition. NaSch reproduces the $p = 0$ result only on a lattice: the ring length is a whole number of 7.5 m cells, vehicles start at multiples of 7.5 m, `speedDev` is 0, and `maxSpeed` is a multiple of 7.5 m/s no higher than the edge's speed limit.

## 8. Units and measurements

| Quantity | Unit and rule |
| --- | --- |
| Time | s; step length 1 s in the current example **(To decide)** |
| Length, position | m |
| Speed | m/s in files; km/h only in text and labels |
| Density $k$ | veh/km |
| Flow $q$ | veh/h |
| Warm-up | The first 600 s are discarded; measurements use 600–1800 s **(To decide)** |

On the ring, the mean speed $\bar v$ is the average speed of all vehicles at each step, averaged over the measurement window. Because no vehicle enters or leaves, flow follows as $q = k\,\bar v$. The congested fraction $\phi$ is the share of vehicles slower than a threshold, and its variance over time is the fluctuation $\chi$. City-network measurements are defined by C in the same way.

## 9. Still to decide

- **IDM parameters** (B, with the group). The example uses placeholders: accel 1.0 m/s², decel 1.5 m/s², time headway 1.5 s, minimum gap 2 m, maximum speed 30 m/s, vehicle length 5 m.
- **Ring congestion criterion** (B). The placeholder, speed below 5 m/s, counts uniformly slow traffic above 100 veh/km as fully congested although it has no stop-and-go waves. The criterion must separate the two.
- **Network congestion criterion** (C).
- **Density grid and number of seeds per point** (B and C, with E), so that E can estimate error bars.
- **Step length and warm-up length** for the continuous models.
- **Which runs keep `fcd.xml`.** One run of 30 vehicles for 1800 s writes about 7 MB, so a full sweep should keep trajectories only for representative runs.
- **Time-series sample interval** (E). The example uses 10 s.

## 10. Working with Git

Nobody pushes to `main` directly. Every change reaches `main` through a pull request (PR). **Any other member can approve a PR. A PR that changes `src/traffic_project/` must be approved by A**; when A opens it, any other member approves.

1. Start from the latest `main`:

   ```bash
   git switch main
   git pull
   ```

2. Create a branch named `<your letter>/<topic>`, for example:

   ```bash
   git switch -c b/ring-bottleneck
   ```

3. Commit your changes with a message that says what changed.
4. Push the branch:

   ```bash
   git push -u origin b/ring-bottleneck
   ```

5. On GitHub, open a pull request into `main` and ask another member to review it. Merge only after the approval.

### Before opening a PR

1. Check that `git status` lists no files under `runs/`, `data/raw/` or `sandbox/`.
2. Commit the config, code and `results/` together, so a result always matches the code that produced it.
3. Rerun the result from a clean commit before it goes into the report or onto the website.
4. Run `pytest` from the repository root and check that every test passes; tests that need SUMO are skipped when it is not installed. When you change `src/traffic_project/`, add a test for the change in `tests/`.
5. If you changed a convention in this guide, update the page `docs/guide.html` (with `docs/assets/guide-i18n.js`), `GUIDE.md` and `GUIDE_zh.md` in the same PR.
