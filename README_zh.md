# 道路网络交通拥堵的智能体建模

[English](README.md) | [中文](README_zh.md)

本项目将交通从自由流向拥堵的转变视为非平衡相变，先研究高速公路环形道路，再扩展到城市道路网络。

## 项目概览

- [英文版](Project_Overview_EN.md)
- [中文版](Project_Overview.md)

## 关键日期

| 日期 | 提交内容 |
|---|---|
| 11 月 5 日 18:00 | 汇报幻灯片（Canvas › People › Groups） |
| 11 月 15 日 23:59 | 同伴评分（Canvas Quiz） |
| 11 月 22 日 23:59 | 小组报告、数据和代码，以及个人报告 |

## 项目网站

[打开项目网站](https://laozhongjie.github.io/agent-based-traffic-modeling/)

网站支持中英文切换，展示项目概览、时间安排、进度和学习资料。点击首页的模型名称或方程卡片，可查看 NaSch、OVM 和 IDM 的详细介绍、交互图解及参考文献。

环路、城市路网和规划页面将在实验完成后逐步展示结果。当前原理演示用于理解模型行为，不代表正式实验结果。主页现在展示暂定的 A–E 主责方向、共享接口和交叉复核安排。

## 仓库目录

以下为目标目录结构。目前仓库已有项目概览、网站和第一个环路场景；其他目录在开始实现时按需添加。目录名称表示文件职责，不代表团队分工。

```text
.
├── README.md / README_zh.md
├── GUIDE.md / GUIDE_zh.md      # 实验手册 Markdown 版，内容与 docs/guide.html 一致
├── Project_Overview.md / Project_Overview_EN.md
├── environment.yml             # 可复现的 Python 环境
├── pyproject.toml              # 让 src/traffic_project 可以导入（pip install -e .）
├── .github/workflows/          # 网站部署及后续自动检查
├── research/                   # 决策记录和验证结果
├── sumo/
│   ├── version.txt             # 固定的上游 SUMO commit
│   ├── check_nasch.py          # 用 p = 0 的精确解检查 SUMO 的 NaSch
│   ├── ovm/                    # MSCFModel_OVM.h/.cpp 完整源文件及 check_ovm.py
│   └── patches/                # 在 SUMO 中注册 OVM 的少量改动
├── scenarios/                  # 固定不变的 SUMO 输入及其生成脚本
│   ├── ring/                   # 环路及瓶颈变体
│   ├── grid/                   # 验证流程的 4×4 网格
│   └── city/                   # 基准、封路和新增连接变体
├── configs/                    # 参数、扫描组合、种子和运行时长
│   ├── validation/
│   ├── ring/
│   ├── network/
│   └── planning/
├── src/traffic_project/        # 共用的模拟和分析代码
│   ├── config.py               # 读取实验配置（TOML）
│   ├── io.py                   # 读取 SUMO 输出，写结果表格
│   ├── runner.py               # SUMO/TraCI 运行与实验记录
│   ├── demand.py               # 目的地、路线及车辆数控制
│   ├── measurements.py         # 统一指标定义
│   ├── results.py              # 交给分析使用的结果数据格式
│   ├── nasch.py                # NaSch 在 p = 0 时的理论与参考元胞自动机
│   ├── ovm.py                  # OVM 理论与参考积分器
│   ├── analysis/               # 临界点、涨落及拥堵簇分析
│   └── export_web.py           # 导出精简网页数据
├── scripts/                    # 命令行入口
├── tests/                      # 模型、控制器和指标检查
├── data/                       # 外部数据，与实验输出分开
│   ├── raw/                    # OSM、PeMS、highD 或 LTA 原始数据（不进 git）
│   └── processed/              # 清洗后的外部数据
├── runs/                       # 每次运行一个目录：输入、记录、日志和输出（不进 git）
├── sandbox/                    # 个人试验代码（不进 git）
├── results/                    # 汇总统计和图表（进 git，保持精简）
├── reports/                    # 报告和幻灯片源文件
└── docs/                       # 发布的网站，保留现有结构
    ├── index.html
    ├── guide.html              # 实验手册（全组共用规范）
    ├── assets/                 # 共用样式、脚本和原理演示
    ├── models/                 # NaSch、OVM 和 IDM 介绍
    ├── lab/                    # 环路、路网和规划结果页面
    └── data/
        ├── project.js          # 网站时间安排和进度
        ├── ring/               # 环路实验导出结果
        ├── network/            # 路网实验导出结果
        └── planning/           # 规划实验导出对照
```

- `scenarios/` 只放各次运行共用、固定不变的输入（路网、信号方案）及生成它们的脚本。为某一次运行生成的文件（车辆初始位置、`.sumocfg`、输出）一律放进 `runs/<run-id>/`。`configs/` 定义实验组合。环路上的三种模型共用运行和分析流程。
- `runs/<run-id>/` 保存本次运行的完整配置、随机种子、项目与 SUMO 版本、场景标识、验证结果、日志和输出。`results/` 汇总这些运行；每个发布的数据点应保留来源运行编号。
- git 跟踪代码、场景、配置、`results/` 和 `docs/`，不跟踪 `runs/` 和 `data/raw/`（见 `.gitignore`）。大文件通过外部存储共享，并记录获取方式。
- `docs/data/` 存放由有效实验结果生成的精简数据。GitHub Pages 会发布整个 `docs/`，完整轨迹、私有数据和实验输入应保存在该目录之外。
- 实验手册 `docs/guide.html` 是全组做实验的唯一依据（单位、运行编号、目录、检查项）；`GUIDE.md`（英文）和 `GUIDE_zh.md`（中文）是内容相同的 Markdown 版。`research/` 记录这些决定的由来和验证结果。
- 上游 SUMO 源码和编译目录放在仓库之外。`sumo/version.txt` 记录版本，`sumo/ovm/` 保存 OVM 新增的源文件，`sumo/patches/` 保存对 SUMO 原有文件的改动。

## 实验工作流程

1. 确定实验协议和配置：单位、模型参数、密度网格、种子、初态、预热与观测时长，以及拥堵判据。固定包含 OVM 的 SUMO 构建。
2. 通过命令行验证：NaSch 对照确定性解析结果，OVM 对照稳定性预测，城市控制器先在 4×4 网格验证。检查车辆数、非负速度和车辆重叠。
3. 通过命令行批量运行 SUMO：先做环路比较，再做城市路网密度扫描，最后比较规划方案。规划实验沿用基准的密度网格和种子组，并记录各方案的车道总长度与车辆数。
4. 按运行编号保存输出，检查有效性并保留失败诊断。排除预热段后计算统计量，汇总重复运行，在候选临界区间附近加密密度取点。
5. 生成报告图表，同时将对应精简数据导出到 `docs/data/ring/`、`docs/data/network/` 和 `docs/data/planning/`。
6. 检查网页展示与导出结果一致，再提交并推送。结果页控件用于选择已有计算组合或回放时刻；新参数组合需要重新通过命令行运行并导出。浏览器原理演示用于教学说明。

环路实验的命令行工具已按此流程实现，具体命令和新增实验的方法见 `docs/guide.html`。其他场景的工具尚待实现。
