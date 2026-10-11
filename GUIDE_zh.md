# 实验手册

[English](GUIDE.md) | [中文](GUIDE_zh.md)

本文件是网页版实验手册 [`docs/guide.html`](docs/guide.html) 的 Markdown 版本，内容与网页一致，可以离线阅读，也可以直接发给 AI 作为上下文。英文版见 [`GUIDE.md`](GUIDE.md)。三处内容必须同步：修改任何规定时，在同一个 PR 中同时更新网页和两个 Markdown 文件。

本手册是全组做实验的唯一依据：怎样安装 SUMO、代码和文件放在哪里、怎样搭建一个新实验、运行怎样命名和检查，以及代码怎样合并到主分支。仓库里的环路示例遵守本手册的每一条规定，可以直接作为模板。

项目背景：本项目用 SUMO 研究交通从自由流到拥堵的转变（视为非平衡相变），先在单车道环路上比较 NaSch、OVM 和 IDM 三种模型，再扩展到城市路网和规划方案。成员用字母 A–E 表示。

标有 **（待确定）** 的事项仍需全组商定。本手册由 A 维护；要修改某项做法，先在组会上提出，再按新做法执行。

## 目录

1. [安装 SUMO 和 Python](#1-安装-sumo-和-python)
2. [代码和文件放在哪里](#2-代码和文件放在哪里)
3. [运行环路示例](#3-运行环路示例)
4. [搭建一个新实验](#4-搭建一个新实验)
5. [运行编号和运行记录](#5-运行编号和运行记录)
6. [结果数据格式](#6-结果数据格式)
7. [每次运行必须通过的检查](#7-每次运行必须通过的检查)
8. [单位和测量方法](#8-单位和测量方法)
9. [待确定事项](#9-待确定事项)
10. [用 Git 协作](#10-用-git-协作)

## 1. 安装 SUMO 和 Python

使用 SUMO 正式版 **1.28.0**，其中已包含 IDM 和 NaSch。OVM 由本项目自行加入，所以 OVM 的运行和正式实验使用 A 编译的版本：同为 1.28.0，另加入了 OVM。其余工作用正式版就够了：熟悉流程、开发场景、运行 IDM 和 NaSch。

1. 按 [SUMO 安装说明](https://sumo.dlr.de/docs/Installing/index.html) 安装适合自己系统的 SUMO 1.28.0。如果之前装的是 1.27.1，用同样的方法安装 1.28.0，再按第 3 步检查。
2. 设置 `SUMO_HOME`，并把 SUMO 的 `bin` 目录加入 `PATH`：
   - **Windows：** `.msi` 安装包会自动设置这两项。安装后关闭并重新打开终端。
   - **macOS：** 安装包不会设置这两项。在终端运行下面三行，它们会把两项设置追加到 `~/.zshrc` 末尾并立即生效：

     ```bash
     echo 'export SUMO_HOME="/Library/Frameworks/EclipseSUMO.framework/Versions/Current/EclipseSUMO/share/sumo"' >> ~/.zshrc
     echo 'export PATH="/Library/Frameworks/EclipseSUMO.framework/Versions/Current/EclipseSUMO/bin:$PATH"' >> ~/.zshrc
     source ~/.zshrc
     ```

   - **Linux：** 在终端运行下面两行。在 Ubuntu 上用 apt 安装时，路径通常是 `/usr/share/sumo`，而且程序已经在 `PATH` 中。

     ```bash
     echo 'export SUMO_HOME="/usr/share/sumo"' >> ~/.bashrc
     source ~/.bashrc
     ```

3. 检查安装结果。输出的第一行应为 `Eclipse SUMO sumo 1.28.0`。

   ```bash
   sumo --version
   ```

4. **可选：** `sumo-gui` 用窗口显示仿真过程，可以看到车辆怎样移动、拥堵在哪里形成，适合用来检查新搭建的场景是否正确。做实验不需要它：除了第 3 节中一个可选步骤，本手册的所有命令都不打开窗口。在 Windows 上，安装 SUMO 后即可使用 `sumo-gui`。在 macOS 上需要先安装 XQuartz（用下面的 Homebrew 命令，或从 [xquartz.org](https://www.xquartz.org/) 下载），再注销并重新登录。没有 XQuartz 时，`sumo-gui` 会报错 `unable to open display`。`sumo-gui` 输出的 `Fontconfig warning` 不影响运行。

   ```bash
   brew install --cask xquartz
   ```

5. 在仓库根目录创建全组共用的 Python 环境，只需做一次。这一步会安装固定版本的 Python 和软件包，并安装 `src/traffic_project` 中的项目代码，让所有脚本都能导入它。

   ```bash
   conda env create -f environment.yml
   ```

   如果你的环境是在 10 月 9 日之前创建的（之后加入了 pandas、JupyterLab 和 pytest），改为运行下面的命令更新：

   ```bash
   conda env update -f environment.yml --prune
   ```

6. 每次打开新终端，运行项目命令前先激活环境：

   ```bash
   conda activate traffic
   ```

## 2. 代码和文件放在哪里

代码按功能存放，不按作者存放。每一类代码只有一个位置和一个负责人。

| 位置 | 存放内容 | 负责人 |
| --- | --- | --- |
| `scenarios/ring/` | 环路路网文件（`ring_<长度>.net.xml` 及其源文件）、生成路网的 `build_net.py`，以及为一次运行摆放车辆的 `build_run.py` | B |
| `scenarios/grid/` | 4×4 测试网格的路网文件和生成脚本；在网格上试做的规划方案 | D |
| `scenarios/city/` | 由 OSM 数据转换的城区路网文件；封路、新增道路后的路网版本 | C；D |
| `configs/<scenario>/` | 每个实验一个 TOML 文件，写明全部参数 | 场景负责人 |
| `scripts/` | 命令行入口，每个任务一个：`<scenario>_sweep.py`、`plot_<scenario>.py` | 场景负责人 |
| `src/traffic_project/` 中的 `config.py`、`io.py`、`runner.py` | 读取配置、读取 SUMO 输出、运行 SUMO、写运行记录、通用检查 | A |
| `src/traffic_project/results.py` | 结果数据格式（第 6 节）：必需列、检查和写出函数 | A |
| `src/traffic_project/export_web.py`、`scripts/export_web.py` | 把通过检查的结果导出到网站（第 3 节第 6 步） | A |
| `src/traffic_project/nasch.py` | NaSch 在 $p = 0$ 时的理论结果和参考元胞自动机 | A |
| `src/traffic_project/ovm.py` | OVM 理论：最优速度、均匀流的稳定性、参考积分器 | A |
| `sumo/` | 包含 OVM 的 SUMO 构建：版本、OVM 源码、补丁，以及检查脚本 `sumo/check_nasch.py` 和 `sumo/ovm/check_ovm.py` | A |
| `tests/` | 共用代码的自动测试，用 `pytest` 运行 | A |
| `src/traffic_project/measurements.py` | 测量量，每个场景一个函数 | A；环路 B；路网 C |
| `src/traffic_project/demand.py` | 城区路网的恒定密度 TraCI 控制器（尚未建立） | C |
| `src/traffic_project/analysis/` | 临界点、涨落和误差范围（尚未建立） | E |
| `results/<scenario>/` | 汇总多次运行的表格和图表，文件保持精简 | 场景负责人 |
| `data/raw/`、`data/processed/` | 外部数据：OSM、PeMS、highD、LTA | E |
| `runs/<run-id>/` | 每次运行一个目录，由脚本写出，不手工修改 | — |
| `sandbox/<your-name>/` | 个人试验代码和 notebook | 本人 |
| `docs/data/<scenario>/` | 导出到网站的结果，由 `scripts/export_web.py` 写出，不手工修改 | — |
| `docs/` | 项目网站 | A |

### `scenarios/` 中的路网文件

SUMO 的路网由几个 XML 文本文件组成：

| 文件 | 内容 |
| --- | --- |
| `<名称>.nod.xml` | 节点（路口）：编号和 x、y 坐标（m）。由脚本或手工编写。 |
| `<名称>.edg.xml` | 边（路段）：从哪个节点到哪个节点、车道数、限速（m/s）、长度（m）和形状。由脚本或手工编写。 |
| `<名称>.net.xml` | SUMO 运行时读取的完整路网：车道、路口、车道之间的连接和红绿灯。由 `netconvert` 或 `netgenerate` 生成，不手工修改。 |

例如，`ring_1000.nod.xml` 中的一个节点和 `ring_1000.edg.xml` 中的一条边：

```xml
<node id="n0" x="159.155" y="0.000" type="priority"/>
<edge id="e0" from="n0" to="n1" numLanes="1" speed="30.0" length="250.000" shape="…"/>
```

三个场景的路网来源不同：

- **环路：** `build_net.py` 写出 `.nod.xml` 和 `.edg.xml`，再调用 `netconvert` 生成 `ring_<长度>.net.xml`。
- **4×4 网格**（计划）：可以用 SUMO 自带的 `netgenerate --grid` 直接生成 `.net.xml`，具体做法由 D 确定。
- **城区**（计划）：OpenStreetMap 原始数据（`.osm` 文件）存放在 `data/raw/`。`netconvert --osm-files` 把它转换成 `.net.xml`，存放在 `scenarios/city/`。D 的每个规划方案（如封路、新增道路）都是在它基础上修改出的另一个 `.net.xml`。

车辆和路线不属于路网。它们每次运行都不同，由场景脚本写进 `runs/<run-id>/vehicles.rou.xml`。

git 忽略 `runs/`、`data/raw/`、`sandbox/` 和所有 `*.fcd.xml`，表中其他内容都提交到 git。

### 规定

1. **不复制共用代码。** 运行 SUMO、读取输出、写运行记录时，一律导入 `traffic_project`。缺少某项功能时，告诉 A，或提交一个 PR 把它加到共用代码中。
2. **参数不写在代码里。** 模型参数、密度、种子和时长全部写在 `configs/` 中该实验的 TOML 文件里。
3. **一个实验对应一个配置文件和一条命令。** 任何人从干净的 commit 出发都能复现。
4. **`sandbox/` 中的代码不得产出正式结果。** 结果写进报告或放上网站前，先把代码移到上表规定的位置。
5. **每个脚本开头写文档字符串**，说明用途和运行方法。
6. **notebook 用来探索和画图，不用来跑正式实验。** notebook 放在 `sandbox/<你的名字>/` 中；这个文件夹不进 git，notebook 只保存在你自己的电脑上。读取结果用 `load_summary` 和 `load_timeseries`（见第 6 节），像脚本一样导入 `traffic_project`。正式实验一律用配置文件加 `scripts/` 中的脚本运行，保证每个结果都有运行记录。notebook 里的分析或图要写进报告时，把代码移到 `scripts/` 或 `src/traffic_project/analysis/`（规则 4）。

## 3. 运行环路示例

所有命令都在仓库根目录、激活 `traffic` 环境后运行。示例在长度 1000 m 的单车道环路上运行 IDM，全部参数写在 `configs/ring/idm_sweep.toml` 中。

1. 生成环路路网。命令会写出 `scenarios/ring/ring_1000.net.xml`，该文件已在 git 中。

   ```bash
   python scenarios/ring/build_net.py --length 1000
   ```

2. 生成一次运行的输入：30 辆车，种子 1。命令会创建 `runs/ring_idm_L1000_n30_s1/`。

   ```bash
   python scenarios/ring/build_run.py --config configs/ring/idm_sweep.toml --vehicles 30 --seed 1
   ```

3. 运行 SUMO。以下两条命令任选其一：
   - 只运行，不打开窗口：

     ```bash
     sumo -c runs/ring_idm_L1000_n30_s1/run.sumocfg
     ```

   - 在 `sumo-gui` 中观看。保留 `--delay 100`：不加这个参数时，1800 秒的仿真不到 1 秒就会结束，看不到任何画面。

     ```bash
     sumo-gui -c runs/ring_idm_L1000_n30_s1/run.sumocfg --delay 100 --start
     ```

4. 运行配置文件中的全部扫描。脚本对每次运行依次生成输入、运行 SUMO、执行第 7 节的检查并写出运行记录，最后写出 `results/ring/idm_sweep.csv`。

   ```bash
   python scripts/ring_sweep.py --config configs/ring/idm_sweep.toml
   ```

5. 把基本图和时空图画到 `results/ring/`。

   ```bash
   python scripts/plot_ring.py --config configs/ring/idm_sweep.toml
   ```

6. 把通过检查的运行导出到网站。命令会写出 `docs/data/ring/idm_sweep.js`，其中包含每次运行的配置哈希值、SUMO 版本和 git commit。运行来自未提交的代码，或运行之后配置文件改动过时，命令会报错停止；加 `--allow-dirty` 可以写出供预览的草稿。导出要读取 `runs/` 中的运行记录，所以在运行扫描的那台电脑上执行。

   ```bash
   python scripts/export_web.py --config configs/ring/idm_sweep.toml
   ```

**预期结果：** 密度为 30 veh/km 时，平均速度为 16.6 m/s，与该间距下的 IDM 平衡速度一致。流量在 30 veh/km 附近达到峰值。约 40 到 80 veh/km 之间出现走走停停的拥堵波；100 veh/km 以上是均匀的慢速车流。结果不一致时，先检查 SUMO 版本。

## 4. 搭建一个新实验

每个实验都按以下步骤进行，包括在已有实验基础上改动参数。可以复制环路示例中对应的文件作为起点。

1. **新建分支**（见第 10 节）。
2. **编写配置文件** `configs/<scenario>/<name>.toml`。以 `configs/ring/idm_sweep.toml` 为起点。顶层的 `name`、`scenario` 和 `model` 必须填写；`name` 同时决定结果文件的名称。每个数字都用注释写明单位。
3. **生成场景输入。** 在 `scenarios/<scenario>/` 中编写脚本，参照 `scenarios/ring/build_run.py`。脚本读取配置文件，为每次运行写出一个 `runs/<run-id>/` 目录并输出运行编号。写出的 `.sumocfg` 使用相对路径，把 `time-to-teleport` 设为 `-1`，把 `collision.action` 设为 `warn`。
4. **添加测量函数。** 在 `src/traffic_project/measurements.py` 中加一个函数，参照 `ring_summary`。函数读取一次运行的输出，按第 6 节的格式返回 `(measurements, checks, timeseries)`。这一步修改了共用代码，PR 必须由 A 批准。
5. **编写入口脚本** `scripts/<scenario>_sweep.py`，参照 `scripts/ring_sweep.py`。脚本接受 `--config` 参数，按扫描逐次运行，使用下方的共用调用，并用 `results.write_summary` 和 `results.write_timeseries` 写出汇总表和时间序列。
6. **运行并检查输出。** 每次运行都会输出 `ok`，或输出 `INVALID` 和未通过的检查项。先排除每次无效运行的原因，再使用结果。
7. **画图**：用 `scripts/plot_<scenario>.py --config …` 把图表写到 `results/<scenario>/`。
8. **提交**：把配置文件、代码和结果一起提交，然后发起 PR。

每个入口脚本都使用以下共用调用。下面只是结构示意，不能直接运行：

```python
from traffic_project import config, measurements, results, runner

cfg = config.load(args.config)
for each run in the sweep:
    run_id, run_dir = …                      # from scenarios/<scenario>/build_*.py
    runner.write_manifest(run_dir, run_id, cfg, parameters)
    _, checks = runner.run_sumo(run_dir)
    measured, more_checks, series = measurements.<scenario>_summary(…)
    results.write_timeseries(run_id, series, cfg)
    row = dict(measured, scenario=…, model=…, variant=…, seed=…)
    rows.append(runner.finish(run_dir, run_id, row, {**checks, **more_checks}))
results.write_summary(rows, cfg)
```

在运行过程中改变仿真的场景（例如城市路网的恒定密度控制器）用 `runner.run_traci(run_dir, controller)` 代替 `runner.run_sumo(run_dir)`。SUMO 会逐步推进，每一步之后调用 `controller(conn, time_s)`，其中 `conn` 是 TraCI 连接，例如 `conn.vehicle.add`、`conn.vehicle.remove`。它写出同样的 `log.txt`，返回同样的检查结果。该运行的 `.sumocfg` 必须设置结束时间。

## 5. 运行编号和运行记录

运行编号依次写出场景、模型、变化的参数和种子，用下划线连接，不含空格。环路示例的编号是 `ring_idm_L1000_n30_s1`：环路、IDM、长度 1000 m、30 辆车、种子 1。其他场景的负责人按同样的方式命名，并把格式补充到本节。

| `runs/<run-id>/` 中的文件 | 内容 |
| --- | --- |
| `run.sumocfg` | SUMO 运行配置：路网、路线、时长、步长、种子和输出。路径都是相对路径，换一台电脑也能运行。 |
| `vehicles.rou.xml` | 车型及其模型参数、路线和初始位置 |
| `fcd.xml` | 每辆车在每个时间步的位置和速度，文件较大 |
| `log.txt` | SUMO 的运行信息，用于碰撞和瞬移检查 |
| `manifest.json` | 运行编号、场景、模型、配置文件及其哈希值、全部参数、SUMO 版本、git commit 和生成时间 |
| `summary.json` | 测量结果和每项检查的结果，`valid` 为 true 或 false |

报告和网站上的每个数字都要保留来源运行编号。配置文件的哈希值可以说明运行之后配置文件是否改动过。git commit 以 `-dirty` 结尾，表示运行时代码有未提交的修改；正式结果必须来自干净的 commit。

## 6. 结果数据格式

E 用同一套脚本分析所有实验，所以 B、C、D 必须按同一格式写出结果。`runs/` 不进 git，E 需要的数据必须全部放在 `results/<scenario>/` 下的两类文件中。两类文件都由 `traffic_project.results` 写出；缺少某列、数值超出范围或附加列缺少前缀时，它会报错并停止。

### 汇总表：`results/<scenario>/<name>.csv`

每次运行一行。所有场景都必须包含以下各列，列名和单位不得改动：

| 列 | 含义 | 单位 |
| --- | --- | --- |
| `run_id` | 运行编号 | — |
| `scenario`、`model` | 场景和模型，与配置文件一致 | — |
| `variant` | 规划方案，如基准、封路、新增道路；没有方案时留空 | — |
| `seed` | 随机种子 | — |
| `density_veh_km` | 密度 $k$：车辆数 ÷ 车道总长度 | veh/km |
| `mean_speed_mps` | 空间平均速度 $\bar v$，在测量时段内取平均 | m/s |
| `flow_veh_h` | 流量 $q = k\,\bar v$ | veh/h |
| `congested_fraction` | 拥堵车辆比例 $\phi$，判据由各场景自行定义 | — |
| `congested_fraction_var` | $\phi$ 随时间的方差，即涨落 $\chi$ | — |
| `valid` | 通过第 7 节全部检查时为 `True` | — |

场景特有的列排在这些列之后，并以场景名开头，例如 `ring_vehicles`、`city_largest_cluster`。

### 时间序列：`results/<scenario>/<name>/<run_id>.csv`

每次运行一个文件。覆盖整个运行过程（包括预热段），每 10 秒记录一行瞬时值，列为 `time_s`、`density_veh_km`、`mean_speed_mps`、`flow_veh_h` 和 `congested_fraction`。E 用它检查预热时长是否足够，并估计涨落和误差范围。一次 1800 秒的运行约 8 KB。

环路和城市路网使用相同的定义，所以 E 可以直接比较 highway 和路网的临界密度。

### 在 Python 或 notebook 中读取结果

两种文件都能读成 pandas 表格，在任何文件夹下都能用；数字读出来就是数字，`valid` 是 `True`/`False`：

```python
from traffic_project.results import load_summary, load_timeseries

df = load_summary("ring", "idm_sweep")                               # 每次运行一行
ts = load_timeseries("ring", "idm_sweep", "ring_idm_L1000_n50_s1")   # 单次运行的时间序列
df = df[df.valid]                                                     # 只保留通过全部检查的运行
```

## 7. 每次运行必须通过的检查

有几类问题会悄悄改变实验，SUMO 却不会因此停止运行。所以每次运行都把下列检查结果写入 `summary.json`。前三项由 `runner.run_sumo` 检查，其余由场景的测量函数检查。无效的运行保留下来用于排查，但不得进入任何表格和图表。

| 检查项 | 发现什么问题 |
| --- | --- |
| `sumo_exit_ok` | SUMO 因错误而停止 |
| `no_teleport` | SUMO 默认会把等待超过 300 秒的车移走，再放到前方。每次运行都把 `time-to-teleport` 设为 `-1`，关闭这一行为。 |
| `no_collision` | 车辆重叠。每次运行都把 `collision.action` 设为 `warn`，让碰撞记录在日志中。 |
| `all_vehicles_present` | 车辆初始位置离其他车太近时，SUMO 会推迟插入这辆车，并且不报错。此时车辆数和密度都是错的。在环路上，`build_run.py` 还会直接拒绝放不下的车辆数。 |
| `no_negative_speed` | 模型错误，尤其是新写的 OVM 代码 |

环路还要遵守两条规则。每条边都显式设置 `length`，并用 `--no-internal-links` 生成路网，保证密度严格等于车辆数 ÷ 环路长度。模型有已知结果时，用它核对仿真：IDM 平衡速度、NaSch 在 $p = 0$ 时的结果、OVM 稳定性条件。NaSch 只有在格点上才能得到 $p = 0$ 的结果：环路长度是 7.5 m 格子的整数倍，车辆初始位置是 7.5 m 的整数倍，`speedDev` 为 0，`maxSpeed` 是 7.5 m/s 的整数倍且不超过路段限速。

## 8. 单位和测量方法

| 物理量 | 单位和规则 |
| --- | --- |
| 时间 | s；当前示例的步长为 1 s **（待确定）** |
| 长度、位置 | m |
| 速度 | 文件中一律用 m/s；只在正文和图表标签中使用 km/h |
| 密度 $k$ | veh/km |
| 流量 $q$ | veh/h |
| 预热 | 舍弃前 600 s，测量使用 600–1800 s 的数据 **（待确定）** |

在环路上，平均速度 $\bar v$ 是每个时间步所有车辆速度的平均值，再在测量时段内取时间平均。环路上没有车辆进出，所以流量为 $q = k\,\bar v$。拥堵车辆比例 $\phi$ 是速度低于阈值的车辆所占比例，它随时间的方差即涨落 $\chi$。城市路网的测量方法由 C 按同样的方式定义。

## 9. 待确定事项

- **IDM 参数**（B 牵头，全组商定）。示例使用的是暂定值：加速度 1.0 m/s²、舒适减速度 1.5 m/s²、车头时距 1.5 s、最小间距 2 m、最高速度 30 m/s、车长 5 m。
- **环路拥堵判据**（B）。暂定判据「速度低于 5 m/s」会把 100 veh/km 以上均匀的慢速车流判为完全拥堵，而这时并没有走走停停的拥堵波。新判据必须能区分这两种状态。
- **路网拥堵判据**（C）。
- **密度取值和每个密度的种子数**（B、C 与 E 商定），供 E 估计误差范围。
- **连续模型的步长和预热时长**。
- **哪些运行保留 `fcd.xml`。** 30 辆车运行 1800 秒约产生 7 MB，完整扫描只应为代表性运行保留轨迹。
- **时间序列的取样间隔**（E）。示例使用 10 秒。

## 10. 用 Git 协作

任何人都不直接推送到 `main`。所有改动都通过 Pull Request（PR）合并到 `main`。**PR 由任意一位其他成员批准即可；改动 `src/traffic_project/` 的 PR 必须由 A 批准**，A 自己发起的除外，由任意一位其他成员批准。

1. 从最新的 `main` 开始：

   ```bash
   git switch main
   git pull
   ```

2. 新建分支，命名为 `<成员字母>/<内容>`，例如：

   ```bash
   git switch -c b/ring-bottleneck
   ```

3. 提交改动，提交说明写清改了什么。
4. 推送分支：

   ```bash
   git push -u origin b/ring-bottleneck
   ```

5. 在 GitHub 上发起合并到 `main` 的 PR，请另一位成员审核。获得批准后再合并。

### 发起 PR 前

1. 确认 `git status` 中没有 `runs/`、`data/raw/` 或 `sandbox/` 下的文件。
2. 把配置文件、代码和 `results/` 一起提交，保证结果始终对应产生它的代码。
3. 结果写进报告或放上网站前，先从干净的 commit 重新运行一次。
4. 在仓库根目录运行 `pytest`，确认所有测试通过；没有安装 SUMO 时，需要 SUMO 的测试会被跳过。修改 `src/traffic_project/` 时，在 `tests/` 中为改动补充测试。
5. 如果修改了本手册中的某项规定，在同一个 PR 中同时更新网页 `docs/guide.html`（含 `docs/assets/guide-i18n.js`）、`GUIDE.md` 和 `GUIDE_zh.md`。
