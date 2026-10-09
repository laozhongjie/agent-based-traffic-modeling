Object.assign(window.I18N.static.zh, {
  "model.nav": "模型介绍页面",
  "model.purpose": "本页介绍模型及其假设。示例仅用于说明原理，不是本项目正式 SUMO 实验的结果。",
  "model.ring": "打开环路实验页面",
  "model.network": "打开城市路网实验页面",
  "model.toOvm": "下一模型：OVM",
  "model.toIdm": "下一模型：IDM",
  "model.toNasch": "与 NaSch 对比",

  "model.nasch.meta": "NaSch 模型 · 交通建模",
  "model.nasch.tag": "离散 · 随机 · 元胞自动机",
  "model.nasch.title": "Nagel–Schreckenberg 模型（NaSch）",
  "model.nasch.lede": "四条简单规则描述车辆如何加速、保持间距、随机减速并移动。大量车辆共同作用后，即使道路上没有红绿灯或障碍，也可能出现走走停停的车流。",
  "model.nasch.idea": `
    <h2>1. 基本思想</h2>
    <p>NaSch 由 Kai Nagel 和 Michael Schreckenberg 于 1992 年提出，是一维元胞自动机模型。单车道被划分为格子，每个格子为空或被一辆车占据。位置、速度和时间均为离散变量。</p>
    <p>每辆车只需知道自身速度和前方空格数。所有车辆并行更新：先用同一时刻的状态计算下一步，再同时移动，不能让后更新的车辆使用前车已经移动后的状态。</p>`,
  "model.nasch.state": `
    <h2>2. 状态与道路几何</h2>
    <p>车辆 \\(i\\) 的位置为 \\(x_i\\)，速度为整数 \\(v_i\\in\\{0,\\ldots,v_{\\max}\\}\\)。间距 \\(g_i=x_{i+1}-x_i-1\\) 表示本车与前车之间的空格数。</p>
    <p>在长度为 \\(L\\) 个格子的环路上，距离和位置按模 \\(L\\) 处理。若有 \\(N\\) 辆车，占有率为 \\(\\rho=N/L\\)。占有率没有量纲；只有指定实际格长后，才能换算为 veh/km。</p>`,
  "model.nasch.rules": `
    <h2>3. 四条更新规则</h2>
    <ol>
      <li><strong>加速：</strong>速度增加 1，但不超过最大速度。</li>
      <li><strong>保持安全间距：</strong>速度不超过前方空格数。</li>
      <li><strong>随机减速：</strong>以概率 \\(p\\) 将当前速度减 1，但不低于 0。</li>
      <li><strong>移动：</strong>按最终速度前进，所有车辆同时移动。</li>
    </ol>
    <div class='eq-math'>\\[\\begin{aligned}
      v_i^{(1)}&=\\min(v_i(t)+1,v_{\\max})\\\\
      v_i^{(2)}&=\\min(v_i^{(1)},g_i(t))\\\\
      v_i(t+1)&=\\begin{cases}\\max(v_i^{(2)}-1,0)&\\text{以概率 }p\\\\v_i^{(2)}&\\text{以概率 }1-p\\end{cases}\\\\
      x_i(t+1)&=[x_i(t)+v_i(t+1)]\\bmod L
    \\end{aligned}\\]</div>
    <p class='caption'>例如，车辆速度为 \\(v=3\\)、最大速度为 \\(v_{\\max}=5\\)、前方有 \\(g=2\\) 个空格。车辆先加速到 4，再因间距限制降到 2。若触发随机减速，则移动 1 格；否则移动 2 格。</p>`,
  "model.nasch.parameters": `
    <h2>4. 参数与物理单位</h2>
    <div class='table-wrap'><table class='model-table'>
      <thead><tr><th>变量</th><th>含义与影响</th></tr></thead>
      <tbody>
        <tr><td>\\(v_{\\max}\\)</td><td>最大速度，单位为格/步。值越大，允许的自由流速度越高。</td></tr>
        <tr><td>\\(p\\in[0,1]\\)</td><td>无量纲的随机减速概率，控制驾驶噪声。应记录随机种子，并进行重复实验。</td></tr>
        <tr><td>\\(L,\\ N,\\ \\rho\\)</td><td>道路格数、车辆数及占有率 \\(N/L\\)。研究时应分别改变密度和系统尺寸。</td></tr>
        <tr><td>\\(\\ell,\\ \\Delta t\\)</td><td>实际格长（m）和时间步长（s）。实际速度为 \\(v\\ell/\\Delta t\\)，单位 m/s；密度为 \\(1000\\rho/\\ell\\)，单位 veh/km。与实际数据比较前，应先确定这些尺度。</td></tr>
      </tbody>
    </table></div>`,
  "model.nasch.jams": `
    <h2>5. 拥堵如何出现</h2>
    <p>占有率较低时，多数车辆有足够空间加速。占有率升高后，一次随机减速会缩短后车间距，后车被迫减速，再影响更后方的车辆。局部扰动可能逐步形成排队，队列上游端向车辆行驶方向的反方向传播。</p>
    <p>在确定性情形 \\(p=0\\) 下，理想环路的稳态基本图为 \\(q(\\rho)=\\min(v_{\\max}\\rho,1-\\rho)\\)，流量单位为每步通过某个格子边界的车辆数。峰值位于 \\(\\rho=1/(v_{\\max}+1)\\)。这只是理想确定性模型的参考，不是 \\(p&gt;0\\) 时的通用阈值。</p>
    <p>存在随机减速时，应通过重复实验测量流量、平均速度、拥堵车辆比例和时空图。有限系统中的流量峰值本身，不能证明无限系统存在严格相变。</p>`,
  "model.nasch.limits": `
    <h2>6. 优点与限制</h2>
    <ul>
      <li>计算快、规则直观，适合研究集体行为和随机扰动。</li>
      <li>在标准单车道、并行更新的模型中，安全间距规则可以避免车辆重叠。</li>
      <li>空间和时间较粗，无法表达平滑加速度。基础模型不包含换道、信号灯或显式反应延迟。</li>
      <li>随机减速只是驾驶差异的简化描述，与实际交通比较时仍需标定。</li>
    </ul>`,
  "model.nasch.project": `
    <h2>7. 在本项目中的作用</h2>
    <p>NaSch 是高速公路环路的随机模型基准。改变占有率、随机减速概率和道路长度，观察噪声与有限尺寸对拥堵的影响，再与 OVM 和 IDM 比较。</p>
    <p>首页动画在浏览器中演示这些规则。正式结果来自 SUMO 1.28.0，其中内置 NaSch（<code>carFollowModel="NaSch"</code>）。项目用 \\(p = 0\\) 时的确定性结果检查它是否符合上述规则。</p>`,
  "model.nasch.reference": `
    <h2>8. 原始论文</h2>
    <p>K. Nagel 和 M. Schreckenberg（1992），<em>A cellular automaton model for freeway traffic</em>，Journal de Physique I，2，2221–2229。<a href='https://doi.org/10.1051/jp1:1992277' class='more'>阅读原始论文</a></p>`,

  "model.ovm.meta": "OVM 最优速度模型 · 交通建模",
  "model.ovm.tag": "连续 · 确定性 · 跟车模型",
  "model.ovm.title": "最优速度模型（OVM）",
  "model.ovm.lede": "驾驶员根据与前车的距离选择期望速度，并逐步调整实际速度。即使没有随机减速，当响应不够快时，微小扰动也可能被放大，形成拥堵。",
  "model.ovm.idea": `
    <h2>1. 基本思想</h2>
    <p>OVM 由 Bando 等人于 1995 年提出，位置和速度都是连续变量。最优速度函数 \\(V(h)\\) 根据车头间距给出期望速度：车辆靠近时希望低速行驶，间距较大时趋近自由流速度。</p>
    <p>「最优」是速度函数的名称，并不表示驾驶员求解了路线或行程时间的优化问题。</p>`,
  "model.ovm.state": `
    <h2>2. 状态与距离约定</h2>
    <p>\\(x_i(t)\\) 和 \\(v_i(t)\\) 分别为位置和速度。车头间距 \\(h_i=x_{i+1}-x_i\\) 是相邻车辆对应参考点之间的距离。在环路上，跨越边界时按向前方向计算。</p>
    <p>车头间距不同于保险杠之间的净间距。若车辆长度均为 \\(\\ell_{\\mathrm{veh}}\\)，净间距为 \\(s_i=h_i-\\ell_{\\mathrm{veh}}\\)。将解析 OVM 接入 SUMO 时，应保留这一区别。</p>`,
  "model.ovm.equations": `
    <h2>3. 向期望速度松弛</h2>
    <div class='eq-math'>\\[\\frac{dx_i}{dt}=v_i,\\qquad \\frac{dv_i}{dt}=\\alpha[V(h_i)-v_i]\\]</div>
    <p>实际速度低于期望速度时加速，高于期望速度时减速。敏感度 \\(\\alpha&gt;0\\) 的单位为 s\\(^{-1}\\)，\\(1/\\alpha\\) 是松弛时间，不是显式的反应延迟。</p>
    <p>一种常见平滑函数可以写成量纲一致的形式：</p>
    <div class='eq-math'>\\[V(h)=\\frac{v_{\\max}}{1+\\tanh(h_c/d)}\\left[\\tanh\\left(\\frac{h-h_c}{d}\\right)+\\tanh\\left(\\frac{h_c}{d}\\right)\\right]\\]</div>
    <p class='caption'>该形式满足 \\(V(0)=0\\)，大间距时 \\(V(h)\\to v_{\\max}\\)。首页采用的简写 \\(v_{\\max}/2\\) 形式常用于已缩放的坐标；其中速度参数是振幅，大间距极限为 \\(v_{\\max}[1+\\tanh(h_c)]/2\\)。定量比较前应确定长度尺度和归一化方式。</p>`,
  "model.ovm.parameters": `
    <h2>4. 参数与物理单位</h2>
    <div class='table-wrap'><table class='model-table'>
      <thead><tr><th>变量</th><th>含义与影响</th></tr></thead>
      <tbody>
        <tr><td>\\(\\alpha\\)</td><td>敏感度，单位 s\\(^{-1}\\)。值越大，实际速度越快趋向 \\(V(h)\\)。</td></tr>
        <tr><td>\\(v_{\\max}\\)</td><td>上述归一化函数的大间距期望速度，单位 m/s。</td></tr>
        <tr><td>\\(h_c,\\ d\\)</td><td>过渡间距和平滑长度，单位 m。\\(h_c\\) 决定曲线最陡处的位置；\\(d\\) 越小，期望速度对间距变化越敏感。</td></tr>
        <tr><td>\\(h_0=L/N\\)</td><td>实际长度为 \\(L\\)、含 \\(N\\) 辆车的环路上的均匀车头间距，单位 m。密度为 \\(1000/h_0\\)，单位 veh/km。</td></tr>
        <tr><td>\\(\\Delta t\\)</td><td>数值积分步长，单位 s，不是 OVM 的定义参数。应减小步长检查数值收敛性。</td></tr>
      </tbody>
    </table></div>`,
  "model.ovm.stability": `
    <h2>5. 均匀车流与失稳</h2>
    <p>均匀车流中，所有车头间距均为 \\(h_0\\)，速度均为 \\(V(h_0)\\)。对标准、同质 OVM 在此状态附近做线性化，在大环路的长波极限下，稳定条件为 \\(V'(h_0)&lt;\\alpha/2\\)，边界为 \\(V'(h_0)=\\alpha/2\\)。</p>
    <div class='eq-math'>\\[V'(h)=\\frac{v_{\\max}}{d[1+\\tanh(h_c/d)]}\\operatorname{sech}^2\\left(\\frac{h-h_c}{d}\\right)\\]</div>
    <p>当 \\(V'(h_0)&gt;\\alpha/2\\) 时，微小间距变化要求较大的期望速度变化，而速度调整的松弛过程可能放大扰动。车辆反复减速和加速，即使没有随机噪声，也能形成走走停停波。</p>
    <p>这个判据依赖具体模型和背景状态。有限环路只允许离散的扰动模式，因此阈值可能不同于长波极限。非线性拥堵和数值安全措施的影响也需要单独检查。</p>`,
  "model.ovm.limits": `
    <h2>6. 优点与限制</h2>
    <ul>
      <li>机制简洁，具有解析稳定性条件，适合区分确定性失稳与随机噪声。</li>
      <li>基础加速度规则使用车头间距和自身速度，没有单独的接近速度项。</li>
      <li>不保证避免碰撞，也没有现实的加速度边界。极端状态或数值积分可能产生不合理结果。</li>
      <li>速度截断、紧急制动或其他安全覆盖规则会改变动力学，应明确记录。</li>
    </ul>`,
  "model.ovm.project": `
    <h2>7. 在本项目中的作用</h2>
    <p>OVM 提供确定性的理论对照。在均匀环路车流中施加小扰动，扫描密度和敏感度，将扰动增长情况与解析预测比较。</p>
    <p>项目计划在固定版本的 SUMO 中用 C++ 实现 OVM。与理论模型比较前，应确认具体的 \\(V(h)\\)、车头间距定义、积分方法和安全干预规则。</p>`,
  "model.ovm.reference": `
    <h2>8. 原始论文</h2>
    <p>M. Bando、K. Hasebe、A. Nakayama、A. Shibata 和 Y. Sugiyama（1995），<em>Dynamical model of traffic congestion and numerical simulation</em>，Physical Review E，51，1035–1042。<a href='https://doi.org/10.1103/PhysRevE.51.1035' class='more'>阅读原始论文</a></p>`,

  "model.idm.meta": "IDM 智能驾驶员模型 · 交通建模",
  "model.idm.tag": "连续 · 确定性 · 跟车模型",
  "model.idm.title": "智能驾驶员模型（IDM）",
  "model.idm.lede": "车辆向期望速度加速，同时根据前车间距和速度调整驾驶行为。一个加速度方程同时描述自由道路行驶、跟车和提前制动。",
  "model.idm.idea": `
    <h2>1. 基本思想</h2>
    <p>IDM 由 Treiber、Hennecke 和 Helbing 开发，并在 2000 年的论文中介绍，是连续跟车模型。驾驶员在「达到期望速度」和「保持随速度变化的间距」之间取得平衡。</p>
    <p>「智能」指这种自适应驾驶规则，不代表模型包含学习算法或路线优化。基础同质模型是确定性的；可通过不同驾驶员参数或外部过程引入差异。</p>`,
  "model.idm.state": `
    <h2>2. 状态与接近速度符号</h2>
    <p>加速度取决于自身速度 \\(v_i\\)、保险杠之间的净间距 \\(s_i\\)，以及接近速度 \\(\\Delta v_i=v_i-v_{i+1}\\)。\\(\\Delta v_i&gt;0\\) 表示本车正在接近前车。</p>
    <p>若车辆长度均为 \\(\\ell_{\\mathrm{veh}}\\)，则 \\(s_i=x_{i+1}-x_i-\\ell_{\\mathrm{veh}}\\)。接近速度的符号必须保持一致；只反转定义、不修改方程，会使提前制动项的作用方向反转。</p>`,
  "model.idm.equations": `
    <h2>3. 加速度与期望间距</h2>
    <div class='eq-math'>\\[\\frac{dx_i}{dt}=v_i,\\qquad \\frac{dv_i}{dt}=a\\left[1-\\left(\\frac{v_i}{v_0}\\right)^\\delta-\\left(\\frac{s^*(v_i,\\Delta v_i)}{s_i}\\right)^2\\right]\\]
    \\[s^*(v,\\Delta v)=s_0+\\max\\left(0,vT+\\frac{v\\Delta v}{2\\sqrt{ab}}\\right)\\]</div>
    <p>自由道路项 \\(1-(v/v_0)^\\delta\\) 使低速车辆向 \\(v_0\\) 加速。相互作用项 \\(-(s^*/s)^2\\) 在实际间距相对期望间距较小时降低加速度，或使车辆制动。</p>
    <p>期望间距包括停车间距 \\(s_0\\)、时距项 \\(vT\\) 和接近速度项 \\(v\\Delta v/(2\\sqrt{ab})\\)。这里的非负截断是一种常见实现约定，保证 \\(s^*\\ge s_0\\)；应记录 SUMO 使用的具体变体。</p>
    <p class='caption'>示例：\\(s_0=2\\) m、\\(T=1.5\\) s、\\(a=1\\) m/s²、\\(b=2\\) m/s²。以 \\(v=10\\) m/s 行驶且 \\(\\Delta v=0\\) 时，期望间距为 17 m；若 \\(\\Delta v=2\\) m/s，期望间距增至约 24.1 m。这些值仅用于说明公式，不是项目标定值。</p>`,
  "model.idm.parameters": `
    <h2>4. 参数与物理单位</h2>
    <div class='table-wrap'><table class='model-table'>
      <thead><tr><th>变量</th><th>含义与影响</th></tr></thead>
      <tbody>
        <tr><td>\\(v_0\\)</td><td>自由道路上的期望速度，单位 m/s，不同车辆可以取不同值。</td></tr>
        <tr><td>\\(T\\)</td><td>期望时距，单位 s。相同速度下，\\(T\\) 越大，跟车间距越大；它不是显式反应延迟。</td></tr>
        <tr><td>\\(s_0\\)</td><td>停车时的最小期望净间距，单位 m。</td></tr>
        <tr><td>\\(a\\)</td><td>最大自由道路加速度参数，单位 m/s²，决定低速车辆加速的快慢。</td></tr>
        <tr><td>\\(b\\)</td><td>舒适减速度参数，单位 m/s²，取正值。它影响提前制动，不是制动减速度的硬上限。</td></tr>
        <tr><td>\\(\\delta\\)</td><td>无量纲加速度指数，常取 4，影响车辆趋近期望速度的方式。</td></tr>
      </tbody>
    </table></div>`,
  "model.idm.equilibrium": `
    <h2>5. 平衡态与交通波</h2>
    <p>均匀车流中，所有车辆以相同速度 \\(v&lt;v_0\\) 行驶，因而 \\(\\Delta v=0\\)，加速度为 0。上述方程对应的平衡净间距为：</p>
    <div class='eq-math'>\\[s_{\\mathrm{eq}}(v)=\\frac{s_0+vT}{\\sqrt{1-(v/v_0)^\\delta}},\\qquad k(v)=\\frac{1000}{s_{\\mathrm{eq}}(v)+\\ell_{\\mathrm{veh}}}\\]</div>
    <p>间距和车长取 m 时，\\(k\\) 的单位为 veh/km。速度 \\(v\\) 取 m/s 时，平衡流量为 \\(q=3.6kv\\)，单位 veh/h。该关系描述同质平衡态，实际拥堵车流不一定落在这条曲线上。</p>
    <p>根据参数和密度，扰动可能衰减，也可能被放大成走走停停波。接近速度反馈支持提前制动，但不能使所有状态稳定。稳定性取决于完整加速度函数对速度、间距和接近速度的偏导数，不能直接套用 OVM 的阈值。</p>`,
  "model.idm.limits": `
    <h2>6. 优点与限制</h2>
    <ul>
      <li>参数有明确物理含义，同一条平滑规则可描述自由流、跟车和制动。</li>
      <li>接近速度反馈使车辆在接近较慢前车时提前制动。</li>
      <li>在适当的连续动力学和初始条件下，模型设计旨在避免碰撞；这不是对任意积分步长、插入车辆或突然停车的无条件保证。</li>
      <li>基础模型不包含换道、显式反应延迟或路线选择。SUMO 通过其他机制处理这些行为。</li>
    </ul>`,
  "model.idm.project": `
    <h2>7. 在本项目中的作用</h2>
    <p>IDM 是城市路网的主要跟车模型，也是环路实验中的连续模型基准。先将流量和拥堵模式与 NaSch、OVM 比较，再在不同规划方案中固定驾驶员参数。</p>
    <p>SUMO 内置 IDM 实现。应记录版本、参数映射、内部积分步长和安全设置，并区分跟车规则与信号灯、交叉口优先权及换道逻辑。</p>`,
  "model.idm.reference": `
    <h2>8. 原始论文</h2>
    <p>M. Treiber、A. Hennecke 和 D. Helbing（2000），<em>Congested traffic states in empirical observations and microscopic simulations</em>，Physical Review E，62，1805–1824。<a href='https://doi.org/10.1103/PhysRevE.62.1805' class='more'>阅读原始论文</a></p>`
});
