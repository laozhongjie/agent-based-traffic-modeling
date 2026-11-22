# 道路网络交通拥堵的智能体建模

[English](README.md) | [中文](README_zh.md)

新加坡国立大学 PC5253 课程期末项目。我们把交通拥堵的出现看作非平衡相变，从单车道环形道路出发，扩展到新加坡武吉士（Bugis）片区的道路网络，再研究该路网的规划改动。所有模拟都是基于智能体的，在 [SUMO](https://eclipse.dev/sumo/) 中运行，使用三种跟驰模型：Nagel–Schreckenberg（NaSch）、优化速度模型（OVM，由我们用 C++ 实现）和智能驾驶模型（IDM）。

**[项目网站](https://laozhongjie.github.io/agent-based-traffic-modeling/)**：模型的交互式讲解，以及环路、城市路网和规划情景的全部结果，提供中英文两种语言。

## 研究问题

1. **高速公路。** 没有信号灯的道路上，临界密度是多少？这一转变是否表现得像相变？它如何依赖于模型、随机性和系统尺寸？是否与真实高速公路数据相符？
2. **城市路网。** 城市路网是否存在一个密度，使总通行量先达到峰值然后下降？局部拥堵是否会合并成大片拥堵区域？路网结构如何决定拥堵从哪里开始？
3. **规划。** 封路或新建道路会提高还是降低路网的临界密度和最大流量？新增一条路会不会让交通更糟（Braess 悖论）？

## 主要结果

- **环形道路。** 密度超过临界值后，自由流会演变为向后传播的走走停停波。临界密度约为 20–25 veh/km（NaSch）、25 veh/km（OVM）和 30–35 veh/km（IDM），在 600 到 4800 m 的环路长度范围内看不出差别。线性稳定性分析给出的 IDM 阈值为 32.9 veh/km。随机性越小、驾驶员反应越快，拥堵越晚出现。真实高速公路数据（PeMS）的流量峰值出现在每车道 19–21 veh/km，并显示出迟滞迹象。
- **城市路网。** Bugis 路网的平均速度在每车道 13.3 veh/km 时减半，流量则在每车道约 171 veh/h 处趋于平稳。涨落和恢复时间在该密度处都没有峰值，因此这是平滑过渡，而不是临界点。局部拥堵在 20 到 25 veh/km 之间合并成一个大团簇；控制交通负载后，边介数几乎无法预测拥堵从哪里开始。
- **规划。** 封闭最中心的可封闭路段，使临界密度下降 0.45 veh/km（3.4%）。车道缩减和新建道路带来的变化都小于不同随机种子之间的差异，没有发现全网范围的 Braess 悖论。

## 团队

| 成员 | 主要工作 |
|---|---|
| Lao Zhongjie（A） | 项目负责人：研究方案、共享框架与实验流程、SUMO 构建与 OVM 实现、模型验证、项目网站 |
| Foo Guowei（B） | 车辆模型；环形道路实验 |
| Lim Yixiang（C） | 城市路网：MFD、拥堵团簇、扩散与临界点分析；LTA 数据 |
| Cheong Zihao Daniel（D） | 规划情景与 Braess 检验 |
| Shen Hongfang（E） | IDM 平衡态与线性稳定性；PeMS 高速公路数据分析；讨论 |

## 仓库结构

```text
.
├── sumo/                 # 固定的 SUMO 版本、OVM 源文件、补丁和验证脚本
├── src/traffic_project/  # 共享 Python 包：配置、运行、测量、密度控制器
├── configs/              # 每个实验一个 TOML 文件（参数、密度、随机种子）
├── scenarios/            # 环路、网格和 Bugis 路网，以及生成它们的脚本
├── scripts/              # 扫描、分析和作图的命令行入口
├── results/              # 所有有效运行的汇总表、时间序列和图
├── data/processed/       # 处理后的外部数据（LTA 速度带）
├── notebooks/            # 组员的分析 notebook
├── tests/                # 自动化测试（pytest）
└── docs/                 # 项目网站（GitHub Pages）
```

运行目录（`runs/`）和原始数据体积较大，没有纳入 Git。`results/` 中的每一行都记录了来源运行的 ID，每次运行都可以用对应的配置文件和随机种子复现。共享约定（单位、运行 ID、检查）见 [GUIDE_zh.md](GUIDE_zh.md)。

## 复现结果

```bash
conda env create -f environment.yml
conda activate traffic
```

NaSch 和 IDM 只需要官方 SUMO 1.28.0。C++ 版 OVM 需要用 `sumo/ovm/` 中的文件和 `sumo/patches/register-ovm.patch` 构建 SUMO 1.28.0（见 `sumo/version.txt`）。

```bash
# 模型验证
python sumo/check_nasch.py
python sumo/ovm/check_ovm.py
pytest

# 城市路网
python scripts/city_sweep.py    --config configs/city/bugis_all_controller.toml
python scripts/city_measures.py --config configs/city/bugis_all_controller.toml

# 规划情景（先分别运行各个 bugis_all_<variant>_controller.toml）
python scripts/planning_figures.py \
    --extra base=bugis_all_base_controller_seeds4to10 \
    --extra newlink=bugis_all_newlink_controller_seeds4to10
```

环形道路的扫描在分支 `gw/self-experiment` 上，IDM 稳定性和 PeMS 的 notebook 在分支 `add-critical-density-analysis` 上。完整命令见报告附录。

## 数据来源

- 道路网络：© [OpenStreetMap](https://www.openstreetmap.org/copyright) 贡献者，ODbL 许可。
- 新加坡速度带：包含来自 LTA DataMall 的 Traffic Speed Bands 信息，依据[新加坡开放数据许可 1.0](https://data.gov.sg/open-data-licence) 提供。
- 高速公路检测器数据：加州交通局性能测量系统（PeMS）。
