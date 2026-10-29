// Project data for the hub page.
// Text fields are { en, zh }. A plain string is shown in both languages.
// Task progress is updated by clicking tasks on member.html (stored in Firebase);
// edit this file to change tasks, owners or the timeline, bump `updated`, then commit and push.

window.PROJECT = {
  updated: "2026-10-08",
  repo: "https://github.com/laozhongjie/agent-based-traffic-modeling",

  // All times are Singapore time (UTC+8).
  deadlines: [
    {
      date: "2026-11-05T18:00:00+08:00",
      label: { en: "Presentation slides", zh: "提交展示幻灯片" },
      detail: { en: "Submit to the group in Canvas › People › Groups", zh: "在 Canvas › People › Groups 中提交给小组" }
    },
    {
      date: "2026-11-15T23:59:00+08:00",
      label: { en: "Peer grading", zh: "完成互评" },
      detail: { en: "Canvas Quiz: Final project peer grading", zh: "Canvas Quiz：Final project peer grading" }
    },
    {
      date: "2026-11-22T23:59:00+08:00",
      label: { en: "Group report, data & code; individual report", zh: "提交小组报告、数据与代码及个人报告" },
      detail: {
        en: "Group files in Canvas › People › Groups; individual report in Canvas › Quizzes",
        zh: "小组文件提交到 Canvas › People › Groups；个人报告提交到 Canvas › Quizzes"
      }
    }
  ],

  // Markers shown on the timeline bar.
  events: [
    { date: "2026-10-24", label: { en: "Course test", zh: "课程测验" }, kind: "test" },
    { date: "2026-11-01", label: { en: "Experiments done", zh: "实验完成" }, kind: "target" },
    { date: "2026-11-05", label: { en: "Slides due", zh: "幻灯片截止" }, kind: "deadline" },
    { date: "2026-11-15", label: { en: "Peer grading", zh: "互评截止" }, kind: "deadline" },
    { date: "2026-11-22", label: { en: "Report due", zh: "报告截止" }, kind: "deadline" }
  ],

  timelineStatus: { en: "Five primary owners are assigned. Workstreams run in parallel through shared interfaces and cross-review.", zh: "五个主责方向已经分配。各方向通过共享接口和交叉复核并行推进。" },
  // `who` is a member letter, a list of letters, or "all" for the whole group.
  timeline: [
    {
      start: "2026-10-01", end: "2026-10-07",
      title: { en: "Kick-off & literature survey", zh: "启动与文献调研" },
      items: [
        { who: "all", en: "Read the project overview and survey traffic models", zh: "阅读项目概览，调研交通模型及其变体和应用" },
        { who: "all", en: "Set up Python, SUMO and the repository locally", zh: "在本地配置 Python、SUMO 和仓库" },
        { who: "A", en: "Confirm primary owners, cross-review and shared interfaces", zh: "确认主责方向、交叉复核和共享接口" }
      ]
    },
    {
      start: "2026-10-08", end: "2026-10-14",
      title: { en: "Build & validate", zh: "搭建与验证" },
      items: [
        { who: "A", en: "Build SUMO from source at a pinned commit; publish a runnable ring example and the run rules", zh: "从源码编译 SUMO 并固定 commit；发布可运行的环路示例和运行规则" },
        { who: "A", en: "Start the OVM implementation in C++", zh: "开始用 C++ 实现 OVM" },
        { who: "B", en: "Build the ring road with IDM on release SUMO; trial density sweep; define the ring congestion criterion", zh: "用正式版 SUMO 和 IDM 搭建环路，试跑密度扫描；定义环路拥堵判据" },
        { who: "C", en: "Choose a district (preferably in Singapore, with several arterial roads, so it can be compared with LTA data) and import it from OSM; spot-check lane counts and speed limits on main roads; define the network congestion criterion", zh: "选定城区（优先新加坡，并包含若干条主干道，便于和 LTA 数据对照）并从 OSM 导入 SUMO；抽查主要道路的车道数和限速；定义路网拥堵判据" },
        { who: "D", en: "Build the 4×4 test grid and validate the pipeline with C", zh: "搭建 4×4 测试网格，并与 C 一起验证流程" },
        { who: "E", en: "Apply for PeMS / highD / LTA access; draft critical-point and error-bar scripts on trial data", zh: "提交 PeMS / highD / LTA 数据申请；用试跑数据写临界点估计和误差分析脚本" },
        { who: "E", en: "Start recording LTA speed bands on a schedule (DataMall only serves current data), covering weekday morning and evening peaks", zh: "开始定时抓取并保存 LTA 速度带数据（DataMall 只提供实时数据），覆盖工作日早晚高峰" }
      ]
    },
    {
      start: "2026-10-15", end: "2026-10-21",
      title: { en: "Main experiments", zh: "主要实验" },
      items: [
        { who: "A", en: "Finish OVM; validate NaSch (p = 0) and OVM stability with B", zh: "完成 OVM；与 B 一起完成 NaSch（p = 0）和 OVM 稳定性验证" },
        { who: "A", en: "Run formal batches on the pinned build; add the in-browser ring demo to the ring page", zh: "用固定版本运行正式批量实验；把浏览器内的环路演示加入环路页面" },
        { who: "B", en: "Ring sweeps for NaSch / OVM / IDM: density, system size, randomness, bottleneck", zh: "三种模型的环路扫描：密度、系统尺寸、随机性、瓶颈" },
        { who: "C", en: "TraCI controller for constant density; network density sweeps and MFD", zh: "实现恒定密度的 TraCI 控制器；路网密度扫描与宏观基本图" },
        { who: "C", en: "Review B's ring protocol and density sweeps", zh: "复核 B 的环路协议和密度扫描" },
        { who: ["C", "E"], en: "Build the lookup table between SUMO edges and LTA road stretches (match by start/end coordinates, direction and road name)", zh: "建立 SUMO 边与 LTA 路段的对照表（按起止经纬度、方向和路名匹配）" },
        { who: "D", en: "Prototype baseline, road-closure and new-link scenarios on the grid", zh: "在网格上试做基准、封路和新增连接场景" },
        { who: "D", en: "Review C's network pipeline before reusing it", zh: "复核 C 的路网流程，确认可以直接沿用" },
        { who: "E", en: "Critical-point analysis for the ring; confirm the method with B and C", zh: "环路的临界点分析；与 B、C 确认分析方法" },
        { who: ["A", "E"], en: "Review each other: E's analysis scripts, A's run records", zh: "互相复核：E 的分析脚本，A 的运行记录" }
      ]
    },
    {
      start: "2026-10-22", end: "2026-10-28",
      title: { en: "Planning runs & figures", zh: "规划实验与图表" },
      note: { en: "Lighter week: course test on 24 Oct", zh: "任务较轻的一周：10月24日有课程测验" },
      items: [
        { who: "A", en: "Export validated results to the site", zh: "把通过验证的结果导出到网站" },
        { who: "B", en: "Final fundamental and space–time diagrams", zh: "完成基本图和时空图" },
        { who: "B", en: "Review D's planning scenarios", zh: "复核 D 的规划场景" },
        { who: "C", en: "Queues, congested clusters and betweenness analysis", zh: "排队、拥堵连通区域和边介数分析" },
        { who: "D", en: "Planning sweeps on the district; compare MFD peaks; test for a Braess effect", zh: "在城区路网上运行规划扫描，比较宏观基本图峰值，检验 Braess 悖论" },
        { who: "E", en: "Network critical points; compare with PeMS / highD / LTA data", zh: "路网临界点分析；与 PeMS / highD / LTA 数据对照" }
      ]
    },
    {
      start: "2026-10-29", end: "2026-11-01",
      title: { en: "Integrate results", zh: "整合结果" },
      items: [
        { who: "A", en: "Run the meeting that freezes conclusions; set the slide outline and assign slides", zh: "组织会议确定结论；制定幻灯片大纲并分配页面" },
        { who: "E", en: "Pull results together into the cross-workstream conclusions", zh: "把各方向结果汇总成整体结论" },
        { who: ["B", "C", "D"], en: "Write conclusions and limitations for your own workstream", zh: "写好自己方向的结论和局限" },
        { who: "all", en: "Draft your own slides", zh: "完成自己负责的幻灯片初稿" }
      ]
    },
    {
      start: "2026-11-02", end: "2026-11-05",
      title: { en: "Presentation", zh: "展示" },
      items: [
        { who: "all", en: "Rehearse the talk (15 min + 3 min Q&A)", zh: "排练展示（15 分钟 + 3 分钟问答）" },
        { who: "A", en: "Assemble the deck and submit by 5 Nov, 6:00 pm", zh: "合并幻灯片，11月5日 18:00 前提交" }
      ]
    },
    {
      start: "2026-11-06", end: "2026-11-15",
      title: { en: "Report drafting & peer grading", zh: "撰写报告与互评" },
      items: [
        { who: "all", en: "Write methods, results and limitations for your own workstream", zh: "撰写自己方向的方法、结果和局限" },
        { who: "A", en: "Edit the group report into one document (at least 10 pages)", zh: "统稿小组报告（至少 10 页）" },
        { who: "all", en: "Complete peer grading by 15 Nov", zh: "11月15日前完成互评" }
      ]
    },
    {
      start: "2026-11-16", end: "2026-11-22",
      title: { en: "Final submission", zh: "最终提交" },
      items: [
        { who: "all", en: "Write individual reports", zh: "撰写个人报告" },
        { who: "A", en: "Finalize report, data and code; submit by 22 Nov, 11:59 pm", zh: "完善报告、数据和代码，11月22日 23:59 前提交" }
      ]
    }
  ],

  // Cross-review. In each ring a member reviews the next one and the last reviews the first:
  // A and E review each other (outer ring); D → C → B → D (inner ring).
  // `flows` label the hand-offs: A passes tools and the plan to B–D; E sends methods and receives results.
  review: {
    outer: ["A", "E"],
    inner: ["D", "C", "B"],
    roles: {
      A: { en: "A · coordinates the project, supplies tools and rules", zh: "A · 全局统筹，提供工具和规则" },
      E: { en: "E · sets analysis methods, pulls results together", zh: "E · 制定分析方法，汇总结论" }
    },
    flows: {
      tools: { en: "Tools & plan", zh: "工具与安排" },
      results: { en: "Results", zh: "实验结果" },
      methods: { en: "Methods", zh: "分析方法" }
    }
  },

  // owner is the primary owner's letter, ownerName (optional) is shown in its place.
  // Each task has a fixed id (owner letter + number). The live status is stored under that id in Firebase
  // (see assets/live.js) and is changed by clicking the task on the member's page; `status` here is only the
  // fallback when Firebase cannot be reached. Never change or reuse an id: give a new task the next free number.
  // status: "todo" | "doing" | "done". `detail` lists the task's key points (what it involves and what it
  // is for), one short line each, shown as bullets on the member page.
  workstreams: [
    {
      name: { en: "Shared framework & model validation", zh: "共享框架与模型验证" },
      stage: { en: "A · Coordination & foundation", zh: "A · 统筹与基础" },
      owner: "A",
      ownerName: "Zhongjie",
      summary: {
        en: "Coordinate the project, define the shared run protocol, build SUMO, implement OVM and make the smallest end-to-end experiment runnable.",
        zh: "统筹全局安排，定义共享运行协议，编译 SUMO，实现 OVM，并打通最小端到端实验。"
      },
      tasks: [
        {
          id: "A1", status: "doing",
          text: { en: "Define config, run-record and output interfaces", zh: "定义配置、运行记录和输出接口" },
          detail: {
            en: [
              "Config file: model, density, ring length, seed, simulation and warm-up time",
              "Run record: config, seed and code version",
              "Output files and units: veh/km, veh/h",
              "B–E all read and write these files, so fixing them first lets everyone work in parallel and keeps results comparable and reproducible"
            ],
            zh: [
              "配置文件：模型、密度、环路长度、随机种子、模拟时长和预热时长",
              "运行记录：配置、随机种子和代码版本",
              "输出文件的格式和单位：veh/km、veh/h",
              "B–E 的脚本都读写这些文件；先定下来，各方向才能并行开发，结果也能直接比较和复现"
            ]
          }
        },
        {
          id: "A2", status: "todo",
          text: { en: "Build SUMO from source at a pinned commit", zh: "从源码编译 SUMO，并固定 commit" },
          detail: {
            en: [
              "Compile SUMO from source; record the commit and the build steps",
              "Publish a ring-road example that runs on this build, plus the run rules",
              "Needed because OVM must be compiled in; one pinned build keeps results identical across computers"
            ],
            zh: [
              "从源码编译 SUMO，记下所用的 commit 和编译步骤",
              "发布一个能在这个版本上运行的环路示例，以及运行规则",
              "OVM 要编译进 SUMO；统一固定版本，避免不同电脑结果不一致"
            ]
          }
        },
        {
          id: "A3", status: "todo",
          text: { en: "Implement OVM in SUMO (C++) and go through its validation with B", zh: "用 C++ 在 SUMO 中实现 OVM，并与 B 一起确认验证结果" },
          detail: {
            en: [
              "Implement OVM in C++ by subclassing MSCFModel, following the built-in IDM; register it as carFollowModel=\"OVM\"",
              "With B, perturb densities on both sides of V′(h) = a/2: the perturbation should decay on the stable side and grow into stop-and-go waves on the unstable side",
              "Check that vehicles never overlap",
              "OVM's analytic instability condition is what checks the simulated critical density against theory"
            ],
            zh: [
              "参照内置 IDM，用 C++ 继承 MSCFModel 实现 OVM，注册为 carFollowModel=\"OVM\"",
              "与 B 一起在 V′(h) = a/2 两侧加入微小扰动：稳定一侧应衰减，失稳一侧应放大为走走停停波",
              "检查车辆不会重叠",
              "OVM 有解析的失稳条件，用来检验模拟得到的临界密度"
            ]
          }
        },
        {
          id: "A4", status: "todo",
          text: { en: "Add validation checks and a minimal end-to-end run", zh: "加入验证检查并打通最小端到端运行" },
          detail: {
            en: [
              "Every run checks automatically: vehicle count conserved, speeds non-negative, no overlaps",
              "NaSch with p = 0 must reproduce J = min(ρ·vmax, 1 − ρ)",
              "Get the smallest pipeline working: config → SUMO run → output → plot, for the others to build on"
            ],
            zh: [
              "每次运行自动检查：车辆数守恒、速度非负、车辆不重叠",
              "NaSch 在 p = 0 时的基本图须与 J = min(ρ·vmax, 1 − ρ) 一致",
              "打通最小流程：配置 → SUMO 运行 → 输出 → 画图，供其他人在上面扩展"
            ]
          }
        },
        {
          id: "A5", status: "todo",
          text: { en: "Review E's analysis scripts and their use of run data", zh: "复核 E 的分析脚本及其对运行数据的使用" },
          detail: {
            en: [
              "Check that E's scripts read run data as agreed: units, seed groups, warm-up period removed",
              "Every critical density is computed with these functions, so an error here affects all conclusions"
            ],
            zh: [
              "检查 E 的脚本是否按约定读取运行数据：单位、随机种子分组、是否剔除预热时段",
              "所有临界密度都用这些函数计算，读错数据会影响全部结论"
            ]
          }
        },
        {
          id: "A6", status: "todo",
          text: { en: "Provide reproducible run records for the report and site", zh: "为报告和网站提供可复现的运行记录" },
          detail: {
            en: [
              "For every formal result, keep config, seeds, code version and output data",
              "Organise them so the report and the site cite the same records"
            ],
            zh: [
              "为每个正式结果保存配置、随机种子、代码版本和输出数据",
              "整理成报告和网站可以直接引用的形式，保证两者使用同一套记录"
            ]
          }
        },
        {
          id: "A7", status: "todo",
          text: { en: "Coordinate the group report, slides and rehearsal", zh: "协调小组报告、幻灯片和排练" },
          detail: {
            en: [
              "Set the report and slide outlines and assign sections",
              "Edit the group report into one document (at least 10 pages)",
              "Merge the slides and submit by 5 Nov, 6:00 pm; run the rehearsal (15 min + 3 min Q&A)"
            ],
            zh: [
              "制定报告和幻灯片大纲，分配章节",
              "统稿小组报告（至少 10 页）",
              "合并幻灯片，11月5日 18:00 前提交；组织排练（15 分钟 + 3 分钟问答）"
            ]
          }
        },
        {
          id: "A8", status: "todo",
          text: { en: "Maintain the site and add the in-browser ring demo to the ring page", zh: "维护网站，并把浏览器内的环路演示加入环路页面" },
          detail: {
            en: [
              "Maintain the site and export SUMO results to it",
              "Add a live in-browser ring demo to the ring page, with model, vehicle-count and parameter controls",
              "The demo is illustrative only; all report data come from SUMO"
            ],
            zh: [
              "维护项目网站，把 SUMO 结果导出到网站",
              "在环路页面加入浏览器内实时运行的环路演示，可选模型、车辆数和参数",
              "演示只作示意，报告中的数据都来自 SUMO"
            ]
          }
        }
      ]
    },
    {
      name: { en: "Highway congestion mechanisms", zh: "高速公路拥堵机制" },
      stage: { en: "B · RQ1", zh: "B · RQ1" },
      owner: "B",
      ownerName: "Guowei",
      summary: {
        en: "Own the ring-road experiment and distinguish spontaneous congestion from bottleneck-induced congestion.",
        zh: "负责环路实验，区分自发拥堵与瓶颈引起的拥堵。"
      },
      tasks: [
        {
          id: "B1", status: "todo",
          text: { en: "Define ring-road scenarios, density sweeps and the ring congestion criterion", zh: "定义环路场景、密度扫描和环路拥堵判据" },
          detail: {
            en: [
              "Build a single-lane closed ring in SUMO with no signals",
              "Choose densities (denser near the transition), at least three ring lengths, simulation and warm-up times",
              "Define the ring congestion criterion: the speed below which a vehicle counts as jammed",
              "The criterion defines the order parameter φ used in E's critical-point analysis"
            ],
            zh: [
              "在 SUMO 中搭建无信号的单车道闭合环路",
              "确定密度取值（临界附近加密）、至少三种环路长度、模拟时长和预热时长",
              "定义环路拥堵判据：速度低于什么阈值算作拥堵车辆",
              "这个判据决定序参量 φ 的计算方式，E 的临界点分析依赖它"
            ]
          }
        },
        {
          id: "B2", status: "todo",
          text: { en: "Run NaSch / OVM / IDM ring-road experiments", zh: "运行 NaSch / OVM / IDM 环路实验" },
          detail: {
            en: [
              "Prepare configs for NaSch, OVM and IDM on the same rings and densities, several seeds each",
              "Set NaSch's sigma explicitly; IDM uses speedDev=0",
              "Trial runs on release SUMO; formal batches on A's pinned build",
              "Answers RQ1: do all three models show a flow peak, a rising order parameter and a fluctuation peak?"
            ],
            zh: [
              "为 NaSch、OVM、IDM 准备同一组环路和密度的配置，每组多个随机种子",
              "NaSch 显式设置 sigma，IDM 设置 speedDev=0",
              "试跑用正式版 SUMO，正式批量运行使用 A 编译的固定版本",
              "回答 RQ1：三种模型是否都出现流量峰值、序参量上升和涨落峰值"
            ]
          }
        },
        {
          id: "B3", status: "todo",
          text: { en: "Compare density, system size, randomness and bottleneck", zh: "比较密度、系统尺寸、随机性和瓶颈条件" },
          detail: {
            en: [
              "Change one factor per set: ring length, NaSch's slowdown probability, bottleneck (none / reduced-speed section)",
              "A transition that sharpens on longer rings has the signature of a phase transition",
              "With vs. without bottleneck: compare peak flow and critical density, and whether jams drift backward or stay upstream",
              "This separates spontaneous jams from bottleneck jams"
            ],
            zh: [
              "每组只改变一个因素：环路长度、NaSch 的随机减速概率、瓶颈（无 / 限速路段）",
              "环路越长转变越陡，说明具有相变特征",
              "有无瓶颈对照：比较最大流量和临界密度，以及拥堵带是向后漂移还是停在瓶颈上游",
              "用来区分自发拥堵和瓶颈拥堵"
            ]
          }
        },
        {
          id: "B4", status: "todo",
          text: { en: "Produce fundamental and space–time diagrams", zh: "生成基本图和时空图" },
          detail: {
            en: [
              "Fundamental diagrams: density vs. mean speed and vs. flow, three models per plot",
              "Order parameter φ and fluctuation χ, one curve per ring length; an extra set for NaSch's slowdown probabilities",
              "Space–time diagrams",
              "These are the main evidence for RQ1"
            ],
            zh: [
              "基本图：密度–平均速度、密度–流量，每张图三种模型",
              "序参量 φ 与涨落 χ：每种环路长度一条曲线，NaSch 另画一组不同随机减速概率",
              "时空图",
              "这些是 RQ1 的主要证据"
            ]
          }
        },
        {
          id: "B5", status: "todo",
          text: { en: "Review D's planning scenarios for consistent demand and routes", zh: "复核 D 的规划场景，确认需求和路线一致" },
          detail: {
            en: [
              "Check that D's scenarios share densities, route rule and seed groups, so only the changed road differs",
              "Otherwise differences between scenarios cannot be attributed to the road change"
            ],
            zh: [
              "检查 D 的各方案是否使用相同的密度取值、路线规则和随机种子组，只有被改动的路段不同",
              "否则方案之间的差异不能归因于路网改动"
            ]
          }
        },
        {
          id: "B6", status: "todo",
          text: { en: "Prepare ring results for the report and site", zh: "为报告和网站整理环路结果" },
          detail: {
            en: [
              "Turn ring results into report figures and export them to the site in A's format",
              "Write the ring experiment's conclusions and limitations",
              "The highway critical density from the ring is the reference for the city network"
            ],
            zh: [
              "把环路结果整理成报告所需的图，按 A 规定的格式导出到网站",
              "写出环路部分的结论和局限",
              "环路给出的 highway 临界密度是路网实验的对照"
            ]
          }
        }
      ]
    },
    {
      name: { en: "City network experiments", zh: "城市路网实验" },
      stage: { en: "C · RQ2", zh: "C · RQ2" },
      owner: "C",
      ownerName: "Yixiang",
      summary: {
        en: "Build the city-network pipeline, keep density constant and measure how local jams spread.",
        zh: "搭建城市路网流程，保持网络密度恒定，并测量局部拥堵的扩展。"
      },
      tasks: [
        {
          id: "C1", status: "todo",
          text: { en: "Choose a district (preferably in Singapore, with several arterial roads) and import it from OSM into SUMO; spot-check lane counts and speed limits", zh: "选定城区（优先新加坡，并包含若干条主干道）并从 OSM 导入 SUMO；抽查车道数和限速" },
          detail: {
            en: [
              "Choose a district, preferably in Singapore with several arterial roads, so it can be compared with LTA data",
              "Import raw OpenStreetMap data with netconvert (OSMnx's export loses turn restrictions and lane tags)",
              "Spot-check: the network matches OSM's lane counts and speed limits on 18 of 18 main roads; whether OSM matches the street is an optional Street View check"
            ],
            zh: [
              "选定城区，优先新加坡并包含若干条主干道，便于和 LTA 数据对照",
              "用 netconvert 导入 OpenStreetMap 原始数据（OSMnx 导出时会丢失转向限制和车道标签）",
              "抽查：18 条主要道路的车道数和限速全部与 OSM 一致；OSM 与实际道路是否一致，可选用街景核对"
            ]
          }
        },
        {
          id: "C2", status: "todo",
          text: { en: "Build the SUMO edge ↔ LTA road stretch lookup table with E", zh: "和 E 一起建立 SUMO 边与 LTA 路段的对照表" },
          detail: {
            en: [
              "With E, match each SUMO edge to an LTA road stretch by start/end coordinates, direction and road name",
              "Needed to compare simulated hotspots with the slowest LTA roads on one map"
            ],
            zh: [
              "和 E 一起，按起止经纬度、方向和路名，把 SUMO 的每条边对应到 LTA 路段",
              "用于把模拟中最常拥堵的路段和 LTA 中最慢的路段画在同一张地图上比较"
            ]
          }
        },
        {
          id: "C3", status: "todo",
          text: { en: "Define the network congestion criterion for road segments", zh: "定义路网拥堵判据（判定路段拥堵的标准）" },
          detail: {
            en: [
              "Define when a road segment counts as congested (persistent low speed)",
              "Define how adjacent congested segments join into a congested cluster",
              "Stopped share, largest cluster and congestion onset all depend on it; D reuses it"
            ],
            zh: [
              "规定路段在什么条件下算作拥堵（持续低速）",
              "规定相连的拥堵路段如何合并成拥堵连通区域",
              "停驶比例、最大拥堵区域和开始拥堵的时刻都依赖这个判据，D 也沿用它"
            ]
          }
        },
        {
          id: "C4", status: "todo",
          text: { en: "Implement the TraCI controller for constant network density", zh: "实现保持网络密度恒定的 TraCI 控制器" },
          detail: {
            en: [
              "With TraCI, give a vehicle nearing the end of its route a new random destination, so none arrives; every car re-plans its route every 60 s",
              "This keeps the number of vehicles in the network constant",
              "Network density = vehicles in the network ÷ total lane length; controlling only the inflow gives no well-defined density"
            ],
            zh: [
              "用 TraCI 给接近路线终点的车辆分配新的随机目的地，使车辆不会到达终点；每辆车每 60 秒重新规划一次路线",
              "使路网内车辆数保持不变",
              "网络密度 = 路网内车辆数 ÷ 车道总长度；只控制进入需求，就得不到确定的网络密度"
            ]
          }
        },
        {
          id: "C5", status: "todo",
          text: { en: "Run network-density sweeps and export representative runs", zh: "运行网络密度扫描并导出代表性运行" },
          detail: {
            en: [
              "Validate on D's 4×4 grid first",
              "Sweep network density from low to high, several seeds per density",
              "Export trajectory clips of a few representative runs for replay on the site",
              "The top of the MFD gives the maximum flow and the critical density; in the city the top is flat from 20 to 35 veh/km, so the critical density is a range (RQ2)"
            ],
            zh: [
              "先在 D 的 4×4 网格上验证",
              "由低到高扫描网络密度，每个密度多个随机种子",
              "导出少量代表性运行的车辆轨迹片段，供网站回放",
              "宏观基本图的顶部给出最大流量和临界密度；城市路网的顶部在 20–35 veh/km 之间是平的，因此临界密度是一个区间（RQ2）"
            ]
          }
        },
        {
          id: "C6", status: "todo",
          text: { en: "Measure MFD inputs, queues and congested clusters", zh: "测量宏观基本图输入、排队和拥堵连通区域" },
          detail: {
            en: [
              "Network mean flow and speed, stopped-vehicle share, queue lengths and spillbacks",
              "Size of the largest congested cluster: does it grow quickly near the critical density?",
              "Edge betweenness (NetworkX) vs. when each segment becomes congested: does structure predict where jams start?"
            ],
            zh: [
              "网络平均流量和速度、停驶车辆比例、排队长度和回溢次数",
              "最大拥堵连通区域的规模：是否在临界密度附近迅速扩大",
              "边介数（NetworkX）与各路段开始拥堵的时刻：路网结构能否预测拥堵最先出现的位置"
            ]
          }
        },
        {
          id: "C7", status: "todo",
          text: { en: "Review B's ring protocol and density sweeps", zh: "复核 B 的环路协议和密度扫描" },
          detail: {
            en: [
              "Check B's ring protocol: one variable per set, enough warm-up, density and units, seed groups",
              "The ring's highway critical density is compared with the network's; a flawed protocol breaks that comparison"
            ],
            zh: [
              "检查 B 的环路协议：每组只改一个变量、预热是否足够、密度和单位换算、随机种子分组",
              "环路临界密度要与路网临界密度比较，协议有问题这个比较就不成立"
            ]
          }
        }
      ]
    },
    {
      name: { en: "Planning interventions", zh: "规划干预方案" },
      stage: { en: "D · RQ3", zh: "D · RQ3" },
      owner: "D",
      ownerName: "Daniel",
      summary: {
        en: "Build the 4×4 test grid early, then compare baseline, road closure and new-link scenarios under the same density values and seeds.",
        zh: "先搭建 4×4 测试网格，再在相同密度取值和随机种子下比较基准、封路和新增连接方案。"
      },
      tasks: [
        {
          id: "D1", status: "todo",
          text: { en: "Build the 4×4 test grid and validate the pipeline with C", zh: "搭建 4×4 测试网格，并与 C 一起验证流程" },
          detail: {
            en: [
              "Build a 4×4 grid network in SUMO",
              "With C, run the whole network pipeline on it: constant-density control, density sweep, metrics",
              "A small regular grid makes problems easy to find before moving to the real district"
            ],
            zh: [
              "在 SUMO 中搭建 4×4 网格路网",
              "和 C 一起在上面跑通路网流程：恒定密度控制、密度扫描、指标统计",
              "网格小、结构规整，问题容易定位，验证后再用到真实城区"
            ]
          }
        },
        {
          id: "D2", status: "todo",
          text: { en: "Prototype baseline, road-closure and new-link scenarios on the grid, then port them to the district", zh: "先在网格上做出基准、封路和新增连接场景，再移植到城区路网" },
          detail: {
            en: [
              "Build three scenarios on the grid: baseline, road closure (close a high-betweenness segment or cut its lanes), new link",
              "Once they work, port them to C's district network for the formal runs"
            ],
            zh: [
              "在网格上做出三个方案：基准、道路封闭（封闭高介数路段或减少车道）、新增连接",
              "跑通后移植到 C 的城区路网正式运行"
            ]
          }
        },
        {
          id: "D3", status: "todo",
          text: { en: "Reuse C's density values, routes and seed groups", zh: "沿用 C 的密度取值、路线和随机种子组" },
          detail: {
            en: [
              "Use the same density values, route rule and seed groups as the network experiment",
              "Then a shift in critical density can be attributed to the planning change, and the baseline checked against C's results"
            ],
            zh: [
              "使用与路网实验相同的密度取值、路线规则和随机种子组",
              "这样临界密度的变化才能归因于规划改动，基准也能与 C 的结果对照"
            ]
          }
        },
        {
          id: "D4", status: "todo",
          text: { en: "Run planning sweeps and compare MFD peaks", zh: "运行规划扫描并比较宏观基本图峰值" },
          detail: {
            en: [
              "Run every scenario at every density with several seeds",
              "Overlay the MFDs; compare peak position (critical density) and height (maximum flow) with error bars",
              "Map each segment's speed change against the baseline",
              "Answers RQ3: a higher critical density means more vehicles before congestion"
            ],
            zh: [
              "每个方案、每个密度运行多个随机种子",
              "把各方案的宏观基本图叠在一起，比较峰值位置（临界密度）和高度（最大流量），附误差范围",
              "画出各路段相对基准的速度变化地图",
              "回答 RQ3：临界密度提高，说明路网能承载更多车辆而不进入拥堵"
            ]
          }
        },
        {
          id: "D5", status: "todo",
          text: { en: "Test whether a new link produces a Braess effect", zh: "检验新增连接是否产生 Braess 悖论" },
          detail: {
            en: [
              "Compare the new-link scenario with the baseline",
              "If critical density or maximum flow is lower and outside the error range, that is a Braess paradox",
              "Tests whether adding a road always improves the system"
            ],
            zh: [
              "比较新增连接方案与基准",
              "临界密度或最大流量任一项低于基准且超出误差范围，就是 Braess 悖论",
              "检验增加道路是否一定改善系统"
            ]
          }
        },
        {
          id: "D6", status: "todo",
          text: { en: "Review C's network pipeline, units and seeds before reusing them", zh: "复核 C 的路网流程、单位和随机种子，确认可以直接沿用" },
          detail: {
            en: [
              "Before reusing C's pipeline, check how network density is computed and its units",
              "Check that constant-density control really keeps the vehicle count fixed, and how seeds are used",
              "All of D's scenarios build on it; finding problems early saves rework"
            ],
            zh: [
              "沿用 C 的流程前，检查网络密度的计算方式和单位",
              "检查恒定密度控制是否真的使车辆数不变，以及随机种子的使用方式",
              "D 的所有方案都建立在这套流程上，越早发现问题，返工越少"
            ]
          }
        },
        {
          id: "D7", status: "todo",
          text: { en: "Prepare planning figures for the report and site", zh: "为报告和网站整理规划方案图表" },
          detail: {
            en: [
              "MFD overlay; critical density and maximum flow per scenario; congestion-change maps",
              "For the report, and exported to the site in A's format"
            ],
            zh: [
              "宏观基本图叠加图、各方案的临界密度与最大流量图、拥堵变化地图",
              "用于报告，并按 A 规定的格式导出到网站"
            ]
          }
        }
      ]
    },
    {
      name: { en: "Analysis, data & integration", zh: "分析、数据与整合" },
      stage: { en: "E · Methods & data", zh: "E · 方法与数据" },
      owner: "E",
      ownerName: "Hongfang",
      summary: {
        en: "Set the critical-point and uncertainty methods, compare with real data and pull the results into conclusions and site exports.",
        zh: "制定临界点估计和误差分析方法，与真实数据对照，并把结果汇总成结论和网站数据。"
      },
      tasks: [
        {
          id: "E1", status: "todo",
          text: { en: "Define critical-point estimators and error bars; B and C supply the congestion criteria", zh: "制定临界点估计方法和误差范围（拥堵判据由 B、C 分别定义）" },
          detail: {
            en: [
              "Estimate the critical density from a sweep: flow peak, rise of the order parameter, fluctuation peak",
              "Give an error range from repeated runs",
              "B and C define the congestion criteria; one method for all experiments puts every critical density on the same axis"
            ],
            zh: [
              "从扫描结果估计临界密度：流量峰值、序参量上升、涨落峰值",
              "用重复实验给出误差范围",
              "拥堵判据由 B、C 分别定义；所有实验用同一套方法，临界密度才能放在同一根轴上比较"
            ]
          }
        },
        {
          id: "E2", status: "todo",
          text: { en: "Provide shared analysis functions that estimate the critical density and its error range, for B and C to call in their own plots; confirm the method with B and C", zh: "提供临界密度估计和误差范围的共用分析函数，供 B、C 画自己的图时调用，并与 B、C 确认方法" },
          detail: {
            en: [
              "Shared functions: sweep data in, critical density and error range out",
              "B and C call them in their own plots; confirm the method with them",
              "Avoids each person computing it differently"
            ],
            zh: [
              "共用函数：输入扫描数据，输出临界密度和误差范围",
              "B、C 画图时直接调用，并与他们确认方法",
              "避免每人各写一套方法，导致结果无法比较"
            ]
          }
        },
        {
          id: "E3", status: "todo",
          text: { en: "Apply for PeMS / highD / LTA access in week 1 (approval takes time)", zh: "第一周提交 PeMS / highD / LTA 数据申请（审核需要时间）" },
          detail: {
            en: [
              "In week 1, register or apply for PeMS and highD, and apply for LTA DataMall access",
              "Approval takes time; applying late delays the comparison with real data"
            ],
            zh: [
              "第一周完成 PeMS、highD 的注册或申请，以及 LTA DataMall 的访问申请",
              "审核需要时间，申请晚了会拖慢与真实数据的对照"
            ]
          }
        },
        {
          id: "E4", status: "todo",
          text: { en: "Record LTA speed bands on a schedule from week 2 (only current data is served), covering weekday peaks", zh: "第 2 周起定时抓取并保存 LTA 速度带数据（只提供实时数据），覆盖工作日早晚高峰" },
          detail: {
            en: [
              "From week 2, a scheduled script fetches and saves LTA speed bands",
              "Cover weekday morning and evening peaks",
              "DataMall serves only current data, so history cannot be downloaded later"
            ],
            zh: [
              "第 2 周起用定时脚本抓取并保存 LTA 速度带数据",
              "覆盖工作日早晚高峰",
              "DataMall 只提供实时数据，事后无法下载历史数据"
            ]
          }
        },
        {
          id: "E5", status: "todo",
          text: { en: "Obtain and clean PeMS / highD / LTA comparison data", zh: "获取并清洗 PeMS / highD / LTA 对照数据" },
          detail: {
            en: [
              "Obtain PeMS, highD and LTA data; unify units; handle missing and abnormal values",
              "Convert PeMS to a per-lane basis",
              "Used to compare diagram shape, critical-density size and congestion locations; not for per-vehicle calibration"
            ],
            zh: [
              "获取 PeMS、highD 和 LTA 数据，统一单位，处理缺失值和异常值",
              "PeMS 数据按单车道换算",
              "用于对照基本图形状、临界密度量级和拥堵位置，不用于逐车校准"
            ]
          }
        },
        {
          id: "E6", status: "todo",
          text: { en: "Build the SUMO edge ↔ LTA road stretch lookup table with C", zh: "和 C 一起建立 SUMO 边与 LTA 路段的对照表" },
          detail: {
            en: [
              "With C, match each SUMO edge to an LTA road stretch by start/end coordinates, direction and road name",
              "Needed to put simulated hotspots and the slowest LTA roads on the same map"
            ],
            zh: [
              "和 C 一起，按起止经纬度、方向和路名，把 SUMO 的每条边对应到 LTA 路段",
              "用于把模拟中的拥堵热点和 LTA 中最慢的路段放在同一张地图上比较"
            ]
          }
        },
        {
          id: "E7", status: "todo",
          text: { en: "Review A's run records for reproducibility", zh: "复核 A 的运行记录，确保可复现" },
          detail: {
            en: [
              "Check that A's run records are complete: config, seeds, code version, output",
              "Spot-check that a few runs reproduce from the records"
            ],
            zh: [
              "检查 A 的运行记录是否完整：配置、随机种子、代码版本、输出",
              "抽查几次运行能否按记录复现"
            ]
          }
        },
        {
          id: "E8", status: "todo",
          text: { en: "Check that the results on the site match the analysis", zh: "检查网站上的结果与分析结论一致" },
          detail: {
            en: [
              "Compare numbers, units, parameters and run IDs on the site with the analysis and the report",
              "Values on the site must match the formal run records"
            ],
            zh: [
              "对照分析结果和报告，检查网站上的数值、单位、参数和实验编号",
              "网页中的数值必须与正式实验记录一致"
            ]
          }
        }
      ]
    }
  ],

  resources: [
    {
      group: { en: "Project documents", zh: "项目文档" },
      links: [
        { label: { en: "Project overview (English)", zh: "项目概览（英文）" }, url: "https://github.com/laozhongjie/agent-based-traffic-modeling/blob/main/Project_Overview_EN.md", note: { en: "Full description of questions, experiments and methods", zh: "研究问题、三个实验和方法的完整说明" } },
        { label: { en: "Project overview (Chinese)", zh: "项目概览（中文）" }, url: "https://github.com/laozhongjie/agent-based-traffic-modeling/blob/main/Project_Overview.md", note: { en: "Chinese version", zh: "中文版" } },
        { label: { en: "GitHub repository", zh: "GitHub 仓库" }, url: "https://github.com/laozhongjie/agent-based-traffic-modeling", note: { en: "Code, data and documents (private)", zh: "代码、数据和文档（私有）" } }
      ]
    },
    {
      group: { en: "Key papers", zh: "关键论文" },
      links: [
        { label: "Nagel & Schreckenberg, 1992", url: "https://doi.org/10.1051/jp1:1992277", note: { en: "Cellular automaton model for highway traffic", zh: "高速公路交通的元胞自动机模型" } },
        { label: "Bando et al., 1995", url: "https://doi.org/10.1103/PhysRevE.51.1035", note: { en: "Optimal Velocity Model", zh: "最优速度模型（OVM）" } },
        { label: "Sugiyama et al., 2008", url: "https://doi.org/10.1088/1367-2630/10/3/033001", note: { en: "Traffic jams without bottlenecks", zh: "没有瓶颈的交通拥堵" } },
        { label: "Geroliminis & Daganzo, 2008", url: "https://doi.org/10.1016/j.trb.2008.02.002", note: { en: "Macroscopic fundamental diagram", zh: "宏观基本图（MFD）" } },
        { label: "Li et al., 2015 (PNAS)", url: "https://doi.org/10.1073/pnas.1419185112", note: { en: "Percolation transition in traffic networks", zh: "交通网络中的渗流相变" } }
      ]
    },
    {
      group: { en: "Tools", zh: "工具" },
      links: [
        { label: "Traffic Simulation", url: "https://traffic-simulation.de/", note: { en: "Interactive IDM demos", zh: "IDM 交互演示" } },
        { label: { en: "IDM description", zh: "IDM 说明" }, url: "https://traffic-simulation.de/info/info_IDM.html", note: { en: "Equations and parameters", zh: "方程与参数" } },
        { label: { en: "SUMO documentation", zh: "SUMO 文档" }, url: "https://sumo.dlr.de/docs/", note: { en: "Network simulation", zh: "路网仿真" } },
        { label: "OSMnx", url: "https://osmnx.readthedocs.io/en/stable/getting-started.html", note: { en: "Download OpenStreetMap networks", zh: "下载 OpenStreetMap 路网" } },
        { label: "NetworkX", url: "https://networkx.org/documentation/stable/tutorial.html", note: { en: "Network analysis", zh: "网络分析" } },
        { label: { en: "ECharts examples", zh: "ECharts 示例" }, url: "https://echarts.apache.org/examples/en/index.html", note: { en: "Interactive charts", zh: "交互图表" } }
      ]
    },
    {
      group: { en: "Data", zh: "数据" },
      links: [
        { label: "PeMS", url: "https://pems.dot.ca.gov/", note: { en: "Highway detector data (registration required)", zh: "高速公路检测器数据（需注册）" } },
        { label: { en: "highD dataset", zh: "highD 数据集" }, url: "https://levelxdata.com/highd-dataset/", note: { en: "Highway vehicle trajectories (request access)", zh: "高速公路车辆轨迹（需申请）" } },
        { label: "LTA DataMall", url: "https://datamall.lta.gov.sg/content/datamall/en/dynamic-data.html", note: { en: "Singapore traffic speed bands", zh: "新加坡路段速度数据" } }
      ]
    }
  ]
};
