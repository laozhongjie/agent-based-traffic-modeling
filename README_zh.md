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

访问任意页面时，输入公用密码 `pc5253` 或 `PC5253`。当前浏览器标签页会记住验证状态，直到标签页关闭。这是用于限制普通访问的前端密码入口：GitHub Pages 仍公开提供静态文件，密码和页面内容可以被查看，验证也可以被绕过。请勿用它保护敏感内容。

项目网站的概览、时间线和进度页面位于 [`docs/`](docs/)。[GitHub Pages 工作流](.github/workflows/pages.yml) 会在每次推送到 `main` 后自动部署 `docs/`，也可以从仓库的 Actions 页面手动运行。后续的交互式仿真环境将加入同一网站。

网站支持中英文切换。更新时间线或进度时，编辑 [`docs/data/project.js`](docs/data/project.js)：将各任务的 `status` 设为 `todo`（待开始）、`doing`（进行中）或 `done`（已完成），填写各工作方向的 `owner`，更新 `updated`，然后提交并推送。其中的文本字段使用 `{ en, zh }` 结构；页面固定文案的译文位于 [`docs/assets/i18n.js`](docs/assets/i18n.js)。

实验页面位于 [`docs/lab/`](docs/lab/)，包括 `ring.html`、`network.html` 和 `planning.html`。目前这些页面仅预留布局，后续将填入预先计算的 SUMO 结果。

[NaSch](docs/models/nasch.html)、[OVM](docs/models/ovm.html) 和 [IDM](docs/models/idm.html) 的详细双语介绍位于 [`docs/models/`](docs/models/)。在首页的车辆模型表格中点击模型名称即可打开，内容包括方程、参数、拥堵机制和适用限制，并附有原始论文链接。

公式使用 KaTeX 渲染。在 HTML、`i18n.js` 或 `project.js` 中，使用 `\( ... \)` 表示行内公式，使用 `\[ ... \]` 表示独立公式。JavaScript 字符串中的反斜杠需要转义，例如 `"\\(p = 0\\)"`。共用的语言切换和公式渲染逻辑位于 [`docs/assets/common.js`](docs/assets/common.js)。

本地预览时，在 `docs/` 目录中运行 `python3 -m http.server 8000`，然后打开 http://127.0.0.1:8000/。
