# Project Overview

## Agent-Based Modeling of Traffic Congestion on Road Networks

**Research areas:** complex systems, network science, nonequilibrium dynamics, agent-based modeling

---

## 1. Summary

Traffic congestion is a textbook example of a complex system. Each driver makes purely local decisions based on the gap to the car ahead, their own speed and the state of the traffic light. Yet when many vehicles interact, the system as a whole produces queues, slow-moving waves, spillback and a drop in overall capacity.

This project models traffic as a dynamical system of vehicle agents moving on a road network, and treats the transition from free flow to congestion as a nonequilibrium phase transition. The work covers two scales:

- **Highway (uninterrupted flow):** On a single-lane ring road with no traffic lights, we compare three agent-based microscopic models (NaSch, OVM and IDM), sweep the vehicle density, and estimate the critical density. Adding a single bottleneck to the ring lets us separate congestion that emerges spontaneously from density alone from congestion caused by a bottleneck.
- **City network (interrupted flow):** On a real urban road network imported from OpenStreetMap, complete with intersections, traffic lights and varying speed limits, we sweep the network density, estimate a network-wide critical density, and study how local jams grow into large congested regions.

The application focuses on urban planning: how do changes to the network, such as closing a road or adding a new link, shift the critical density? Real traffic data are used as a reference for the simulated fundamental diagrams and congestion locations. The final deliverables are a research report, reproducible simulation code, figures, and an interactive web-based simulation environment.

We make no prior assumption that any particular model or intervention will work. The core task is to build models that can be checked, define congestion criteria that can be reproduced, and use simulation data to state under what conditions each conclusion holds and where it breaks down.

---

## 2. Research Questions

### 2.1 Phase transition and critical density on a highway

On a road without traffic lights, can the transition from free flow to congestion be described as a phase transition? What is the critical density, and how does it depend on the vehicle model (NaSch, OVM, IDM), the level of randomness and the system size? Can jams form spontaneously without any bottleneck, and how do they differ, in shape and statistics, from jams caused by a bottleneck? Does the simulated critical density agree with real highway data?

### 2.2 Network-level critical point in a city

In an urban network with intersections, traffic lights and mixed speed limits, is there a network-wide critical density beyond which total throughput peaks and then falls? Above that density, do local jams merge into large congested regions? How does the network structure (bottleneck links, edge betweenness) determine the critical density and where congestion first appears? How does the network critical density compare with the highway one?

### 2.3 How urban planning shifts the critical point

Do changes such as road closures or new links raise or lower the network's critical density and maximum throughput? Does adding a road always help, or can it make things worse (Braess's paradox)?

All three questions revolve around the same theme: **where the critical point lies, what determines it, and how it can be moved.** Together they form a progression from **a single road**, to **a city network**, to **a planning application**.

---

## 3. Research Framework

```mermaid
flowchart LR
    A[Local driving rules<br/>NaSch / OVM / IDM] --> B[Highway ring road<br/>critical density & spontaneous jams]
    B --> C[City network<br/>network-level critical density]
    C --> D[Planning scenarios<br/>shift of the critical point]
    E[Real traffic data] -.reference.-> B
    E -.reference.-> C
```

The guiding principle is to introduce one new factor at each step, so that any change in the results can be attributed to that factor.

1. Define how vehicles move using microscopic rules.
2. Find the highway critical density on a ring road without traffic lights, and use a single bottleneck to distinguish spontaneous jams from bottleneck-induced ones.
3. Place vehicles on a city network with intersections, traffic lights and speed limits, and apply the same density-sweep approach to find the network-level critical density.
4. Modify the network according to planning scenarios, and measure each scenario's effect by how much it shifts the critical density.

---

## 4. Vehicle Models and Simulation Tools

### 4.1 Agent-based modeling

Each agent is a single vehicle. Its state includes at least its position, speed, length, gap to the vehicle ahead, current road, destination and departure time. Vehicles update their state using local information only, and the collective state of all vehicles determines the macroscopic behavior of the road or network.

This approach never prescribes that "a given density causes a jam". Instead, it lets us observe whether congestion emerges on its own from individual rules and boundary conditions.

### 4.2 Nagel–Schreckenberg model (NaSch)

NaSch divides the road into cells of equal length and updates vehicle speeds in discrete time steps. Each update consists of four rules: accelerate, slow down to avoid hitting the car ahead, randomly slow down, and move all vehicles simultaneously.

The rules are simple and fast to compute, which makes NaSch well suited to validating the implementation, sweeping many densities, and producing the fundamental diagram that shows the change from free flow to congested flow. Original paper: [Nagel & Schreckenberg, 1992](https://doi.org/10.1051/jp1:1992277).

### 4.3 Intelligent Driver Model (IDM)

IDM uses continuous positions and speeds. A vehicle's acceleration depends on its desired speed, its current speed, the net gap to the vehicle ahead, and the speed difference between the two. It captures smooth car-following, gradual acceleration and anticipatory braking.

The equations and an interactive demo are available in [Treiber's IDM page](https://traffic-simulation.de/info/info_IDM.html) and [Microsimulation of Traffic Flow](https://traffic-simulation.de/).

IDM is collision-free, its parameters have clear physical meaning, and it is one of the car-following models built into SUMO. This means the same driving rules can be used in both the ring-road and the city-network experiments.

### 4.4 Optimal Velocity Model (OVM)

OVM also uses continuous positions and speeds. Each vehicle computes an "optimal velocity" V(Δx) from its headway and relaxes towards it with sensitivity a: dv/dt = a[V(Δx) − v]. Original paper: [Bando et al., 1995](https://doi.org/10.1103/PhysRevE.51.1035).

What makes OVM useful here is that its linear stability can be analysed exactly. Uniform flow with headway h becomes unstable when V′(h) > a/2, at which point small perturbations grow into stop-and-go waves. This gives a theoretical density range for the transition that can be compared directly with the simulated threshold. For some parameter choices OVM allows vehicles to overlap, so this needs to be checked in the implementation.

### 4.5 Comparing the three models

All three are agent-based microscopic models, but they produce congestion through different mechanisms. The goal of the comparison is not to make them agree numerically, but to test how sensitive the transition, the jam waves and the capacity drop are to the modeling assumptions.

| Model | Space and time | Source of congestion | Role in the comparison |
|---|---|---|---|
| **NaSch** | Discrete cells, discrete time | Random slowdowns; with zero slowdown probability there are no spontaneous jams | Noise-driven congestion |
| **OVM** | Continuous | Deterministic instability: uniform flow is unstable when V′(h) > a/2 | Provides a theoretical critical condition to validate the simulated threshold |
| **IDM** | Continuous | Instability, while keeping safe gaps and avoiding collisions | Most realistic behavior; carries over to the SUMO network experiments |

To make results comparable, all models use the same physical units: NaSch uses a cell length of 7.5 m and a time step of 1 s; densities are reported in veh/km and flows in veh/h.

### 4.6 Models cover more than "how cars drive"

A traffic simulation is made up of several interacting model layers. NaSch, OVM and IDM only describe longitudinal vehicle motion; a complete experiment also needs to describe roads, signals, demand and routes:

| Layer | What it describes | How this project represents it |
|---|---|---|
| Vehicle behavior | Acceleration, braking, car-following, safe gaps, random fluctuations | Ring road: NaSch, OVM, IDM; city network: IDM |
| Road network | Link length, direction, number of lanes, speed limit, connectivity | Ring road: single-lane periodic road; city network: directed weighted graph imported from OpenStreetMap and run in SUMO |
| Intersections and signals | Conflicting movements, signal phases, green times, queue storage | SUMO junctions and traffic lights, with fixed-time plans generated by a common rule |
| Demand | Which vehicles are in the network and where they are going | A fixed number of vehicles set by the target network density; each vehicle gets a new random destination on arrival, so the vehicle count stays constant |
| Routing | Which roads a vehicle chooses or follows | Shortest path by free-flow travel time; same routing rule across all scenarios |
| Measurement | How vehicle states are turned into speed, flow, delay and congestion | A shared analysis script and a common set of congestion criteria |

In other words, the models are not just there to "put roads and cars into an animation". Together they determine how vehicles move, where they meet, how demand enters the system, and which macroscopic quantities can be measured.

### 4.7 Models for the literature review and optional extensions

The following models will be covered in the literature review. If time permits they can be implemented as extensions, but the main experiments do not depend on them:

| Model | Scale | Suggested use |
|---|---|---|
| **Cell Transmission Model (CTM) / LWR** | Describes traffic by the density and flow in each road cell, without tracking individual vehicles | Macroscopic cross-check: does the bottleneck capacity from the microscopic models agree with flow conservation? |
| **Biham–Middleton–Levine (BML)** | Two types of vehicles moving alternately on a 2D lattice | Illustrates self-organized jamming at the network level; not intended as a realistic city model |

CTM/LWR is not an agent-based model. Its role is to provide a cross-scale comparison, not to replace the vehicle agents.

### 4.8 Tools

| Layer | Tools | Purpose |
|---|---|---|
| Microscopic vehicle models | Python, NumPy | Our own implementations of NaSch, OVM and IDM on the ring road, for controlled experiments |
| Macroscopic benchmark (optional) | Python, NumPy | CTM/LWR density–flow conservation on a simple link or bottleneck |
| City network import | [OSMnx](https://osmnx.readthedocs.io/en/stable/getting-started.html), SUMO netconvert | Download an urban network from OpenStreetMap and convert it to a SUMO network |
| Network simulation | [SUMO](https://sumo.dlr.de/docs/), TraCI | Roads, intersections, traffic lights, routing and vehicle movement; TraCI keeps the vehicle count in the network constant |
| Network analysis | [NetworkX](https://networkx.org/documentation/stable/tutorial.html) | Paths, edge betweenness, connectivity and congested clusters |
| Data analysis | Python, Matplotlib, Pandas | Aggregate repeated runs, compute metrics, produce report figures |
| Interactive front end | JavaScript, Canvas, ECharts | Set up experiments, launch simulations, watch vehicles and view linked statistics |

The ring-road models we write ourselves are used to understand and validate the driving rules. SUMO handles intersections and signals in the city network, with vehicles following IDM. SUMO is a simulation platform, not a separate traffic model, so it is not compared side by side with NaSch, OVM and IDM.

---

## 5. Experimental Stages

### 5.0 Two kinds of flow, two congestion mechanisms

| | Stage 1: Highway | Stages 2 & 3: City network |
|---|---|---|
| Flow type | Uninterrupted flow | Interrupted flow |
| Setting | Single-lane ring road, an idealized stretch of highway without traffic lights | Urban network from OpenStreetMap with intersections, traffic lights and varying speed limits |
| Main cause of congestion | Spontaneous jams from vehicle interactions | Queues, spillback and gridlock caused by limited intersection capacity |
| Meaning of the critical point | Critical density of a single road | Critical density of the whole network |

Congestion has at least two distinct causes:

- **Spontaneous congestion:** There is no bottleneck on the road. Once the density exceeds a certain range, interactions between vehicles make uniform flow unstable and stop-and-go waves form.
- **Bottleneck-induced congestion:** An intersection, traffic light or reduced-speed section lowers the local capacity below the incoming flow, and vehicles queue upstream of it.

In a city network, links are short and intersections are dense, so congestion is dominated by intersection bottlenecks and purely spontaneous jams are hard to observe. Evidence for spontaneous congestion therefore comes from the bottleneck-free ring road in Stage 1. Stage 1 also adds a single bottleneck as a control, to confirm that the two mechanisms can be told apart in simulation. They have different observable signatures:

| Signature | Spontaneous congestion | Bottleneck-induced congestion |
|---|---|---|
| Where jams appear | Random; varies between random seeds | Always just upstream of the bottleneck |
| Space–time diagram | Jam bands drift backwards at roughly 15 km/h | Jam bands stay in place; behind a traffic light they grow and shrink with each signal cycle |
| Fundamental diagram | Maximum flow is set by the driving rules | Maximum flow is capped by the bottleneck capacity, and the critical density is lower |

For experimental evidence that jams can form without any bottleneck, see [Sugiyama et al., 2008, *Traffic jams without bottlenecks*](https://doi.org/10.1088/1367-2630/10/3/033001).

### Stage 1: Phase transition and critical density on a highway (Question 2.1)

| Item | Details |
|---|---|
| Goal | Find the critical density for the free-flow-to-jam transition on a road without traffic lights; test how it depends on the model, randomness and system size; distinguish spontaneous from bottleneck-induced congestion |
| Setting | Single-lane ring road; vehicles neither enter nor leave; no traffic lights |
| Models | NaSch, OVM, IDM |
| Control variables | ① **Vehicle density** (veh/km): swept from low to high, with finer steps near the transition<br>② **System size**: at least three ring lengths<br>③ **Randomness**: NaSch slowdown probability<br>④ **Bottleneck**: none / a reduced-speed section (representing a work zone, tunnel or similar capacity drop); a traffic light on the ring as an optional bridging case |
| Held fixed | Only one control variable changes per experiment set; all other parameters, simulation length, warm-up period and seed set stay the same |
| Measurements | Mean speed, flow at a fixed point, order parameter (fraction of jammed vehicles) and its fluctuations, jam locations, jam-wave speed |
| Outputs | ① Density–speed and density–flow diagrams (fundamental diagrams) for all three models<br>② Order parameter and its fluctuations versus density, compared across system sizes<br>③ OVM theoretical instability range versus the simulated critical density<br>④ Fundamental diagrams, space–time diagrams and jam-location distributions with and without the bottleneck<br>⑤ Simulated fundamental diagrams versus real highway detector data |
| Interpretation | If all three models show a flow peak, a rising order parameter and a peak in its fluctuations at some density, and the transition sharpens as the system grows, the transition has the hallmarks of a phase transition. If the bottleneck lowers the maximum flow, shifts the critical density down and pins jams just upstream of it, congestion under that condition is bottleneck-dominated |

### Stage 2: Network-level critical point in a city (Question 2.2)

| Item | Details |
|---|---|
| Goal | Find the network-level critical density of an urban network; study how local jams grow into large congested regions; test how network structure affects the critical point and where congestion starts |
| Setting | An urban district imported from OpenStreetMap (the code is first validated on a 4×4 grid). Intersections, lanes and speed limits come from the map data; traffic lights use fixed-time plans generated by a common rule and are not varied in this stage |
| Model | SUMO with IDM car-following |
| Control variable | **Network density** (vehicles in the network ÷ total lane length), swept from low to high. Each vehicle gets a new random destination on arrival, so the density stays constant within a run |
| Held fixed | Network, signal plans, destination rule, routing rule, seed set, simulation length |
| Measurements | Network-average flow and speed, fraction of stopped vehicles, speed and queue length on each link, number of spillback events, size of the largest congested cluster, occurrence of gridlock |
| Outputs | ① Network-level fundamental diagram (macroscopic fundamental diagram, MFD) and its peak, i.e. the network critical density<br>② Size of the largest congested cluster versus density<br>③ Link congestion heat maps at low, near-critical and high density<br>④ Scatter plot of edge betweenness against the time each link becomes congested<br>⑤ Network critical density compared with the Stage 1 highway critical density<br>⑥ Simulated congestion hotspots compared with real link-speed data |
| Interpretation | If network flow peaks and then falls at some density, while the largest congested cluster grows rapidly around the same density, there is a network-level transition. The correlation between betweenness and congestion onset tests whether a network measure can predict where bottlenecks will form |

Congestion in this stage is dominated by intersection bottlenecks, so the network critical density is generally lower than the highway one. That difference itself reflects the two different congestion mechanisms. For the concept of the MFD and empirical evidence, see [Geroliminis & Daganzo, 2008](https://doi.org/10.1016/j.trb.2008.02.002).

### Stage 3: How planning scenarios shift the critical point (Question 2.3)

| Item | Details |
|---|---|
| Goal | Test how changes to the network shift the network critical density, and evaluate each planning scenario at the system level |
| Setting | The Stage 2 urban network |
| Scenarios | **Baseline:** the original Stage 2 network<br>**Scenario 1, road closure:** close a high-betweenness link or reduce its lanes (representing roadworks or redesign)<br>**Scenario 2, new link:** add a connecting road and check for Braess's paradox<br>**Scenario 3 (optional), signal timing:** keep the cycle length fixed and redistribute green time at a bottleneck intersection according to directional flows |
| Control variables | Scenario × network density (same density values as Stage 2) |
| Held fixed | Everything except the modified link or intersection: the rest of the network, signals, routing rule, seed set and simulation length |
| Measurements | Same as Stage 2 |
| Outputs | ① MFDs of all scenarios overlaid<br>② Critical density and maximum network flow for each scenario, with error bars from repeated runs<br>③ Difference in congestion heat maps before and after each change |
| Interpretation | Scenarios are judged by the change in critical density and maximum network flow. A higher critical density means the network can hold more vehicles before tipping into congestion. If adding a road lowers the critical density or the maximum flow, Braess's paradox has occurred |

### How the stages answer the research questions

Each question needs its own controlled comparison; a single scenario is not enough:

| Research question | Minimum convincing experiment | Key evidence | Common pitfall |
|---|---|---|---|
| What is the highway critical density, and does it behave like a phase transition? | Same ring road, many densities, three models, several system sizes, multiple seeds; with and without a bottleneck | Fundamental diagrams, fluctuation peak of the order parameter, finite-size comparison, OVM theoretical threshold, comparison with real data | Showing only an animation; or seeing jams in a signalized network and calling them a density-driven phase transition |
| Does a city network have a network-level critical point, and what determines it? | Density sweep on a real urban network with multiple seeds | MFD peak, size of congested clusters, relationship between betweenness and congestion location | Sweeping inflow demand without controlling the number of vehicles in the network, so network density is undefined; using only a regular grid, which does not represent a city |
| How do planning changes shift the critical point? | Baseline and modified networks compared at the same density values and seeds | Change in critical density and maximum network flow, with error bars | Comparing at a single density, or reporting only the scenarios that improve things |

Stage 1 establishes the phase-transition behavior on a highway and separates the two causes of congestion. Stage 2 extends the same density-sweep approach to a city network. Stage 3 uses shifts in the critical point to evaluate planning scenarios.

---

## 6. Critical-Point Analysis

The critical density is the density at which the system switches from free flow to congestion as the density increases. We estimate it using standard tools from the statistical physics of phase transitions:

| Quantity | Definition | Behavior near the critical point |
|---|---|---|
| Order parameter | Fraction of jammed vehicles (vehicles slower than a threshold speed) | Close to 0 in free flow; rises sharply above the critical density |
| Fluctuations | Variance over time of the order parameter or the flow | Peaks near the critical point |
| Finite-size effects | Repeating the same sweep for different system sizes | The transition sharpens with system size and the peak position settles |
| Relaxation time (optional) | Time for the system to reach a steady state from its initial condition | Grows near the critical point (critical slowing down) |

Finite road length, finite observation time and random initial conditions all introduce uncertainty. The report will give the critical density as an estimate with error bars, discuss how sensitive it is to the congestion criterion and system size, and will not claim a rigorous phase-transition point in advance.

### 6.1 Highway criteria

- Does the mean speed drop noticeably?
- Does the flow reach a peak and then decline?
- Does the order parameter rise sharply, and do its fluctuations peak?
- Does the space–time diagram show persistent jammed regions or backward-moving waves?
- For OVM, does the simulated critical density fall within the instability range predicted by linear stability analysis?
- With a bottleneck on the ring, are jams pinned upstream of the bottleneck (bottleneck-induced) or drifting backwards elsewhere (spontaneous)?

### 6.2 City-network criteria

- Does the network-average flow peak and then decline (the MFD peak)?
- Does the fraction of stopped vehicles keep increasing?
- Do slow links form a connected region that grows rapidly?
- Does gridlock occur, with vehicles unable to move for long periods?

Candidate transition ranges are first located on a coarse density grid, then refined with extra points and more repeated runs nearby. The report gives means, the spread across repeated runs, the observation time, and the sensitivity of each criterion.

---

## 7. The Network Science Connection

The road network is not just a backdrop for the animation. The project asks how network structure shapes traffic dynamics.

### 7.1 Representing the road network

- Intersections are nodes.
- One-way road segments are directed edges.
- Length, speed limit and number of lanes are edge attributes.
- Free-flow travel time is the edge weight used for routing.

### 7.2 Route load and bottlenecks

We count how many vehicle routes use each link in the simulation and compare this with the weighted edge betweenness computed in NetworkX. High betweenness means many paths pass through a link, but it does not automatically make that link the most congested. Signals, capacity and downstream spillback also affect where queues actually form.

### 7.3 Connectivity of congestion

Links that stay slow are marked as congested, and adjacent congested links are grouped using the network's connectivity. We track the share of road length in the largest congested cluster and check whether it jumps sharply near the network critical density. This quantity describes the spatial spread of slow traffic over time; it is not the same as a percolation cluster in the sense of randomly removing nodes.

Concepts from the course, such as graph representation, centrality, connected components and percolation, provide the theoretical language for this analysis. Traffic congestion, however, is directional, capacity-constrained and correlated, so percolation thresholds for independent random removal cannot be applied directly.

For a research example linking traffic networks and critical phenomena, see [Percolation transition in dynamical traffic network with evolving critical bottlenecks](https://doi.org/10.1073/pnas.1419185112). It is useful background for the direction of the project; we do not need to reproduce it.

---

## 8. Data and Limits of Realism

| Data | Use | Stage | What it cannot show |
|---|---|---|---|
| [OpenStreetMap / OSMnx](https://osmnx.readthedocs.io/en/stable/getting-started.html) | Topology, directions, lanes and speed limits of the urban network | Stages 2 & 3 | Real traffic flows |
| [PeMS](https://pems.dot.ca.gov/) | Flow, occupancy and speed from highway detectors; used to plot real fundamental diagrams and estimate a real critical density | Stage 1 | Data come from California highways and do not represent a city network |
| [highD Dataset](https://levelxdata.com/highd-dataset/) | Vehicle trajectories and following gaps on highways; used to check that car-following parameters are in a plausible range | Stage 1 | Recorded road sections are short and do not represent a city network |
| [LTA DataMall](https://datamall.lta.gov.sg/content/datamall/en/dynamic-data.html) | Link speeds in Singapore; compared with simulated congestion hotspots (applicable if the district is in Singapore) | Stage 2 | Cannot calibrate all vehicle behavior on its own |

The city network uses real topology, but the number of vehicles and their destinations are synthetic. The report should therefore describe these as "synthetic-demand experiments on a real network topology". Real traffic data serve as a reference for the shape of the fundamental diagram, the order of magnitude of the critical density, and the locations of congestion; they are not used for vehicle-by-vehicle calibration. Both PeMS and highD require registration or an access request, so how to obtain the data needs to be confirmed early.

---

## 9. Interactive Simulation Environment

The web page is the project's **experiment console and visualization interface**. Ring-road experiments are computed live in the browser. City-network results come from SUMO: the formal runs are computed in advance and published with the site, and the page is used to pick parameters, replay runs and compare results.

```mermaid
flowchart LR
    A[Web console<br/>choose model and parameters] --> B{Experiment type}
    B --> C[Live in the browser<br/>ring road NaSch / OVM / IDM]
    B --> D[Precomputed SUMO results<br/>city network]
    B -. when a local backend is running .-> G[Python backend<br/>live SUMO runs]
    C --> E[Vehicle trajectories and statistics]
    D --> E
    G --> E
    E --> F[Animation, charts and run records on the page]
```

### 9.1 Ring-road experiments in the browser

The ring-road versions of NaSch, OVM and IDM are small enough to run in JavaScript directly in the browser. The page provides controls for the model, number of vehicles, road length, model parameters, perturbations, a bottleneck toggle and simulation length. When the user clicks "Run", the browser computes each time step and draws the animation and charts.

This mode is for live exploration: change one parameter and immediately see traffic go from smooth to jammed. It is also a good way to show how simple individual rules produce collective behavior.

The ring-road results in the report are computed in batch with the Python version. The browser and Python versions share the same rules and parameters, and a common set of tests checks that they agree.

### 9.2 City-network experiments: SUMO is the reference

City networks involve intersections, traffic lights, lane changes and routing. All of this is computed by SUMO, so the results are reliable and close to real traffic.

The site is hosted on GitHub Pages, which serves static files only and cannot run Python or SUMO. City-network experiments therefore run in two ways:

| Mode | How it works | Purpose |
|---|---|---|
| **Precomputed (main)** | Run every experiment combination locally with SUMO (network density × network scenario × random seed), export the results as data files, and publish them with the site | Formal results for the report; anyone opening the site can switch parameters, replay runs and compare scenarios |
| **Live local runs (supplementary)** | Start the Python backend locally; the page sends a configuration to it, and it runs SUMO and returns the results | Trying parameters outside the precomputed grid during group discussions or a live demo |

The data published with the site are mostly aggregated: speed and flow on each link per time interval, network-level density–flow points, and short vehicle-trajectory clips from a few representative runs for the replay animation. Full raw outputs are stored separately and not published with the site.

### 9.3 Exploration versus formal results

| Use | Ring road | City network |
|---|---|---|
| Exploration | Change any parameter in the browser and run it live | Switch between precomputed parameter combinations; use the local backend for new ones |
| Formal results | Batch runs of the Python version over many random seeds | Batch SUMO runs over many random seeds, published with the site |

Every formal result must save its configuration, random seeds, code version and output data, so that the page, the report figures and anyone reproducing the work all rely on the same records.

Suggested views:

1. **Ring road:** set the model, vehicle density and bottleneck on/off; watch the animation along with mean speed, flow and the space–time diagram.
2. **City network:** choose a network density; replay how link speeds evolve in the SUMO results, and view congested regions and the MFD.
3. **Planning comparison:** pick a network modification and compare its SUMO-derived MFD and critical density side by side with the baseline.

A top-down 2D view is sufficient; photorealistic 3D buildings are not a goal. Vehicles are drawn as simple shapes colored by speed, and every data point on a chart links to a viewable run record.

For reference, see the traffic playback on [Traffic Simulation](https://traffic-simulation.de/) and the interactive charts in [ECharts Examples](https://echarts.apache.org/examples/en/index.html). All values, units, parameters and run IDs shown on the page must match the formal experiment records.

---

## 10. Deliverables

| Deliverable | Contents |
|---|---|
| Research report | Model review, network representation, experimental design, critical-point analysis for highway and city network, planning application, discussion and limitations |
| Simulation code | NaSch, OVM and IDM ring-road models, SUMO network scenarios, batch-run and analysis scripts |
| Experimental data | Configurations, random seeds, summary statistics and representative vehicle trajectories |
| Key figures | Fundamental diagrams for the three models, order parameter and fluctuation plots, with/without-bottleneck comparisons, space–time diagrams, MFDs, network heat maps, planning-scenario comparisons |
| Interactive web page | Parameter setup, simulation runs, vehicle visualization, metric charts, model/scenario switching and explanations of results |
| Presentation slides | About 15 minutes covering the research questions, methods, evidence and conclusions |

A sound conclusion should state the observed phenomenon, the experimental conditions it depends on, the statistical uncertainty, and the gap between the model and reality.

---

## 11. In One Sentence

Following the chain **local driving rules → highway critical density → city-network critical density → how planning changes shift the critical point**, this project studies how traffic congestion emerges from individual interactions as a nonequilibrium phase transition, distinguishes density-driven spontaneous jams from bottleneck-induced ones, and uses the graph structure and dynamic connectivity of network science to explain how congestion spreads through a city.
