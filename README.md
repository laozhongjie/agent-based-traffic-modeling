# Agent-Based Modeling of Traffic Congestion on Road Networks

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

The project hub (overview, timeline, progress) lives in [`docs/`](docs/) and is served by GitHub Pages from the `main` branch, `/docs` folder. The interactive simulation environment will be added to the same site later.

The site has an English / Chinese toggle. To update the timeline or progress, edit [`docs/data/project.js`](docs/data/project.js): set each task's `status` to `todo`, `doing` or `done`, fill in workstream `owner`s, bump `updated`, then commit and push. Text fields there are `{ en, zh }`; fixed page text is translated in [`docs/assets/i18n.js`](docs/assets/i18n.js).

Experiment pages live in [`docs/lab/`](docs/lab/) (`ring.html`, `network.html`, `planning.html`). They are reserved layouts for now and will be filled with precomputed SUMO results.

Formulas are rendered with KaTeX: write `\( ... \)` for inline math and `\[ ... \]` for display math, in HTML, `i18n.js` or `project.js` (escape the backslash in JavaScript strings, e.g. `"\\(p = 0\\)"`). Shared language switching and math rendering live in [`docs/assets/common.js`](docs/assets/common.js).

To preview locally, run `python3 -m http.server 8000` inside `docs/` and open http://127.0.0.1:8000/.
