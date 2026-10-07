Object.assign(window.I18N.static.zh, {
  "guide.meta": "统一做法 · 交通建模",
  "guide.nav": "统一做法页面",
  "guide.tag": "全组统一做法 · 第一次运行前请读",
  "guide.title": "统一做法",
  "guide.lede": "本页是全组统一做法的唯一依据：怎样安装 SUMO、文件放在哪里、运行怎样命名和记录，以及每次运行必须通过哪些检查。页面中的每一项都已在仓库里的环路示例上验证过。",
  "guide.status": "标有 <span class='chip decide'>待确定</span> 的事项仍需全组商定。本页由 A 维护；要修改某项做法，先在组会上提出，再按新做法执行。",

  "guide.toc": `
    <h2 id='guide-toc-title'>本页内容</h2>
    <ol>
      <li><a href='#setup'>安装 SUMO 和 Python</a></li>
      <li><a href='#layout'>文件放在哪里</a></li>
      <li><a href='#example'>运行环路示例</a></li>
      <li><a href='#records'>运行编号和运行记录</a></li>
      <li><a href='#checks'>每次运行必须通过的检查</a></li>
      <li><a href='#units'>单位和测量方法</a></li>
      <li><a href='#decide'>待确定事项</a></li>
      <li><a href='#commit'>提交前检查</a></li>
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
      <li>使用装有 <code>scipy</code> 和 <code>matplotlib</code> 的 Python 3。<span class='chip decide'>待确定</span> A 将添加 <code>environment.yml</code>，统一全组的软件包版本。</li>
    </ol>`,

  "guide.layout": `
    <h2>2. 文件放在哪里</h2>
    <p>最重要的一条规则：<strong>每次运行都相同的文件放在 <code>scenarios/</code>；为某一次运行生成的文件放在 <code>runs/&lt;run-id&gt;/</code>。</strong>一次完整扫描会产生几百次运行，混进 <code>scenarios/</code> 后两边都无法使用。</p>
    <div class='table-wrap'>
      <table class='model-table'>
        <thead><tr><th>目录</th><th>存放内容</th><th>是否进 git</th></tr></thead>
        <tbody>
          <tr><td><code>scenarios/&lt;name&gt;/</code></td><td>路网、信号方案和生成它们的脚本，例如 <code>scenarios/ring/build_net.py</code></td><td>是</td></tr>
          <tr><td><code>configs/</code></td><td>参数组、密度取值、种子列表和运行时长</td><td>是</td></tr>
          <tr><td><code>scripts/</code></td><td>命令行入口，例如 <code>scripts/ring_sweep.py</code></td><td>是</td></tr>
          <tr><td><code>src/traffic_project/</code></td><td>共用的 Python 代码（运行、测量、分析），尚未建立</td><td>是</td></tr>
          <tr><td><code>runs/&lt;run-id&gt;/</code></td><td>每次运行一个目录：生成的输入、SUMO 输出、日志、记录和检查结果</td><td><strong>否</strong></td></tr>
          <tr><td><code>results/&lt;scenario&gt;/</code></td><td>汇总多次运行的表格和图表，文件保持精简</td><td>是</td></tr>
          <tr><td><code>data/raw/</code></td><td>外部原始数据：OSM、PeMS、highD、LTA</td><td><strong>否</strong></td></tr>
          <tr><td><code>docs/data/</code></td><td>由 <code>results/</code> 生成、供网站使用的精简数据</td><td>是</td></tr>
        </tbody>
      </table>
    </div>
    <p><code>.gitignore</code> 已经排除 <code>runs/</code>、<code>data/raw/</code> 和所有 <code>*.fcd.xml</code>。大文件通过外部存储共享，并写明获取方式。</p>`,

  "guide.example": `
    <h2>3. 运行环路示例</h2>
    <p>所有命令都在仓库根目录运行。示例在长度 1000 m 的单车道环路上运行 IDM。</p>
    <ol>
      <li>生成环路路网。命令会写出 <code>scenarios/ring/ring_1000.net.xml</code>，该文件已在 git 中。
<pre><code>python scenarios/ring/build_net.py --length 1000</code></pre>
      </li>
      <li>生成一次运行的输入：30 辆车，种子 1。命令会创建 <code>runs/ring_idm_L1000_n30_s1/</code>。
<pre><code>python scenarios/ring/build_run.py --vehicles 30 --seed 1</code></pre>
      </li>
      <li>不打开窗口运行 SUMO，或者在 <code>sumo-gui</code> 中观看。不加 <code>--delay</code> 时，1800 秒的仿真不到 1 秒就会结束，看不到任何画面。
<pre><code>sumo -c runs/ring_idm_L1000_n30_s1/run.sumocfg
sumo-gui -c runs/ring_idm_L1000_n30_s1/run.sumocfg --delay 100 --start</code></pre>
      </li>
      <li>运行密度扫描。脚本对每个车辆数依次生成输入、运行 SUMO、执行第 5 节的检查并写出运行记录，最后写出 <code>results/ring/idm_sweep.csv</code>。
<pre><code>python scripts/ring_sweep.py --vehicles 10 20 30 40 50 60 70 80 90 100 110 120 --seeds 1</code></pre>
      </li>
      <li>把基本图和时空图画到 <code>results/ring/</code>。
<pre><code>python scripts/plot_ring.py</code></pre>
      </li>
    </ol>
    <p><strong>预期结果：</strong>密度为 30 veh/km 时，平均速度为 16.6 m/s，与该间距下的 IDM 平衡速度一致。流量在 30 veh/km 附近达到峰值。约 40 到 80 veh/km 之间出现走走停停的拥堵波；100 veh/km 以上是均匀的慢速车流。结果不一致时，先检查 SUMO 版本。</p>`,

  "guide.records": `
    <h2>4. 运行编号和运行记录</h2>
    <p>运行编号依次写出场景、模型、变化的参数和种子，用下划线连接，不含空格。环路示例的编号是 <code>ring_idm_L1000_n30_s1</code>：环路、IDM、长度 1000 m、30 辆车、种子 1。其他场景的负责人按同样的方式命名，并把格式补充到本节。</p>
    <div class='table-wrap'>
      <table class='model-table'>
        <thead><tr><th><code>runs/&lt;run-id&gt;/</code> 中的文件</th><th>内容</th></tr></thead>
        <tbody>
          <tr><td><code>run.sumocfg</code></td><td>SUMO 运行配置：路网、路线、时长、步长、种子和输出。路径都是相对路径，换一台电脑也能运行。</td></tr>
          <tr><td><code>vehicles.rou.xml</code></td><td>车型及其模型参数、路线和初始位置</td></tr>
          <tr><td><code>fcd.xml</code></td><td>每辆车在每个时间步的位置和速度，文件较大</td></tr>
          <tr><td><code>log.txt</code></td><td>SUMO 的运行信息，用于碰撞和瞬移检查</td></tr>
          <tr><td><code>manifest.json</code></td><td>运行编号、场景、模型、参数、SUMO 版本、git commit 和生成时间</td></tr>
          <tr><td><code>summary.json</code></td><td>测量结果和每项检查的结果，<code>valid</code> 为 true 或 false</td></tr>
        </tbody>
      </table>
    </div>
    <p>报告和网站上的每个数字都要保留来源运行编号。git commit 以 <code>-dirty</code> 结尾，表示运行时代码有未提交的修改；正式结果必须来自干净的 commit。</p>`,

  "guide.checks": `
    <h2>5. 每次运行必须通过的检查</h2>
    <p>有几类问题会悄悄改变实验，SUMO 却不会因此停止运行。所以每次运行都把下列检查结果写入 <code>summary.json</code>。无效的运行保留下来用于排查，但不得进入任何表格和图表。</p>
    <div class='table-wrap'>
      <table class='model-table'>
        <thead><tr><th>检查项</th><th>发现什么问题</th></tr></thead>
        <tbody>
          <tr><td><code>all_vehicles_present</code></td><td>车辆初始位置离其他车太近时，SUMO 会推迟插入这辆车，并且不报错。此时车辆数和密度都是错的。在环路上，<code>build_run.py</code> 还会直接拒绝放不下的车辆数。</td></tr>
          <tr><td><code>no_teleport</code></td><td>SUMO 默认会把等待超过 300 秒的车移走，再放到前方。每次运行都把 <code>time-to-teleport</code> 设为 <code>-1</code>，关闭这一行为。</td></tr>
          <tr><td><code>no_collision</code></td><td>车辆重叠。每次运行都把 <code>collision.action</code> 设为 <code>warn</code>，让碰撞记录在日志中。</td></tr>
          <tr><td><code>no_negative_speed</code></td><td>模型错误，尤其是新写的 OVM 代码</td></tr>
          <tr><td><code>sumo_exit_ok</code></td><td>SUMO 因错误而停止</td></tr>
        </tbody>
      </table>
    </div>
    <p>环路还要遵守两条规则。每条边都显式设置 <code>length</code>，并用 <code>--no-internal-links</code> 生成路网，保证密度严格等于车辆数 ÷ 环路长度。模型有已知结果时，用它核对仿真：IDM 平衡速度、NaSch 在 \\(p = 0\\) 时的结果、OVM 稳定性条件。</p>`,

  "guide.units": `
    <h2>6. 单位和测量方法</h2>
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
    <h2>7. 待确定事项</h2>
    <ul>
      <li><strong>IDM 参数</strong>（B 牵头，全组商定）。示例使用的是暂定值：加速度 1.0 m/s²、舒适减速度 1.5 m/s²、车头时距 1.5 s、最小间距 2 m、最高速度 30 m/s、车长 5 m。</li>
      <li><strong>环路拥堵判据</strong>（B）。暂定判据「速度低于 5 m/s」会把 100 veh/km 以上均匀的慢速车流判为完全拥堵，而这时并没有走走停停的拥堵波。新判据必须能区分这两种状态。</li>
      <li><strong>路网拥堵判据</strong>（C）。</li>
      <li><strong>密度取值和每个密度的种子数</strong>（B、C 与 E 商定），供 E 估计误差范围。</li>
      <li><strong>连续模型的步长和预热时长</strong>。</li>
      <li><strong>哪些运行保留 <code>fcd.xml</code>。</strong>30 辆车运行 1800 秒约产生 7 MB，完整扫描只应为代表性运行保留轨迹。</li>
      <li><strong><code>environment.yml</code> 和包含 NaSch、OVM 的固定版 SUMO</strong>（A）。</li>
    </ul>`,

  "guide.commit": `
    <h2>8. 提交前检查</h2>
    <ol>
      <li>确认 <code>git status</code> 中没有 <code>runs/</code> 或 <code>data/raw/</code> 下的文件。</li>
      <li>把代码、场景和 <code>results/</code> 一起提交，保证结果始终对应产生它的代码。</li>
      <li>结果写进报告或放上网站前，先从干净的 commit 重新运行一次。</li>
      <li>修改本页的某项做法时，先告知全组，再在同一次提交中更新本页。</li>
    </ol>`
});
