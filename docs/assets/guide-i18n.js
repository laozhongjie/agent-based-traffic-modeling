Object.assign(window.I18N.static.zh, {
  "guide.meta": "实验手册 · 交通建模",
  "guide.nav": "实验手册页面",
  "guide.tag": "全组共用 · 第一次运行前请读",
  "guide.title": "实验手册",
  "guide.lede": "本手册是全组做实验的唯一依据：怎样安装 SUMO、代码和文件放在哪里、怎样搭建一个新实验、运行怎样命名和检查，以及代码怎样合并到主分支。仓库里的环路示例遵守本页的每一条规定，可以直接作为模板。",
  "guide.status": "标有 <span class='chip decide'>待确定</span> 的事项仍需全组商定。本手册由 A 维护；要修改某项做法，先在组会上提出，再按新做法执行。",

  "guide.toc": `
    <h2 id='guide-toc-title'>本页内容</h2>
    <ol>
      <li><a href='#setup'>安装 SUMO 和 Python</a></li>
      <li><a href='#layout'>代码和文件放在哪里</a></li>
      <li><a href='#example'>运行环路示例</a></li>
      <li><a href='#new'>搭建一个新实验</a></li>
      <li><a href='#records'>运行编号和运行记录</a></li>
      <li><a href='#checks'>每次运行必须通过的检查</a></li>
      <li><a href='#units'>单位和测量方法</a></li>
      <li><a href='#decide'>待确定事项</a></li>
      <li><a href='#git'>用 Git 协作</a></li>
    </ol>`,

  "guide.setup": `
    <h2>1. 安装 SUMO 和 Python</h2>
    <p>开发阶段使用 SUMO 正式版 <strong>1.27.1</strong>，其中已包含 IDM。NaSch 只在 SUMO 开发版中提供，OVM 由本项目自行加入，所以正式实验将使用 A 提供的固定版本。正式版足以熟悉流程和开发场景。</p>
    <ol>
      <li>按 <a href='https://sumo.dlr.de/docs/Installing/index.html'>SUMO 安装说明</a> 安装适合自己系统的 SUMO 1.27.1。</li>
      <li>设置 <code>SUMO_HOME</code>，并把 SUMO 的 <code>bin</code> 目录加入 <code>PATH</code>：
        <ul>
          <li><strong>Windows：</strong><code>.msi</code> 安装包会自动设置这两项。安装后关闭并重新打开终端。</li>
          <li><strong>macOS：</strong>安装包不会设置这两项。把下面两行加到 <code>~/.zshrc</code> 末尾，再运行 <code>source ~/.zshrc</code>：
<pre><code>export SUMO_HOME="/Library/Frameworks/EclipseSUMO.framework/Versions/Current/EclipseSUMO/share/sumo"
export PATH="/Library/Frameworks/EclipseSUMO.framework/Versions/Current/EclipseSUMO/bin:$PATH"</code></pre>
          </li>
          <li><strong>Linux：</strong>把下面一行加到 <code>~/.bashrc</code> 末尾，然后注销并重新登录。在 Ubuntu 上用 apt 安装时，路径通常是 <code>/usr/share/sumo</code>，而且程序已经在 <code>PATH</code> 中。
<pre><code>export SUMO_HOME="/usr/share/sumo"</code></pre>
          </li>
        </ul>
      </li>
      <li>检查安装结果。输出的第一行应为 <code>Eclipse SUMO sumo 1.27.1</code>。
<pre><code>sumo --version</code></pre>
      </li>
      <li>在 macOS 上使用 <code>sumo-gui</code> 前，先安装 XQuartz（用下面的 Homebrew 命令，或从 <a href='https://www.xquartz.org/'>xquartz.org</a> 下载），再注销并重新登录。没有 XQuartz 时，<code>sumo-gui</code> 会报错 <code>unable to open display</code>。命令行工具不需要 XQuartz。<code>sumo-gui</code> 输出的 <code>Fontconfig warning</code> 不影响运行。
<pre><code>brew install --cask xquartz</code></pre>
      </li>
      <li>在仓库根目录创建全组共用的 Python 环境，只需做一次。这一步会安装固定版本的 Python 和软件包，并安装 <code>src/traffic_project</code> 中的项目代码，让所有脚本都能导入它。
<pre><code>conda env create -f environment.yml</code></pre>
      </li>
      <li>每次打开新终端，运行项目命令前先激活环境：
<pre><code>conda activate traffic</code></pre>
      </li>
    </ol>`,

  "guide.layout": `
    <h2>2. 代码和文件放在哪里</h2>
    <p>代码按功能存放，不按作者存放。每一类代码只有一个位置和一个负责人。</p>
    <div class='table-wrap'>
      <table class='model-table'>
        <thead><tr><th>位置</th><th>存放内容</th><th>负责人</th></tr></thead>
        <tbody>
          <tr><td><code>scenarios/ring/</code></td><td>环路路网，以及为一次运行摆放车辆的脚本</td><td>B</td></tr>
          <tr><td><code>scenarios/grid/</code></td><td>4×4 测试网格，以及在网格上试做的规划场景</td><td>D</td></tr>
          <tr><td><code>scenarios/city/</code></td><td>OSM 城区路网；城区路网的规划方案</td><td>C；D</td></tr>
          <tr><td><code>configs/&lt;scenario&gt;/</code></td><td>每个实验一个 TOML 文件，写明全部参数</td><td>场景负责人</td></tr>
          <tr><td><code>scripts/</code></td><td>命令行入口，每个任务一个：<code>&lt;scenario&gt;_sweep.py</code>、<code>plot_&lt;scenario&gt;.py</code></td><td>场景负责人</td></tr>
          <tr><td><code>src/traffic_project/</code> <code>config.py</code>、<code>io.py</code>、<code>runner.py</code></td><td>读取配置、读取 SUMO 输出、运行 SUMO、写运行记录、通用检查</td><td>A</td></tr>
          <tr><td><code>src/traffic_project/measurements.py</code></td><td>测量量，每个场景一个函数</td><td>A；环路 B；路网 C</td></tr>
          <tr><td><code>src/traffic_project/demand.py</code></td><td>城区路网的恒定密度 TraCI 控制器（尚未建立）</td><td>C</td></tr>
          <tr><td><code>src/traffic_project/analysis/</code></td><td>临界点、涨落和误差范围（尚未建立）</td><td>E</td></tr>
          <tr><td><code>results/&lt;scenario&gt;/</code></td><td>汇总多次运行的表格和图表，文件保持精简</td><td>场景负责人</td></tr>
          <tr><td><code>data/raw/</code>、<code>data/processed/</code></td><td>外部数据：OSM、PeMS、highD、LTA</td><td>E</td></tr>
          <tr><td><code>runs/&lt;run-id&gt;/</code></td><td>每次运行一个目录，由脚本写出，不手工修改</td><td>—</td></tr>
          <tr><td><code>sandbox/&lt;your-name&gt;/</code></td><td>个人试验代码和 notebook</td><td>本人</td></tr>
          <tr><td><code>docs/</code></td><td>本网站</td><td>A</td></tr>
        </tbody>
      </table>
    </div>
    <p>git 忽略 <code>runs/</code>、<code>data/raw/</code>、<code>sandbox/</code> 和所有 <code>*.fcd.xml</code>，表中其他内容都提交到 git。</p>
    <p><strong>规定</strong></p>
    <ol>
      <li><strong>不复制共用代码。</strong>运行 SUMO、读取输出、写运行记录时，一律导入 <code>traffic_project</code>。缺少某项功能时，告诉 A，或提交一个 PR 把它加到共用代码中。</li>
      <li><strong>参数不写在代码里。</strong>模型参数、密度、种子和时长全部写在 <code>configs/</code> 中该实验的 TOML 文件里。</li>
      <li><strong>一个实验对应一个配置文件和一条命令。</strong>任何人从干净的 commit 出发都能复现。</li>
      <li><strong><code>sandbox/</code> 中的代码不得产出正式结果。</strong>结果写进报告或放上网站前，先把代码移到上表规定的位置。</li>
      <li><strong>每个脚本开头写文档字符串</strong>，说明用途和运行方法。</li>
    </ol>`,

  "guide.example": `
    <h2>3. 运行环路示例</h2>
    <p>所有命令都在仓库根目录、激活 <code>traffic</code> 环境后运行。示例在长度 1000 m 的单车道环路上运行 IDM，全部参数写在 <code>configs/ring/idm_sweep.toml</code> 中。</p>
    <ol>
      <li>生成环路路网。命令会写出 <code>scenarios/ring/ring_1000.net.xml</code>，该文件已在 git 中。
<pre><code>python scenarios/ring/build_net.py --length 1000</code></pre>
      </li>
      <li>生成一次运行的输入：30 辆车，种子 1。命令会创建 <code>runs/ring_idm_L1000_n30_s1/</code>。
<pre><code>python scenarios/ring/build_run.py --config configs/ring/idm_sweep.toml --vehicles 30 --seed 1</code></pre>
      </li>
      <li>运行 SUMO。以下两条命令任选其一：
        <ul>
          <li>只运行，不打开窗口：
<pre><code>sumo -c runs/ring_idm_L1000_n30_s1/run.sumocfg</code></pre>
          </li>
          <li>在 <code>sumo-gui</code> 中观看。保留 <code>--delay 100</code>：不加这个参数时，1800 秒的仿真不到 1 秒就会结束，看不到任何画面。
<pre><code>sumo-gui -c runs/ring_idm_L1000_n30_s1/run.sumocfg --delay 100 --start</code></pre>
          </li>
        </ul>
      </li>
      <li>运行配置文件中的全部扫描。脚本对每次运行依次生成输入、运行 SUMO、执行第 6 节的检查并写出运行记录，最后写出 <code>results/ring/idm_sweep.csv</code>。
<pre><code>python scripts/ring_sweep.py --config configs/ring/idm_sweep.toml</code></pre>
      </li>
      <li>把基本图和时空图画到 <code>results/ring/</code>。
<pre><code>python scripts/plot_ring.py --config configs/ring/idm_sweep.toml</code></pre>
      </li>
    </ol>
    <p><strong>预期结果：</strong>密度为 30 veh/km 时，平均速度为 16.6 m/s，与该间距下的 IDM 平衡速度一致。流量在 30 veh/km 附近达到峰值。约 40 到 80 veh/km 之间出现走走停停的拥堵波；100 veh/km 以上是均匀的慢速车流。结果不一致时，先检查 SUMO 版本。</p>`,

  "guide.new": `
    <h2>4. 搭建一个新实验</h2>
    <p>每个实验都按以下步骤进行，包括在已有实验基础上改动参数。可以复制环路示例中对应的文件作为起点。</p>
    <ol>
      <li><strong>新建分支</strong>（见第 9 节）。</li>
      <li><strong>编写配置文件</strong> <code>configs/&lt;scenario&gt;/&lt;name&gt;.toml</code>。以 <code>configs/ring/idm_sweep.toml</code> 为起点。顶层的 <code>name</code>、<code>scenario</code> 和 <code>model</code> 必须填写；<code>name</code> 同时决定结果文件的名称。每个数字都用注释写明单位。</li>
      <li><strong>生成场景输入。</strong>在 <code>scenarios/&lt;scenario&gt;/</code> 中编写脚本，参照 <code>scenarios/ring/build_run.py</code>。脚本读取配置文件，为每次运行写出一个 <code>runs/&lt;run-id&gt;/</code> 目录并输出运行编号。写出的 <code>.sumocfg</code> 使用相对路径，把 <code>time-to-teleport</code> 设为 <code>-1</code>，把 <code>collision.action</code> 设为 <code>warn</code>。</li>
      <li><strong>添加测量函数。</strong>在 <code>src/traffic_project/measurements.py</code> 中加一个函数，参照 <code>ring_summary</code>。函数读取一次运行的输出，返回 <code>(measurements, checks)</code>。这一步修改了共用代码，PR 由 A 审核。</li>
      <li><strong>编写入口脚本</strong> <code>scripts/&lt;scenario&gt;_sweep.py</code>，参照 <code>scripts/ring_sweep.py</code>。脚本接受 <code>--config</code> 参数，按扫描逐次运行，使用下方的共用调用，最后写出 <code>results/&lt;scenario&gt;/&lt;name&gt;.csv</code>。</li>
      <li><strong>运行并检查输出。</strong>每次运行都会输出 <code>ok</code>，或输出 <code>INVALID</code> 和未通过的检查项。先排除每次无效运行的原因，再使用结果。</li>
      <li><strong>画图</strong>：用 <code>scripts/plot_&lt;scenario&gt;.py --config …</code> 把图表写到 <code>results/&lt;scenario&gt;/</code>。</li>
      <li><strong>提交</strong>：把配置文件、代码和结果一起提交，然后发起 PR。</li>
    </ol>
    <p>每个入口脚本都使用以下共用调用。下面只是结构示意，不能直接运行：</p>
<pre><code>from traffic_project import ROOT, config, io, measurements, runner

cfg = config.load(args.config)
for each run in the sweep:
    run_id, run_dir = …                      # from scenarios/&lt;scenario&gt;/build_*.py
    runner.write_manifest(run_dir, run_id, cfg, parameters)
    _, checks = runner.run_sumo(run_dir)
    measured, more_checks = measurements.&lt;scenario&gt;_summary(…)
    rows.append(runner.finish(run_dir, run_id, measured, {**checks, **more_checks}))
io.write_csv(rows, ROOT / "results" / cfg["scenario"] / f"{cfg['name']}.csv", columns)</code></pre>`,

  "guide.records": `
    <h2>5. 运行编号和运行记录</h2>
    <p>运行编号依次写出场景、模型、变化的参数和种子，用下划线连接，不含空格。环路示例的编号是 <code>ring_idm_L1000_n30_s1</code>：环路、IDM、长度 1000 m、30 辆车、种子 1。其他场景的负责人按同样的方式命名，并把格式补充到本节。</p>
    <div class='table-wrap'>
      <table class='model-table'>
        <thead><tr><th><code>runs/&lt;run-id&gt;/</code> 中的文件</th><th>内容</th></tr></thead>
        <tbody>
          <tr><td><code>run.sumocfg</code></td><td>SUMO 运行配置：路网、路线、时长、步长、种子和输出。路径都是相对路径，换一台电脑也能运行。</td></tr>
          <tr><td><code>vehicles.rou.xml</code></td><td>车型及其模型参数、路线和初始位置</td></tr>
          <tr><td><code>fcd.xml</code></td><td>每辆车在每个时间步的位置和速度，文件较大</td></tr>
          <tr><td><code>log.txt</code></td><td>SUMO 的运行信息，用于碰撞和瞬移检查</td></tr>
          <tr><td><code>manifest.json</code></td><td>运行编号、场景、模型、配置文件及其哈希值、全部参数、SUMO 版本、git commit 和生成时间</td></tr>
          <tr><td><code>summary.json</code></td><td>测量结果和每项检查的结果，<code>valid</code> 为 true 或 false</td></tr>
        </tbody>
      </table>
    </div>
    <p>报告和网站上的每个数字都要保留来源运行编号。配置文件的哈希值可以说明运行之后配置文件是否改动过。git commit 以 <code>-dirty</code> 结尾，表示运行时代码有未提交的修改；正式结果必须来自干净的 commit。</p>`,

  "guide.checks": `
    <h2>6. 每次运行必须通过的检查</h2>
    <p>有几类问题会悄悄改变实验，SUMO 却不会因此停止运行。所以每次运行都把下列检查结果写入 <code>summary.json</code>。前三项由 <code>runner.run_sumo</code> 检查，其余由场景的测量函数检查。无效的运行保留下来用于排查，但不得进入任何表格和图表。</p>
    <div class='table-wrap'>
      <table class='model-table'>
        <thead><tr><th>检查项</th><th>发现什么问题</th></tr></thead>
        <tbody>
          <tr><td><code>sumo_exit_ok</code></td><td>SUMO 因错误而停止</td></tr>
          <tr><td><code>no_teleport</code></td><td>SUMO 默认会把等待超过 300 秒的车移走，再放到前方。每次运行都把 <code>time-to-teleport</code> 设为 <code>-1</code>，关闭这一行为。</td></tr>
          <tr><td><code>no_collision</code></td><td>车辆重叠。每次运行都把 <code>collision.action</code> 设为 <code>warn</code>，让碰撞记录在日志中。</td></tr>
          <tr><td><code>all_vehicles_present</code></td><td>车辆初始位置离其他车太近时，SUMO 会推迟插入这辆车，并且不报错。此时车辆数和密度都是错的。在环路上，<code>build_run.py</code> 还会直接拒绝放不下的车辆数。</td></tr>
          <tr><td><code>no_negative_speed</code></td><td>模型错误，尤其是新写的 OVM 代码</td></tr>
        </tbody>
      </table>
    </div>
    <p>环路还要遵守两条规则。每条边都显式设置 <code>length</code>，并用 <code>--no-internal-links</code> 生成路网，保证密度严格等于车辆数 ÷ 环路长度。模型有已知结果时，用它核对仿真：IDM 平衡速度、NaSch 在 \\(p = 0\\) 时的结果、OVM 稳定性条件。</p>`,

  "guide.units": `
    <h2>7. 单位和测量方法</h2>
    <div class='table-wrap'>
      <table class='model-table'>
        <thead><tr><th>物理量</th><th>单位和规则</th></tr></thead>
        <tbody>
          <tr><td>时间</td><td>s；当前示例的步长为 1 s <span class='chip decide'>待确定</span></td></tr>
          <tr><td>长度、位置</td><td>m</td></tr>
          <tr><td>速度</td><td>文件中一律用 m/s；只在正文和图表标签中使用 km/h</td></tr>
          <tr><td>密度 \\(k\\)</td><td>veh/km</td></tr>
          <tr><td>流量 \\(q\\)</td><td>veh/h</td></tr>
          <tr><td>预热</td><td>舍弃前 600 s，测量使用 600–1800 s 的数据 <span class='chip decide'>待确定</span></td></tr>
        </tbody>
      </table>
    </div>
    <p>在环路上，平均速度 \\(\\bar v\\) 是每个时间步所有车辆速度的平均值，再在测量时段内取时间平均。环路上没有车辆进出，所以流量为 \\(q = k\\,\\bar v\\)。拥堵车辆比例 \\(\\phi\\) 是速度低于阈值的车辆所占比例，它随时间的方差即涨落 \\(\\chi\\)。城市路网的测量方法由 C 按同样的方式定义。</p>`,

  "guide.decide": `
    <h2>8. 待确定事项</h2>
    <ul>
      <li><strong>IDM 参数</strong>（B 牵头，全组商定）。示例使用的是暂定值：加速度 1.0 m/s²、舒适减速度 1.5 m/s²、车头时距 1.5 s、最小间距 2 m、最高速度 30 m/s、车长 5 m。</li>
      <li><strong>环路拥堵判据</strong>（B）。暂定判据「速度低于 5 m/s」会把 100 veh/km 以上均匀的慢速车流判为完全拥堵，而这时并没有走走停停的拥堵波。新判据必须能区分这两种状态。</li>
      <li><strong>路网拥堵判据</strong>（C）。</li>
      <li><strong>密度取值和每个密度的种子数</strong>（B、C 与 E 商定），供 E 估计误差范围。</li>
      <li><strong>连续模型的步长和预热时长</strong>。</li>
      <li><strong>哪些运行保留 <code>fcd.xml</code>。</strong>30 辆车运行 1800 秒约产生 7 MB，完整扫描只应为代表性运行保留轨迹。</li>
      <li><strong>包含 NaSch 和 OVM 的固定版 SUMO</strong>（A）。</li>
    </ul>`,

  "guide.git": `
    <h2>9. 用 Git 协作</h2>
    <p>任何人都不直接推送到 <code>main</code>。所有改动都通过 Pull Request（PR）合并到 <code>main</code>。<strong>PR 由任意一位其他成员批准即可；改动 <code>src/traffic_project/</code> 的 PR 必须由 A 批准</strong>，A 自己发起的除外，由任意一位其他成员批准。</p>
    <ol>
      <li>从最新的 <code>main</code> 开始：
<pre><code>git switch main
git pull</code></pre>
      </li>
      <li>新建分支，命名为 <code>&lt;成员字母&gt;/&lt;内容&gt;</code>，例如：
<pre><code>git switch -c b/ring-bottleneck</code></pre>
      </li>
      <li>提交改动，提交说明写清改了什么。</li>
      <li>推送分支：
<pre><code>git push -u origin b/ring-bottleneck</code></pre>
      </li>
      <li>在 GitHub 上发起合并到 <code>main</code> 的 PR，请另一位成员审核。获得批准后再合并。</li>
    </ol>
    <p><strong>发起 PR 前</strong></p>
    <ol>
      <li>确认 <code>git status</code> 中没有 <code>runs/</code>、<code>data/raw/</code> 或 <code>sandbox/</code> 下的文件。</li>
      <li>把配置文件、代码和 <code>results/</code> 一起提交，保证结果始终对应产生它的代码。</li>
      <li>结果写进报告或放上网站前，先从干净的 commit 重新运行一次。</li>
      <li>如果修改了本手册中的某项规定，在同一个 PR 中更新本手册。</li>
    </ol>`
});
