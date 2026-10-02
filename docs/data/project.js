// Project data for the hub page.
// Text fields are { en, zh }. A plain string is shown in both languages.
// To update progress: change a task's status to "todo", "doing" or "done",
// fill in owners, bump `updated`, then commit and push.

window.PROJECT = {
  updated: "2026-10-02",
  repo: "https://github.com/laozhongjie/abm-traffic-modeling",

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

  timelineStatus: { en: "Draft schedule, to be confirmed at kick-off.", zh: "以下为草拟的时间安排，将在 kick-off 时确认。" },
  timeline: [
    {
      start: "2026-10-01", end: "2026-10-07",
      title: { en: "Kick-off & literature survey", zh: "启动与文献调研" },
      items: [
        { en: "Read the project overview", zh: "阅读项目概览" },
        { en: "Survey traffic models, their variations and applications", zh: "调研交通模型及其变体和应用" },
        { en: "Set up Python, SUMO and the repository locally", zh: "在本地配置 Python、SUMO 和仓库" },
        { en: "Choose workstreams", zh: "选择工作方向" }
      ]
    },
    {
      start: "2026-10-08", end: "2026-10-14",
      title: { en: "Build & validate", zh: "搭建与验证" },
      items: [
        { en: "NaSch, OVM and IDM on the ring road, with validation checks", zh: "在环路上实现 NaSch、OVM 和 IDM，并完成验证检查" },
        { en: "Import an OSM district into SUMO; validate on a 4×4 grid", zh: "将一片 OSM 城区导入 SUMO，并用 4×4 网格验证" },
        { en: "Shared analysis script and congestion criteria", zh: "统一的分析脚本和拥堵判据" },
        { en: "Request PeMS / highD data access", zh: "申请 PeMS / highD 数据" }
      ]
    },
    {
      start: "2026-10-15", end: "2026-10-21",
      title: { en: "Stage 1 & 2 experiments", zh: "阶段一、二实验" },
      items: [
        { en: "Ring-road sweeps: density, system size, randomness, bottleneck", zh: "环路扫描：密度、系统尺寸、随机性、瓶颈" },
        { en: "Critical-point analysis for the highway", zh: "高速公路的临界点分析" },
        { en: "Network density sweeps and MFD", zh: "路网密度扫描与宏观基本图" },
        { en: "In-browser ring-road simulation on this site", zh: "在本网站实现浏览器内的环路模拟" }
      ]
    },
    {
      start: "2026-10-22", end: "2026-10-28",
      title: { en: "Stage 3 & figures", zh: "阶段三与图表" },
      note: { en: "Lighter week: course test on 24 Oct", zh: "任务较轻的一周：10月24日有课程测验" },
      items: [
        { en: "Planning scenarios: road closure, new link", zh: "规划场景：封路、新增道路" },
        { en: "Comparison with real traffic data", zh: "与真实交通数据对比" },
        { en: "Final figures for all stages", zh: "完成各阶段的最终图表" }
      ]
    },
    {
      start: "2026-10-29", end: "2026-11-01",
      title: { en: "Integrate results", zh: "整合结果" },
      items: [
        { en: "Freeze conclusions", zh: "确定结论" },
        { en: "Slide outline and first draft", zh: "幻灯片大纲与初稿" }
      ]
    },
    {
      start: "2026-11-02", end: "2026-11-05",
      title: { en: "Presentation", zh: "展示" },
      items: [
        { en: "Finish and rehearse slides (15 min + 3 min Q&A)", zh: "完成并排练幻灯片（15 分钟 + 3 分钟问答）" },
        { en: "Submit slides by 5 Nov, 6:00 pm", zh: "11月5日 18:00 前提交幻灯片" }
      ]
    },
    {
      start: "2026-11-06", end: "2026-11-15",
      title: { en: "Report drafting & peer grading", zh: "撰写报告与互评" },
      items: [
        { en: "Write the group report (at least 10 pages)", zh: "撰写小组报告（至少 10 页）" },
        { en: "Complete peer grading by 15 Nov", zh: "11月15日前完成互评" }
      ]
    },
    {
      start: "2026-11-16", end: "2026-11-22",
      title: { en: "Final submission", zh: "最终提交" },
      items: [
        { en: "Finalize report, data and code", zh: "完善报告、数据和代码" },
        { en: "Write individual reports", zh: "撰写个人报告" },
        { en: "Submit by 22 Nov, 11:59 pm", zh: "11月22日 23:59 前提交" }
      ]
    }
  ],

  // status: "todo" | "doing" | "done"; owner: null means not yet claimed.
  workstreams: [
    {
      name: { en: "Highway models", zh: "高速公路模型" },
      stage: { en: "Stage 1", zh: "阶段一" },
      owner: null,
      summary: {
        en: "Ring-road implementations of NaSch, OVM and IDM, and the Stage 1 experiments.",
        zh: "在环路上实现 NaSch、OVM 和 IDM，并完成阶段一实验。"
      },
      tasks: [
        { text: { en: "Implement NaSch on a ring road", zh: "在环路上实现 NaSch" }, status: "todo" },
        { text: { en: "Implement OVM and IDM on a ring road", zh: "在环路上实现 OVM 和 IDM" }, status: "todo" },
        { text: { en: "Validation checks: no overlaps, vehicle conservation, units", zh: "验证检查：车辆不重叠、车辆数守恒、单位正确" }, status: "todo" },
        { text: { en: "Sweeps: density, system size, randomness", zh: "扫描：密度、系统尺寸、随机性" }, status: "todo" },
        { text: { en: "Bottleneck runs: reduced-speed section, optional traffic light", zh: "瓶颈实验：限速路段，可选红绿灯" }, status: "todo" }
      ]
    },
    {
      name: { en: "City network", zh: "城市路网" },
      stage: { en: "Stages 2 & 3", zh: "阶段二、三" },
      owner: null,
      summary: {
        en: "SUMO network from OpenStreetMap, constant-density runs and planning scenarios.",
        zh: "基于 OpenStreetMap 的 SUMO 路网、恒定密度实验和规划场景。"
      },
      tasks: [
        { text: { en: "Choose a district and import it from OSM into SUMO", zh: "选定城区并从 OSM 导入 SUMO" }, status: "todo" },
        { text: { en: "Validate the pipeline on a 4×4 grid", zh: "用 4×4 网格验证整个流程" }, status: "todo" },
        { text: { en: "TraCI controller that keeps network density constant", zh: "用 TraCI 编写保持网络密度恒定的控制器" }, status: "todo" },
        { text: { en: "Network density sweeps", zh: "网络密度扫描" }, status: "todo" },
        { text: { en: "Planning scenarios: road closure, new link", zh: "规划场景：封路、新增道路" }, status: "todo" }
      ]
    },
    {
      name: { en: "Critical-point analysis & data", zh: "临界点分析与数据" },
      stage: { en: "All stages", zh: "全部阶段" },
      owner: null,
      summary: {
        en: "Congestion criteria, phase-transition analysis and comparison with real data.",
        zh: "拥堵判据、相变分析，以及与真实数据的对比。"
      },
      tasks: [
        { text: { en: "Define order parameter and congestion criteria", zh: "定义序参量和拥堵判据" }, status: "todo" },
        { text: { en: "Fundamental diagrams, fluctuations, finite-size analysis", zh: "基本图、涨落和有限尺寸分析" }, status: "todo" },
        { text: { en: "MFD and congested-cluster analysis with NetworkX", zh: "用 NetworkX 做宏观基本图和拥堵连通区域分析" }, status: "todo" },
        { text: { en: "Obtain PeMS / highD / LTA data", zh: "获取 PeMS / highD / LTA 数据" }, status: "todo" },
        { text: { en: "Compare simulated and real results", zh: "对比模拟结果与真实数据" }, status: "todo" }
      ]
    },
    {
      name: { en: "Web & visualization", zh: "网页与可视化" },
      stage: { en: "Site", zh: "网站" },
      owner: null,
      summary: {
        en: "This project site, then the interactive simulation environment.",
        zh: "先做项目主页，再做交互式模拟环境。"
      },
      tasks: [
        { text: { en: "Project hub page (this site)", zh: "项目主页（本网站）" }, status: "doing" },
        { text: { en: "In-browser ring-road simulation (NaSch / OVM / IDM)", zh: "浏览器内环路模拟（NaSch / OVM / IDM）" }, status: "todo" },
        { text: { en: "Linked charts: fundamental diagram, space–time diagram", zh: "联动图表：基本图、时空图" }, status: "todo" },
        { text: { en: "City-network view with link speeds and MFD", zh: "城市路网视图：路段速度和宏观基本图" }, status: "todo" },
        { text: { en: "Run SUMO from the page via the backend", zh: "网页调用后端运行 SUMO" }, status: "todo" }
      ]
    },
    {
      name: { en: "Integration, report & slides", zh: "整合、报告与展示" },
      stage: { en: "Deliverables", zh: "交付成果" },
      owner: null,
      summary: {
        en: "Literature survey, reproducibility, report and presentation.",
        zh: "文献综述、可复现性、报告和展示。"
      },
      tasks: [
        { text: { en: "Project overview (EN / ZH) and repository", zh: "项目概览（中英文）与仓库" }, status: "done" },
        { text: { en: "Literature survey: models, variations, applications", zh: "文献综述：模型、变体与应用" }, status: "todo" },
        { text: { en: "Experiment log: configs, seeds and outputs", zh: "实验记录：配置、随机种子和输出" }, status: "todo" },
        { text: { en: "Slides and rehearsal", zh: "幻灯片与排练" }, status: "todo" },
        { text: { en: "Group report and AI prompt appendix", zh: "小组报告及 AI prompt 附录" }, status: "todo" }
      ]
    }
  ],

  resources: [
    {
      group: { en: "Project documents", zh: "项目文档" },
      links: [
        { label: { en: "Project overview (English)", zh: "项目概览（英文）" }, url: "https://github.com/laozhongjie/abm-traffic-modeling/blob/main/Project_Overview_EN.md", note: { en: "Full description of questions, stages and methods", zh: "研究问题、实验阶段和方法的完整说明" } },
        { label: { en: "Project overview (Chinese)", zh: "项目概览（中文）" }, url: "https://github.com/laozhongjie/abm-traffic-modeling/blob/main/Project_Overview.md", note: { en: "Chinese version", zh: "中文版" } },
        { label: { en: "GitHub repository", zh: "GitHub 仓库" }, url: "https://github.com/laozhongjie/abm-traffic-modeling", note: { en: "Code, data and documents (private)", zh: "代码、数据和文档（私有）" } }
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
