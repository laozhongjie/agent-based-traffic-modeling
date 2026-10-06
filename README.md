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

The ring-road, city-network and planning pages will display experimental results as they become available. The current illustrations explain model behavior and are not formal experiment results. The displayed workstreams are a draft; team assignments have not been decided.

## Repository layout

The tree below is the intended layout. The repository currently contains the overview documents and website; add the experiment directories and environment file as their implementation begins. Directory names describe responsibilities, not team assignments.

```text
.
├── README.md / README_zh.md
├── Project_Overview.md / Project_Overview_EN.md
├── environment.yml             # Reproducible Python environment
├── .github/workflows/          # Pages deployment and future checks
├── research/                   # Experiment protocol, validation, decisions
├── sumo/
│   ├── version.txt             # Pinned upstream SUMO commit
│   └── patches/                # OVM implementation and integration changes
├── scenarios/                  # SUMO road, route and signal inputs
│   ├── ring/                   # Ring road and bottleneck variants
│   ├── grid/                   # 4×4 network for pipeline validation
│   └── city/                   # Baseline, closure and new-link variants
├── configs/                    # Parameters, sweeps, seeds and durations
│   ├── validation/
│   ├── ring/
│   ├── network/
│   └── planning/
├── src/traffic_project/        # Shared simulation and analysis code
│   ├── runner.py               # SUMO/TraCI execution and run records
│   ├── demand.py               # Destinations, routing, vehicle-count control
│   ├── measurements.py         # Common measurement definitions
│   ├── analysis/               # Critical points, fluctuations, clusters
│   └── export_web.py           # Export compact website data
├── scripts/                    # Command-line entry points
├── tests/                      # Model, controller and measurement checks
├── data/                       # External data, separate from run outputs
│   ├── raw/                    # Original OSM, PeMS, highD or LTA data
│   └── processed/              # Cleaned external data
├── runs/                       # Per-run records, logs and SUMO outputs
├── results/                    # Aggregated statistics and generated figures
├── reports/                    # Report and presentation sources
└── docs/                       # Published website; retain existing structure
    ├── index.html
    ├── assets/                 # Shared styles, scripts and illustrations
    ├── models/                 # NaSch, OVM and IDM explanations
    ├── lab/                    # Ring, network and planning result views
    └── data/
        ├── project.js          # Website schedule and progress
        ├── ring/               # Exported Stage 1 results
        ├── network/            # Exported Stage 2 results
        └── planning/           # Exported Stage 3 comparisons
```

- `scenarios/` defines the simulated roads and traffic setup; `configs/` defines the experiment combinations. The three ring-road models share the same execution and analysis pipeline.
- `runs/<run-id>/` preserves the resolved configuration, random seed, project and SUMO versions, scenario identity, validation outcome, logs and outputs. `results/` aggregates these runs; every published point should retain its source run identifiers.
- `docs/data/` contains compact exports generated from validated results. GitHub Pages publishes all of `docs/`, so keep full trajectories, private data and experiment inputs outside it.
- Keep the upstream SUMO checkout and build outside this repository; record its version and preserve the OVM integration changes here. Large raw datasets and simulation outputs should use external storage with retrieval instructions. Configure `.gitignore` before generating them; the current ignore file does not yet exclude these planned data directories.

## Experiment workflow

1. Define the protocol and configuration: units, model parameters, density grid, seeds, initial conditions, warm-up and observation durations, and congestion criteria. Fix the SUMO build, including OVM.
2. Validate from the command line: NaSch against the deterministic reference, OVM against stability predictions, and the city controller on the 4×4 grid. Check vehicle counts, nonnegative speeds and vehicle overlap.
3. Run SUMO batches from the command line: ring-road comparisons first, city-network density sweeps next, then planning comparisons. Planning runs use the same density grid and seed set as the baseline, with lane length and vehicle count recorded for each scenario.
4. Save each run under its run identifier, check validity and retain failed-run diagnostics. Compute statistics after warm-up, aggregate repeated runs and refine the density grid near candidate critical regions.
5. Generate report figures and export the corresponding compact data to `docs/data/ring/`, `docs/data/network/` and `docs/data/planning/`.
6. Verify the website against the exported results, then commit and push. Result-page controls select available precomputed runs or replay times; new parameter combinations require another command-line run and export. Browser illustrations remain educational examples.

The experiment command-line tools are still to be implemented; this section defines their intended workflow rather than an existing command reference.
