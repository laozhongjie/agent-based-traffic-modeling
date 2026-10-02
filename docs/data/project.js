// Project data for the hub page.
// To update progress: change a task's status to "todo", "doing" or "done",
// fill in owners, bump `updated`, then commit and push.

window.PROJECT = {
  updated: "2026-10-02",
  repo: "https://github.com/laozhongjie/abm-traffic-modeling",

  // All times are Singapore time (UTC+8).
  deadlines: [
    { date: "2026-11-05T18:00:00+08:00", label: "Presentation slides", detail: "Submit to the group in Canvas › People › Groups" },
    { date: "2026-11-15T23:59:00+08:00", label: "Peer grading", detail: "Canvas Quiz: Final project peer grading" },
    { date: "2026-11-22T23:59:00+08:00", label: "Group report, data & code; individual report", detail: "Group files in Canvas › People › Groups; individual report in Canvas › Quizzes" }
  ],

  // Markers shown on the timeline bar.
  events: [
    { date: "2026-10-24", label: "Course test", kind: "test" },
    { date: "2026-11-01", label: "Experiments done", kind: "target" },
    { date: "2026-11-05", label: "Slides due", kind: "deadline" },
    { date: "2026-11-15", label: "Peer grading", kind: "deadline" },
    { date: "2026-11-22", label: "Report due", kind: "deadline" }
  ],

  timelineStatus: "Draft schedule, to be confirmed at kick-off.",
  timeline: [
    {
      start: "2026-10-01", end: "2026-10-07", title: "Kick-off & literature survey",
      items: [
        "Read the project overview",
        "Survey traffic models, their variations and applications",
        "Set up Python, SUMO and the repository locally",
        "Choose workstreams"
      ]
    },
    {
      start: "2026-10-08", end: "2026-10-14", title: "Build & validate",
      items: [
        "NaSch, OVM and IDM on the ring road, with validation checks",
        "Import an OSM district into SUMO; validate on a 4×4 grid",
        "Shared analysis script and congestion criteria",
        "Request PeMS / highD data access"
      ]
    },
    {
      start: "2026-10-15", end: "2026-10-21", title: "Stage 1 & 2 experiments",
      items: [
        "Ring-road sweeps: density, system size, randomness, bottleneck",
        "Critical-point analysis for the highway",
        "Network density sweeps and MFD",
        "In-browser ring-road simulation on this site"
      ]
    },
    {
      start: "2026-10-22", end: "2026-10-28", title: "Stage 3 & figures",
      note: "Lighter week: course test on 24 Oct",
      items: [
        "Planning scenarios: road closure, new link",
        "Comparison with real traffic data",
        "Final figures for all stages"
      ]
    },
    {
      start: "2026-10-29", end: "2026-11-01", title: "Integrate results",
      items: [
        "Freeze conclusions",
        "Slide outline and first draft"
      ]
    },
    {
      start: "2026-11-02", end: "2026-11-05", title: "Presentation",
      items: [
        "Finish and rehearse slides (15 min + 3 min Q&A)",
        "Submit slides by 5 Nov, 6:00 pm"
      ]
    },
    {
      start: "2026-11-06", end: "2026-11-15", title: "Report drafting & peer grading",
      items: [
        "Write the group report (at least 10 pages)",
        "Complete peer grading by 15 Nov"
      ]
    },
    {
      start: "2026-11-16", end: "2026-11-22", title: "Final submission",
      items: [
        "Finalize report, data and code",
        "Write individual reports",
        "Submit by 22 Nov, 11:59 pm"
      ]
    }
  ],

  // status: "todo" | "doing" | "done"; owner: null means not yet claimed.
  workstreams: [
    {
      name: "Highway models",
      stage: "Stage 1",
      owner: null,
      summary: "Ring-road implementations of NaSch, OVM and IDM, and the Stage 1 experiments.",
      tasks: [
        { text: "Implement NaSch on a ring road", status: "todo" },
        { text: "Implement OVM and IDM on a ring road", status: "todo" },
        { text: "Validation checks: no overlaps, vehicle conservation, units", status: "todo" },
        { text: "Sweeps: density, system size, randomness", status: "todo" },
        { text: "Bottleneck runs: reduced-speed section, optional traffic light", status: "todo" }
      ]
    },
    {
      name: "City network",
      stage: "Stages 2 & 3",
      owner: null,
      summary: "SUMO network from OpenStreetMap, constant-density runs and planning scenarios.",
      tasks: [
        { text: "Choose a district and import it from OSM into SUMO", status: "todo" },
        { text: "Validate the pipeline on a 4×4 grid", status: "todo" },
        { text: "TraCI controller that keeps network density constant", status: "todo" },
        { text: "Network density sweeps", status: "todo" },
        { text: "Planning scenarios: road closure, new link", status: "todo" }
      ]
    },
    {
      name: "Critical-point analysis & data",
      stage: "All stages",
      owner: null,
      summary: "Congestion criteria, phase-transition analysis and comparison with real data.",
      tasks: [
        { text: "Define order parameter and congestion criteria", status: "todo" },
        { text: "Fundamental diagrams, fluctuations, finite-size analysis", status: "todo" },
        { text: "MFD and congested-cluster analysis with NetworkX", status: "todo" },
        { text: "Obtain PeMS / highD / LTA data", status: "todo" },
        { text: "Compare simulated and real results", status: "todo" }
      ]
    },
    {
      name: "Web & visualization",
      stage: "Site",
      owner: null,
      summary: "This project site, then the interactive simulation environment.",
      tasks: [
        { text: "Project hub page (this site)", status: "doing" },
        { text: "In-browser ring-road simulation (NaSch / OVM / IDM)", status: "todo" },
        { text: "Linked charts: fundamental diagram, space–time diagram", status: "todo" },
        { text: "City-network view with link speeds and MFD", status: "todo" },
        { text: "Connect the page to SUMO runs on the backend", status: "todo" }
      ]
    },
    {
      name: "Integration, report & slides",
      stage: "Deliverables",
      owner: null,
      summary: "Literature survey, reproducibility, report and presentation.",
      tasks: [
        { text: "Project overview (EN / ZH) and repository", status: "done" },
        { text: "Literature survey: models, variations, applications", status: "todo" },
        { text: "Experiment registry: configs, seeds, outputs", status: "todo" },
        { text: "Slides and rehearsal", status: "todo" },
        { text: "Group report and AI prompt appendix", status: "todo" }
      ]
    }
  ],

  resources: [
    {
      group: "Project documents",
      links: [
        { label: "Project overview (English)", url: "https://github.com/laozhongjie/abm-traffic-modeling/blob/main/Project_Overview_EN.md", note: "Full description of questions, stages and methods" },
        { label: "Project overview (中文)", url: "https://github.com/laozhongjie/abm-traffic-modeling/blob/main/Project_Overview.md", note: "Chinese version" },
        { label: "GitHub repository", url: "https://github.com/laozhongjie/abm-traffic-modeling", note: "Code, data and documents (private)" }
      ]
    },
    {
      group: "Key papers",
      links: [
        { label: "Nagel & Schreckenberg, 1992", url: "https://doi.org/10.1051/jp1:1992277", note: "Cellular automaton model for highway traffic" },
        { label: "Bando et al., 1995", url: "https://doi.org/10.1103/PhysRevE.51.1035", note: "Optimal Velocity Model" },
        { label: "Sugiyama et al., 2008", url: "https://doi.org/10.1088/1367-2630/10/3/033001", note: "Traffic jams without bottlenecks" },
        { label: "Geroliminis & Daganzo, 2008", url: "https://doi.org/10.1016/j.trb.2008.02.002", note: "Macroscopic fundamental diagram" },
        { label: "Li et al., 2015 (PNAS)", url: "https://doi.org/10.1073/pnas.1419185112", note: "Percolation transition in traffic networks" }
      ]
    },
    {
      group: "Tools",
      links: [
        { label: "Traffic Simulation", url: "https://traffic-simulation.de/", note: "Interactive IDM demos" },
        { label: "IDM description", url: "https://traffic-simulation.de/info/info_IDM.html", note: "Equations and parameters" },
        { label: "SUMO documentation", url: "https://sumo.dlr.de/docs/", note: "Network simulation" },
        { label: "OSMnx", url: "https://osmnx.readthedocs.io/en/stable/getting-started.html", note: "Download OpenStreetMap networks" },
        { label: "NetworkX", url: "https://networkx.org/documentation/stable/tutorial.html", note: "Network analysis" },
        { label: "ECharts examples", url: "https://echarts.apache.org/examples/en/index.html", note: "Interactive charts" }
      ]
    },
    {
      group: "Data",
      links: [
        { label: "PeMS", url: "https://pems.dot.ca.gov/", note: "Highway detector data (registration required)" },
        { label: "highD dataset", url: "https://levelxdata.com/highd-dataset/", note: "Highway vehicle trajectories (request access)" },
        { label: "LTA DataMall", url: "https://datamall.lta.gov.sg/content/datamall/en/dynamic-data.html", note: "Singapore traffic speed bands" }
      ]
    }
  ]
};
