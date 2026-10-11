# Agent-Based Modeling of Traffic Congestion on Road Networks

[English](README.md) | [中文](README_zh.md)

This project studies the transition from free flow to congestion as a nonequilibrium phase transition, first on a highway ring road and then on a city road network.

## Project overview

- [English](Project_Overview_EN.md)
- [中文](Project_Overview.md)

## Key dates

| Date | Deliverable |
|---|---|
| 5 Nov, 6:00 pm | Presentation slides (Canvas › People › Groups) |
| 15 Nov, 11:59 pm | Peer grading (Canvas Quiz) |
| 22 Nov, 11:59 pm | Group report, data and code; individual report |

## Project site

[Open the project website](https://laozhongjie.github.io/agent-based-traffic-modeling/)

Shared password: `pc5253` or `PC5253`.

The site supports English and Chinese and presents the project overview, schedule, progress and learning materials. Click a model name or equation card on the homepage to explore NaSch, OVM or IDM, including interactive illustrations and references.

The ring-road, city-network and planning pages will display experimental results as they become available. The current illustrations explain model behavior and are not formal experiment results. The homepage now shows the provisional A–E primary owners, shared interfaces and cross-review plan.

## Repository layout

The tree below is the intended layout. The repository currently contains the overview documents, the website and a first ring-road scenario; add the other directories as their implementation begins. Directory names describe responsibilities, not team assignments.

```text
.
├── README.md / README_zh.md
├── GUIDE.md / GUIDE_zh.md      # Guide as Markdown, same content as docs/guide.html
├── Project_Overview.md / Project_Overview_EN.md
├── environment.yml             # Reproducible Python environment
├── pyproject.toml              # Makes src/traffic_project importable (pip install -e .)
├── .github/workflows/          # Pages deployment and future checks
├── research/                   # Decision log and validation notes
├── sumo/
│   ├── version.txt             # Pinned upstream SUMO commit
│   ├── check_nasch.py          # Checks SUMO's NaSch against the exact p = 0 result
│   ├── ovm/                    # MSCFModel_OVM.h/.cpp, kept as complete files, and check_ovm.py
│   └── patches/                # Small edits that register OVM in SUMO
├── scenarios/                  # Fixed SUMO inputs and their generators
│   ├── ring/                   # Ring road and bottleneck variants
│   ├── grid/                   # 4×4 network for pipeline validation
│   └── city/                   # Baseline, closure and new-link variants
├── configs/                    # Parameters, sweeps, seeds and durations
│   ├── validation/
│   ├── ring/
│   ├── network/
│   └── planning/
├── src/traffic_project/        # Shared simulation and analysis code
│   ├── config.py               # Load experiment configs (TOML)
│   ├── io.py                   # Read SUMO outputs, write result tables
│   ├── runner.py               # SUMO/TraCI execution and run records
│   ├── demand.py               # Destinations, routing, vehicle-count control
│   ├── measurements.py         # Common measurement definitions
│   ├── results.py              # Result data format shared with the analysis
│   ├── nasch.py                # NaSch theory at p = 0 and reference automaton
│   ├── ovm.py                  # OVM theory and reference integrator
│   ├── analysis/               # Critical points, fluctuations, clusters
│   └── export_web.py           # Export compact website data
├── scripts/                    # Command-line entry points
├── tests/                      # Model, controller and measurement checks
├── data/                       # External data, separate from run outputs
│   ├── raw/                    # Original OSM, PeMS, highD or LTA data (not in git)
│   └── processed/              # Cleaned external data
├── runs/                       # One folder per run: inputs, record, log, outputs (not in git)
├── sandbox/                    # Personal experiments (not in git)
├── results/                    # Aggregated statistics and figures (in git, keep small)
├── reports/                    # Report and presentation sources
└── docs/                       # Published website; retain existing structure
    ├── index.html
    ├── guide.html              # Shared conventions for all members
    ├── assets/                 # Shared styles, scripts and illustrations
    ├── models/                 # NaSch, OVM and IDM explanations
    ├── lab/                    # Ring, network and planning result views
    └── data/
        ├── project.js          # Website schedule and progress
        ├── ring/               # Exported ring-road results
        ├── network/            # Exported city-network results
        └── planning/           # Exported planning comparisons
```

- `scenarios/` holds only inputs that stay fixed across runs (networks, signal plans) and the scripts that generate them. Anything generated for a single run (vehicle placement, `.sumocfg`, outputs) goes into `runs/<run-id>/`. `configs/` defines the experiment combinations. The three ring-road models share the same execution and analysis pipeline.
- `runs/<run-id>/` preserves the resolved configuration, random seed, project and SUMO versions, scenario identity, validation outcome, logs and outputs. `results/` aggregates these runs; every published point should retain its source run identifiers.
- Git tracks code, scenarios, configs, `results/` and `docs/`. It ignores `runs/` and `data/raw/` (see `.gitignore`); share large files through external storage and record how to retrieve them.
- `docs/data/` contains compact exports generated from validated results. GitHub Pages publishes all of `docs/`, so keep full trajectories, private data and experiment inputs outside it.
- `docs/guide.html` is the single reference for the shared conventions (units, run IDs, directories, checks); `GUIDE.md` and `GUIDE_zh.md` have the same content as Markdown. `research/` records how those decisions were reached and the validation results.
- Keep the upstream SUMO checkout and build outside this repository; record its version in `sumo/version.txt`, the new OVM files in `sumo/ovm/` and the edits to existing SUMO files in `sumo/patches/`.

## Experiment workflow

1. Define the protocol and configuration: units, model parameters, density grid, seeds, initial conditions, warm-up and observation durations, and congestion criteria. Fix the SUMO build, including OVM.
2. Validate from the command line: NaSch against the deterministic reference, OVM against stability predictions, and the city controller on the 4×4 grid. Check vehicle counts, nonnegative speeds and vehicle overlap.
3. Run SUMO batches from the command line: ring-road comparisons first, city-network density sweeps next, then planning comparisons. Planning runs use the same density grid and seed set as the baseline, with lane length and vehicle count recorded for each scenario.
4. Save each run under its run identifier, check validity and retain failed-run diagnostics. Compute statistics after warm-up, aggregate repeated runs and refine the density grid near candidate critical regions.
5. Generate report figures and export the corresponding compact data to `docs/data/ring/`, `docs/data/network/` and `docs/data/planning/`.
6. Verify the website against the exported results, then commit and push. Result-page controls select available precomputed runs or replay times; new parameter combinations require another command-line run and export. Browser illustrations remain educational examples.

The ring-road tools follow this workflow; see `docs/guide.html` for the commands and for how to add a new experiment. Tools for the other scenarios are still to be implemented.
