// Project data for the hub page.
// Text fields are { en, zh }. A plain string is shown in both languages.
// To update progress: change a task's status to "todo", "doing" or "done",
// fill in owners, bump `updated`, then commit and push.

window.PROJECT = {
  updated: "2026-10-07",
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
        { who: "C", en: "Choose a district and import it from OSM; define the network congestion criterion", zh: "选定城区并从 OSM 导入 SUMO；定义路网拥堵判据" },
        { who: "D", en: "Build the 4×4 test grid and validate the pipeline with C", zh: "搭建 4×4 测试网格，并与 C 一起验证流程" },
        { who: "E", en: "Apply for PeMS / highD / LTA access; draft critical-point and error-bar scripts on trial data", zh: "提交 PeMS / highD / LTA 数据申请；用试跑数据写临界点估计和误差分析脚本" }
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

  // status: "todo" | "doing" | "done"; owner is the primary owner's letter, ownerName (optional) is shown in its place.
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
        { text: { en: "Define config, run-record and output interfaces", zh: "定义配置、运行记录和输出接口" }, status: "doing" },
        { text: { en: "Build SUMO from source at a pinned commit", zh: "从源码编译 SUMO，并固定 commit" }, status: "todo" },
        { text: { en: "Implement OVM in SUMO (C++) and go through its validation with B", zh: "用 C++ 在 SUMO 中实现 OVM，并与 B 一起确认验证结果" }, status: "todo" },
        { text: { en: "Add validation checks and a minimal end-to-end run", zh: "加入验证检查并打通最小端到端运行" }, status: "todo" },
        { text: { en: "Review E's analysis scripts and their use of run data", zh: "复核 E 的分析脚本及其对运行数据的使用" }, status: "todo" },
        { text: { en: "Provide reproducible run records for the report and site", zh: "为报告和网站提供可复现的运行记录" }, status: "todo" },
        { text: { en: "Coordinate the group report, slides and rehearsal", zh: "协调小组报告、幻灯片和排练" }, status: "todo" },
        { text: { en: "Maintain the site and add the in-browser ring demo to the ring page", zh: "维护网站，并把浏览器内的环路演示加入环路页面" }, status: "todo" }
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
        { text: { en: "Define ring-road scenarios, density sweeps and the ring congestion criterion", zh: "定义环路场景、密度扫描和环路拥堵判据" }, status: "todo" },
        { text: { en: "Run NaSch / OVM / IDM ring-road experiments", zh: "运行 NaSch / OVM / IDM 环路实验" }, status: "todo" },
        { text: { en: "Compare density, system size, randomness and bottleneck", zh: "比较密度、系统尺寸、随机性和瓶颈条件" }, status: "todo" },
        { text: { en: "Produce fundamental and space–time diagrams", zh: "生成基本图和时空图" }, status: "todo" },
        { text: { en: "Review D's planning scenarios for consistent demand and routes", zh: "复核 D 的规划场景，确认需求和路线一致" }, status: "todo" },
        { text: { en: "Prepare ring results for the report and site", zh: "为报告和网站整理环路结果" }, status: "todo" }
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
        { text: { en: "Choose a district and import it from OSM into SUMO", zh: "选定城区并从 OSM 导入 SUMO" }, status: "todo" },
        { text: { en: "Define the network congestion criterion for road segments", zh: "定义路网拥堵判据（判定路段拥堵的标准）" }, status: "todo" },
        { text: { en: "Implement the TraCI controller for constant network density", zh: "实现保持网络密度恒定的 TraCI 控制器" }, status: "todo" },
        { text: { en: "Run network-density sweeps and export representative runs", zh: "运行网络密度扫描并导出代表性运行" }, status: "todo" },
        { text: { en: "Measure MFD inputs, queues and congested clusters", zh: "测量宏观基本图输入、排队和拥堵连通区域" }, status: "todo" },
        { text: { en: "Review B's ring protocol and density sweeps", zh: "复核 B 的环路协议和密度扫描" }, status: "todo" }
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
        { text: { en: "Build the 4×4 test grid and validate the pipeline with C", zh: "搭建 4×4 测试网格，并与 C 一起验证流程" }, status: "todo" },
        { text: { en: "Prototype baseline, road-closure and new-link scenarios on the grid, then port them to the district", zh: "先在网格上做出基准、封路和新增连接场景，再移植到城区路网" }, status: "todo" },
        { text: { en: "Reuse C's density values, routes and seed groups", zh: "沿用 C 的密度取值、路线和随机种子组" }, status: "todo" },
        { text: { en: "Run planning sweeps and compare MFD peaks", zh: "运行规划扫描并比较宏观基本图峰值" }, status: "todo" },
        { text: { en: "Test whether a new link produces a Braess effect", zh: "检验新增连接是否产生 Braess 悖论" }, status: "todo" },
        { text: { en: "Review C's network pipeline, units and seeds before reusing them", zh: "复核 C 的路网流程、单位和随机种子，确认可以直接沿用" }, status: "todo" },
        { text: { en: "Prepare planning figures for the report and site", zh: "为报告和网站整理规划方案图表" }, status: "todo" }
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
        { text: { en: "Define critical-point estimators and error bars; B and C supply the congestion criteria", zh: "制定临界点估计方法和误差范围（拥堵判据由 B、C 分别定义）" }, status: "todo" },
        { text: { en: "Provide shared analysis functions that estimate the critical density and its error range, for B and C to call in their own plots; confirm the method with B and C", zh: "提供临界密度估计和误差范围的共用分析函数，供 B、C 画自己的图时调用，并与 B、C 确认方法" }, status: "todo" },
        { text: { en: "Apply for PeMS / highD / LTA access in week 1 (approval takes time)", zh: "第一周提交 PeMS / highD / LTA 数据申请（审核需要时间）" }, status: "todo" },
        { text: { en: "Obtain and clean PeMS / highD / LTA comparison data", zh: "获取并清洗 PeMS / highD / LTA 对照数据" }, status: "todo" },
        { text: { en: "Review A's run records for reproducibility", zh: "复核 A 的运行记录，确保可复现" }, status: "todo" },
        { text: { en: "Export validated data and figures to the site", zh: "将通过验证的数据和图表导出到网站" }, status: "todo" }
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
