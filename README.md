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

The project hub (overview, timeline, progress) lives in [`docs/`](docs/). The [GitHub Pages workflow](.github/workflows/pages.yml) deploys `docs/` on each push to `main`, and can also be run manually from the repository's Actions tab. The interactive simulation environment will be added to the same site later.

The site has an English / Chinese toggle. To update the timeline or progress, edit [`docs/data/project.js`](docs/data/project.js): set each task's `status` to `todo`, `doing` or `done`, fill in workstream `owner`s, bump `updated`, then commit and push. Text fields there are `{ en, zh }`; fixed page text is translated in [`docs/assets/i18n.js`](docs/assets/i18n.js).

Experiment pages live in [`docs/lab/`](docs/lab/) (`ring.html`, `network.html`, `planning.html`). They are reserved layouts for now and will be filled with precomputed SUMO results.

Formulas are rendered with KaTeX: write `\( ... \)` for inline math and `\[ ... \]` for display math, in HTML, `i18n.js` or `project.js` (escape the backslash in JavaScript strings, e.g. `"\\(p = 0\\)"`). Shared language switching and math rendering live in [`docs/assets/common.js`](docs/assets/common.js).

To preview locally, run `python3 -m http.server 8000` inside `docs/` and open http://127.0.0.1:8000/.
