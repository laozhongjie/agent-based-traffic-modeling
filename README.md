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

Enter the shared password `pc5253` or `PC5253` to open any page. Access is remembered for the current browser tab until it is closed. This is a browser-side gate for casual access: GitHub Pages still serves the files publicly, and the password and page content can be inspected or bypassed. Do not use it to protect confidential content.

The project hub (overview, timeline, progress) lives in [`docs/`](docs/). The [GitHub Pages workflow](.github/workflows/pages.yml) deploys `docs/` on each push to `main`, and can also be run manually from the repository's Actions tab. Formal experiments run through the command line; their exported results will be displayed on this site.

The site has an English / Chinese toggle. The displayed workstreams are a presentation draft; team assignments have not been decided. To update the timeline or progress, edit [`docs/data/project.js`](docs/data/project.js): set each task's `status` to `todo`, `doing` or `done`, fill in `owner`s once assignments are agreed, bump `updated`, then commit and push. Text fields there are `{ en, zh }`; fixed page text is translated in [`docs/assets/i18n.js`](docs/assets/i18n.js).

Experiment pages live in [`docs/lab/`](docs/lab/) (`ring.html`, `network.html`, `planning.html`). They are reserved layouts for now and will be filled with precomputed SUMO results.

Detailed bilingual introductions to [NaSch](docs/models/nasch.html), [OVM](docs/models/ovm.html) and [IDM](docs/models/idm.html) live in [`docs/models/`](docs/models/). Open them from the model names or equation cards on the homepage. Each page includes an interactive illustration, followed by consistently styled sections explaining equations, parameters, congestion mechanisms and limitations, with links to the original papers. The illustrations explain the rules and do not represent formal SUMO results.

Formulas are rendered with KaTeX: write `\( ... \)` for inline math and `\[ ... \]` for display math, in HTML, `i18n.js` or `project.js` (escape the backslash in JavaScript strings, e.g. `"\\(p = 0\\)"`). Shared language switching and math rendering live in [`docs/assets/common.js`](docs/assets/common.js).

To preview locally, run `python3 -m http.server 8000` inside `docs/` and open http://127.0.0.1:8000/.

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
