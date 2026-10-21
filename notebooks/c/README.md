# C's notebooks for teammates

These are read-only copies of C's working notebooks for the city-network experiment (RQ 2.2), revised so that teammates can follow them without running anything. Task 1 imports the road network and task 2 matches LTA road stretches to it. Task 3's notebook (the congestion criterion) follows once its run setup is settled.

| Notebook | What it covers | Most relevant to |
|---|---|---|
| `task1-district-import-2026-10-21` | the Bugis–Rochor–Lavender road network: how it was imported, the checks it passes, what the cleaning removed, the signal plans | member D (network variants), member E |
| `task2-lta-lookup-2026-10-21` | real LTA road stretches matched to the network's roads, the speed data collected, and how to use the lookup | member E |

- **Reading them.** Open the `.ipynb` on GitHub for the text, tables and static figures. The interactive maps show only in the `.html`: download it and open it in a browser (map tiles load from the internet).
- **Status.** The outputs were computed on 2026-10-20 and the text was revised on 2026-10-21; the date in each file name is the date of the text revision. Each notebook opens with a status box that lists what has changed since its outputs were computed.
- **Read-only.** The notebooks import C's drawing helpers from the git-ignored `sandbox/c/notebooks/` and read git-ignored `runs/` and `data/raw/` files, so they do not re-run from a clone. Code behind any figure that goes into the report moves to `scripts/` or `src/traffic_project/analysis/` first (GUIDE rule 4).
- **Why this folder exists.** GUIDE rule 6 keeps notebooks in `sandbox/<your-name>/`, which is not in git, so teammates cannot see them there. This folder is an exception to that rule, pending member A's agreement. It holds only executed teammate copies released by date, never working notebooks. A new release replaces the previous one; git history keeps the old files.
- **Questions and objections:** to C in the group chat.
