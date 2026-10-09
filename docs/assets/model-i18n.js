Object.assign(window.I18N.static.zh, {
  "model.nav": "模型介绍页面",
  "model.ring": "打开环路实验页面",
  "model.network": "打开城市路网实验页面",
  "model.toOvm": "下一模型：OVM",
  "model.toIdm": "下一模型：IDM",
  "model.toNasch": "与 NaSch 对比",

  "model.compare": `
    <h2>三个模型对比</h2>
    <div class='table-wrap'><table class='model-table'>
      <thead><tr><th>模型</th><th>空间与时间</th><th>随机性</th><th>均匀车流为何失稳</th><th>是否碰撞</th><th>SUMO 中</th></tr></thead>
      <tbody>
        <tr data-model='nasch'><td><a href='nasch.html'>NaSch</a></td><td>7.5 m 的格子，1 s 一步</td><td>以概率 \\(p\\) 随机减速</td><td>随机减速加上只看间距的保守规则；\\(p=0\\) 时不会自发拥堵</td><td>不会（规则 2）</td><td>1.28.0 起内置</td></tr>
        <tr data-model='ovm'><td><a href='ovm.html'>OVM</a></td><td>连续</td><td>无</td><td>响应太慢：\\(V'(s_0)&gt;\\alpha/2\\)</td><td>会，在失稳区间内</td><td>我们的 C++ 实现</td></tr>
        <tr data-model='idm'><td><a href='idm.html'>IDM</a></td><td>连续</td><td>无</td><td>加速度小或时距短；接近速度项有帮助，但不保证稳定</td><td>连续时间下不会；步长较粗时间距可低于 \\(s_0\\)</td><td>内置</td></tr>
      </tbody>
    </table></div>`,

  "model.nasch.meta": "NaSch 模型 · 交通建模",
  "model.nasch.tag": "离散 · 随机 · 元胞自动机",
  "model.nasch.title": "Nagel–Schreckenberg 模型（NaSch）",
  "model.nasch.lede": "道路切成 7.5 m 一格，时间 1 s 一步，所有车辆每步同时按四条规则更新。唯一的随机性是偶尔的随机减速，但它足以让没有任何瓶颈的道路堵起来。",
  "model.nasch.rule": `
    <h2>规则</h2>
    <p>车辆 \\(i\\) 位于格子 \\(x_i\\)，速度为整数 \\(v_i\\in\\{0,\\ldots,v_{\\max}\\}\\)，单位为格/步。间距 \\(g_i=x_{i+1}-x_i-1\\) 是到前车之间的空格数。每一步，所有车辆同时执行四条规则：</p>
    <ol>
      <li><strong>加速：</strong>\\(v\\leftarrow\\min(v+1,\\,v_{\\max})\\)。司机想开得更快，但每步最多提速 1 格/步。</li>
      <li><strong>不撞前车：</strong>\\(v\\leftarrow\\min(v,\\,g)\\)。车辆不会越过前车当前所在格子的后一格。这是唯一的相互作用，而且只看间距，不看前车速度。</li>
      <li><strong>随机减速：</strong>以概率 \\(p\\) 执行 \\(v\\leftarrow\\max(v-1,\\,0)\\)。它代表司机的各种不完美：走神、过度刹车、起步慢。</li>
      <li><strong>移动：</strong>\\(x\\leftarrow x+v\\)。</li>
    </ol>
    <p>规则 2 保证不会碰撞：即使前车这一步不动，后车也停在它后面。规则 2 也非常保守，因为它按前车可能突然停住来行驶。所有车辆都用同一个旧状态计算下一步；如果逐辆更新、让后车看到前车已经移动后的位置，车队就能像火车一样整体前进，结果会完全不同。</p>`,
  "model.nasch.look": `
    <h2>观察要点</h2>
    <ol class='experiment-list'>
      <li>
        <h3>没有随机性、低密度：自由流</h3>
        <p>\\(p=0\\)、15 veh/km 时，每辆车很快都会在前方留出至少 \\(v_{\\max}\\) 个空格，规则 2 不再起作用，所有车都以 \\(v_{\\max}\\) 行驶。当前点落在上升直线 \\(q=v_{\\max}\\rho\\) 上。</p>
        <button type='button' class='btn' data-preset='nasch-free'>载入</button>
      </li>
      <li>
        <h3>随机减速：幽灵堵车</h3>
        <p>20 veh/km 在 \\(p=0\\) 时是自由流；现在设 \\(p=0.25\\)。偶尔一辆车随机减速，后车被迫减速，再传给更后面的车：时空图里出现短暂的深色带，向后移动，然后消失。道路上没有任何障碍。</p>
        <button type='button' class='btn' data-preset='nasch-ghost'>载入</button>
      </li>
      <li>
        <h3>高密度：持续的拥堵</h3>
        <p>45 veh/km 时，拥堵不再消失，而是持续向后漂移。跟踪带描边的车：它在拥堵里停下、离开、加速，再遇到下一个拥堵。车辆向前穿过拥堵，拥堵本身却向后移动：拥堵是一种波，而不是一群固定的车。</p>
        <button type='button' class='btn' data-preset='nasch-dense'>载入</button>
      </li>
    </ol>`,
  "model.nasch.theory": `
    <h2>基本图为什么是三角形</h2>
    <p>在 \\(L\\) 格、\\(N\\) 辆车的环路上，占有率为 \\(\\rho=N/L\\)，经过任一截面的流量为每步 \\(q=\\frac{1}{L}\\sum_i v_i\\) 辆。规则直接给出两个上界：</p>
    <ul>
      <li>没有车快于 \\(v_{\\max}\\)，所以 \\(q\\le v_{\\max}\\rho\\)；</li>
      <li>没有车走得比它的间距远，而所有间距加起来就是 \\(L-N\\) 个空格，所以 \\(q\\le1-\\rho\\)。</li>
    </ul>
    <p>\\(p=0\\) 时，流量达到两者中较小的那个：</p>
    <div class='eq-math'>\\[q=\\min\\bigl(v_{\\max}\\rho,\\ 1-\\rho\\bigr),\\qquad \\rho_c=\\frac{1}{v_{\\max}+1}\\]</div>
    <p>在 \\(\\rho_c\\) 处，每辆车加上它前方的 \\(v_{\\max}\\) 个空格正好铺满道路。低于 \\(\\rho_c\\) 时所有车以 \\(v_{\\max}\\) 行驶；高于 \\(\\rho_c\\) 时流量受空格数限制，车越多流量越低。换成物理单位（\\(\\ell=7.5\\) m、\\(\\Delta t=1\\) s、\\(v_{\\max}=5\\)），\\(\\rho_c\\) 为 22 veh/km，最大流量 3000 veh/h，高于真实单车道，因为 \\(p=0\\) 的车跟车时没有反应时间。</p>
    <p>\\(p&gt;0\\) 时没有精确解。随机减速把自由流速度降到约 \\(v_{\\max}-p\\)，并不断产生小扰动，由规则 2 向后传递。最大流量下降，峰值移向更低的密度，形状也变圆：不再有尖锐的阈值。这种转变是否仍像相变，正是环路实验要检验的问题：比较不同环路长度下拥堵比例的涨落。</p>`,
  "model.nasch.parameters": `
    <h2>参数</h2>
    <div class='table-wrap'><table class='model-table'>
      <thead><tr><th>符号</th><th>SUMO 设置</th><th>本页取值</th><th>含义</th></tr></thead>
      <tbody>
        <tr><td>\\(\\ell,\\ \\Delta t\\)</td><td><code>accel="7.5"</code>，<code>step-length="1"</code></td><td>7.5 m，1 s</td><td>格长和时间步长；1 格/步 = 7.5 m/s = 27 km/h。</td></tr>
        <tr><td>\\(v_{\\max}\\)</td><td><code>maxSpeed</code> = \\(7.5\\,v_{\\max}\\) m/s</td><td>5 格/步</td><td>自由流速度；决定 \\(\\rho_c=1/(v_{\\max}+1)\\)。</td></tr>
        <tr><td>\\(p\\)</td><td><code>sigma</code></td><td>0.25</td><td>随机减速概率。SUMO 默认值为 0.5，必须显式设置。</td></tr>
        <tr><td>车辆</td><td><code>length="7.5"</code>，<code>minGap="0"</code></td><td>1 格</td><td>一辆车占一格。</td></tr>
      </tbody>
    </table></div>`,
  "model.nasch.sumo": `
    <h2>在 SUMO 中</h2>
    <p>SUMO 1.28.0 内置 NaSch（<code>carFollowModel="NaSch"</code>）。它在 SUMO 的连续道路上执行同样的四条规则：速度向下取整为整数格/步，下一步速度只受间距限制，<code>sigma</code> 是随机减速概率。格长由 <code>accel</code> 决定：加速一步正好走一格。</p>
    <p>按上表设置后与原版模型一致：\\(p=0\\) 时平均速度等于精确解（检验记录见 <code>sumo/version.txt</code>）。有两种情况会破坏一致性：车辆初始位置不在格点上；<code>speedDev</code> 或 <code>speedFactor</code> 保持 SUMO 默认值，使每辆车有各自的最高速度。</p>`,
  "model.nasch.reference": `
    <h2>延伸阅读</h2>
    <ul>
      <li>K. Nagel 和 M. Schreckenberg（1992），<em>A cellular automaton model for freeway traffic</em>，Journal de Physique I，2，2221–2229。<a href='https://doi.org/10.1051/jp1:1992277'>doi:10.1051/jp1:1992277</a></li>
      <li>D. Chowdhury、L. Santen 和 A. Schadschneider（2000），<em>Statistical physics of vehicular traffic and some related systems</em>，Physics Reports，329，199–329。NaSch 及其变体的综述。</li>
    </ul>`,

  "model.ovm.meta": "OVM 最优速度模型 · 交通建模",
  "model.ovm.tag": "连续 · 确定性 · 跟车模型",
  "model.ovm.title": "最优速度模型（OVM）",
  "model.ovm.lede": "司机根据与前车的间距判断「该开多快」，再逐渐把速度调整过去。不需要任何随机性：只要司机反应太慢，均匀车流就会自己变成走走停停。",
  "model.ovm.rule": `
    <h2>规则</h2>
    <p>位置和速度都是连续的。车辆只看一个量：到前车的净间距 \\(s_i\\)，即本车车头到前车车尾的距离，单位 m。最优速度函数 \\(V(s)\\) 给出这个间距下该开的速度，车辆以速率 \\(\\alpha\\) 向它调整：</p>
    <div class='eq-math'>\\[\\frac{dx_i}{dt}=v_i,\\qquad \\frac{dv_i}{dt}=\\alpha\\,\\bigl[V(s_i)-v_i\\bigr]\\]
    \\[V(s)=v_{\\max}\\,\\frac{\\tanh\\bigl((s-s_c)/d\\bigr)+\\tanh(s_c/d)}{1+\\tanh(s_c/d)}\\]</div>
    <ul>
      <li>\\(V(0)=0\\)：没有间距时想停下；间距很大时 \\(V\\to v_{\\max}\\)。</li>
      <li>\\(s_c\\) 是曲线最陡的位置，\\(d\\) 决定过渡区的宽度。在 \\(s_c\\) 附近，间距的一点变化就要求速度大幅变化。</li>
      <li>\\(\\alpha\\) 的单位是 s\\(^{-1}\\)，\\(1/\\alpha\\) 是松弛时间：实际速度与目标速度之差每过 \\(1/\\alpha\\) 秒缩小为原来的 \\(1/e\\)。它不是反应延迟，但作用类似：车辆总是慢半拍地追随目标。</li>
    </ul>
    <p>OVM 只用间距，不看前车速度。即使前车急刹，后车也要等间距真正缩小后才减速。这就是 OVM 中车辆会碰撞的原因。</p>
    <p>「最优」只是函数 \\(V\\) 的名字，并不表示有人在做优化。Bando 等人用含车长的车头间距和无量纲单位；我们的实现和本页统一使用净间距 \\(s\\) 和国际单位。</p>`,
  "model.ovm.look": `
    <h2>观察要点</h2>
    <ol class='experiment-list'>
      <li>
        <h3>低密度：扰动会消失</h3>
        <p>20 veh/km 时间距为 45 m，位于 \\(V(s)\\) 平坦的部分，所以 \\(V'(s_0)&lt;\\alpha/2\\)。10 s 时带描边的车突然停下；后面的车减速一辆比一辆少，车流恢复。</p>
        <button type='button' class='btn' data-preset='ovm-stable'>载入</button>
      </li>
      <li>
        <h3>中等密度：没有随机性也会堵</h3>
        <p>50 veh/km 时间距为 15 m，正是 \\(V(s)\\) 最陡的地方，所以 \\(V'(s_0)&gt;\\alpha/2\\)。车辆起初等距排列，位置只有 0.5 m 的抖动。不用按任何按钮，约一分钟后抖动就长成向后传播的走走停停波，即时空图中的深色带。同时观察「最小间距」：它会变成负数，因为 OVM 中的车辆会碰撞。</p>
        <button type='button' class='btn' data-preset='ovm-unstable'>载入</button>
      </li>
      <li>
        <h3>反应更快：不再拥堵</h3>
        <p>同样的密度，取 \\(\\alpha=2.5\\ \\mathrm{s^{-1}}\\)。这时 \\(\\alpha/2\\) 大于 \\(V\\) 的最大斜率，基本图上的失稳区消失，停下的车只造成短暂的减速。慢慢降低 \\(\\alpha\\)，可以看到失稳区逐渐展开。</p>
        <button type='button' class='btn' data-preset='ovm-alpha'>载入</button>
      </li>
    </ol>`,
  "model.ovm.theory": `
    <h2>均匀车流为什么会失稳</h2>
    <p>当所有间距都等于 \\(s_0=L/N-\\ell\\)、所有速度都等于 \\(V(s_0)\\) 时，没有车加速：均匀车流是方程的解。它能否维持，取决于一个连锁反应。前车稍微减速，后车间距缩小 \\(\\Delta s\\)，目标速度随之下降 \\(V'(s_0)\\,\\Delta s\\)。后车需要约 \\(1/\\alpha\\) 秒才能达到新目标；到那时间距已经缩得更多，它只好比前车刹得更狠。每辆车传给后车的扰动都比自己收到的大。</p>
    <p>对小的间距扰动 \\(y_n=s_n-s_0\\) 线性化，得到 \\(\\ddot y_n+\\alpha\\dot y_n=\\alpha V'(s_0)(y_{n+1}-y_n)\\)。对沿车队的长波扰动，扰动增长的条件是</p>
    <div class='eq-math'>\\[V'(s_0)&gt;\\frac{\\alpha}{2}\\]</div>
    <p>\\(V'\\) 衡量间距变化要求速度变化多少；\\(\\alpha/2\\) 衡量司机能多快跟上。\\(V'\\) 在 \\(s=s_c\\) 处最大（本页参数下为 1.13 s\\(^{-1}\\)），所以失稳的密度集中在 \\(s_0=s_c\\) 附近的一个区间；\\(\\alpha&gt;2.26\\ \\mathrm{s^{-1}}\\) 时所有密度都稳定。这个区间就是演示中的阴影部分。</p>
    <p>这个结论有两点限制：它是长波判据，有限环路和有限步长会让阈值略有移动（<code>src/traffic_project/ovm.py</code> 中的 <code>growth_rate</code> 给出精确增长率）；它也只说明扰动是否开始增长，扰动变大后，波会稳定成持续的走走停停。</p>`,
  "model.ovm.parameters": `
    <h2>参数</h2>
    <div class='table-wrap'><table class='model-table'>
      <thead><tr><th>符号</th><th>SUMO 属性</th><th>本页取值</th><th>含义</th></tr></thead>
      <tbody>
        <tr><td>\\(\\alpha\\)</td><td><code>alpha</code></td><td>1.0 s\\(^{-1}\\)</td><td>敏感度；\\(1/\\alpha\\) 为松弛时间。</td></tr>
        <tr><td>\\(v_{\\max}\\)</td><td><code>maxSpeed</code></td><td>25 m/s</td><td>大间距时的速度。</td></tr>
        <tr><td>\\(s_c\\)</td><td><code>sc</code></td><td>18 m</td><td>\\(V\\) 最陡处的间距。</td></tr>
        <tr><td>\\(d\\)</td><td><code>d</code></td><td>11.6 m</td><td>过渡区宽度；\\(d\\) 越小，\\(V\\) 越陡。</td></tr>
        <tr><td>\\(\\ell\\)</td><td><code>length</code></td><td>5 m</td><td>车长。</td></tr>
      </tbody>
    </table></div>
    <p class='caption'>取自 <code>sumo/ovm/check_ovm.py</code> 的检验参数，不是标定值。</p>`,
  "model.ovm.sumo": `
    <h2>在 SUMO 中</h2>
    <p>SUMO 没有内置 OVM，我们自己加入了 <code>carFollowModel="OVM"</code>（<code>sumo/ovm/</code>，属性为 <code>alpha</code>、<code>sc</code>、<code>d</code>）。每个长度为 \\(\\Delta t\\) 的步长内，它计算 \\(v'=\\max\\bigl(0,\\ v+\\Delta t\\,\\alpha[V(s)-v]\\bigr)\\)，再计算 \\(x'=x+\\Delta t\\,v'\\)；没有加速度限制，也允许碰撞。\\(s\\) 是 SUMO 的间距，已扣除 <code>minGap</code>。演示使用同样的更新方式，\\(\\Delta t=0.1\\) s，所以它显示的就是 SUMO 的行为，包括车辆重叠。</p>
    <p>步长会改变结果：\\(\\Delta t=1\\) s、\\(\\alpha=1\\) 时更新变成 \\(v'=V(s)\\)，慢半拍的效应消失，大部分失稳也随之消失。因此 OVM 的模拟使用 0.1 s 步长。</p>`,
  "model.ovm.reference": `
    <h2>延伸阅读</h2>
    <ul>
      <li>M. Bando、K. Hasebe、A. Nakayama、A. Shibata 和 Y. Sugiyama（1995），<em>Dynamical model of traffic congestion and numerical simulation</em>，Physical Review E，51，1035–1042。<a href='https://doi.org/10.1103/PhysRevE.51.1035'>doi:10.1103/PhysRevE.51.1035</a></li>
      <li>Y. Sugiyama 等（2008），<em>Traffic jams without bottlenecks: experimental evidence for the physical mechanism of the formation of a jam</em>，New Journal of Physics，10，033001。真实车辆在环路上的实验，与演示的设置相同。<a href='https://doi.org/10.1088/1367-2630/10/3/033001'>doi:10.1088/1367-2630/10/3/033001</a></li>
    </ul>`,

  "model.idm.meta": "IDM 智能驾驶员模型 · 交通建模",
  "model.idm.tag": "连续 · 确定性 · 跟车模型",
  "model.idm.title": "智能驾驶员模型（IDM）",
  "model.idm.lede": "车辆向期望速度加速；当间距小于想要的间距时刹车，而想要的间距随车速和接近前车的快慢增大。一个平滑的公式同时描述自由行驶、跟车和刹车。车辆不会碰撞，但均匀车流仍然可能失稳。",
  "model.idm.rule": `
    <h2>规则</h2>
    <p>位置和速度都是连续的。车辆看三个量：自身速度 \\(v\\)、到前车的净间距 \\(s\\)，以及接近速度 \\(\\Delta v=v-v_{\\text{前车}}\\)（正在追近时为正）：</p>
    <div class='eq-math'>\\[\\frac{dv}{dt}=a\\left[1-\\Bigl(\\frac{v}{v_0}\\Bigr)^{\\delta}-\\Bigl(\\frac{s^*(v,\\Delta v)}{s}\\Bigr)^{2}\\right],\\qquad s^*=s_0+\\max\\Bigl(0,\\ vT+\\frac{v\\,\\Delta v}{2\\sqrt{ab}}\\Bigr)\\]</div>
    <ul>
      <li><strong>自由行驶项</strong> \\(a[1-(v/v_0)^\\delta]\\)：空路上车辆以约 \\(a\\) 的加速度加速，并在期望速度 \\(v_0\\) 处稳定下来。</li>
      <li><strong>相互作用项</strong> \\(-a(s^*/s)^2\\)：实际间距 \\(s\\) 小于期望间距 \\(s^*\\) 时刹车，远大于 \\(s^*\\) 时几乎不起作用。</li>
      <li><strong>期望间距</strong> \\(s^*\\)：停车时为 \\(s_0\\)，行驶时再加上以速度 \\(v\\) 行驶 \\(T\\) 秒的距离，正在追近时还要再加一项。最后这一项让车辆在接近慢车时<em>提前</em>刹车。</li>
    </ul>
    <p>接近速度是 IDM 与 OVM 的区别：前车一减速，IDM 的车就有反应，而不是等到间距缩小。正常接近时刹车减速度约为舒适减速度 \\(b\\)，紧急时会更大。这就是 IDM 中车辆不会碰撞的原因。</p>
    <p>均匀车流中 \\(\\Delta v=0\\)、加速度为零，由此得到每个速度对应的平衡间距：\\(s_e(v)=(s_0+vT)/\\sqrt{1-(v/v_0)^\\delta}\\)。低速时约为 \\(s_0+vT\\)：间距随速度线性增加，\\(T\\) 就是车头时距。</p>`,
  "model.idm.look": `
    <h2>观察要点</h2>
    <ol class='experiment-list'>
      <li>
        <h3>低密度：停下的车被消化</h3>
        <p>20 veh/km 时，带描边的车在 10 s 停下。后面的车提前、平缓地刹车，停下的车以约 \\(a\\) 的加速度重新起步，扰动逐渐消失。</p>
        <button type='button' class='btn' data-preset='idm-free'>载入</button>
      </li>
      <li>
        <h3>中等密度：不会消失的波</h3>
        <p>50 veh/km 时，同样的停车形成一个以约 15 km/h 向后传播的拥堵，与真实高速公路上 15–20 km/h 的拥堵波接近，而且一直不消失。观察「最小间距」：它始终保持几米；与 OVM 不同，IDM 的车能及时刹住。（如果不让车停下，起始的 0.5 m 抖动也会长成波，但需要几分钟。）</p>
        <button type='button' class='btn' data-preset='idm-stop'>载入</button>
      </li>
      <li>
        <h3>加速度更大：车流稳定</h3>
        <p>取 \\(a=2\\ \\mathrm{m/s^2}\\) 时，车辆离开拥堵足够快，能在下一辆车到来之前跟上前车：扰动消失，基本图上的失稳区也消失。把 \\(a\\) 拖到 0.5，可以看到失稳区变宽。</p>
        <button type='button' class='btn' data-preset='idm-strong'>载入</button>
      </li>
    </ol>`,
  "model.idm.theory": `
    <h2>均匀车流为什么会失稳</h2>
    <p>每个间距 \\(s\\) 对应一个平衡速度 \\(v_e(s)\\)，即 \\(s_e(v)\\) 的反函数。密度为 \\(k=1000/(s+\\ell)\\) veh/km 时，均匀车流的流量为 \\(q=3.6\\,k\\,v_e\\) veh/h，即演示中的灰色曲线。</p>
    <p>对任意跟车规则 \\(dv/dt=f(s,v,\\Delta v)\\)，稳定性由平衡点处的三个偏导数决定。长波扰动不增长的条件是（Wilson 和 Ward，2011）</p>
    <div class='eq-math'>\\[f_s\\le\\frac{f_v^2}{2}+f_{\\Delta v}\\,f_v\\]</div>
    <p>\\(f_s&gt;0\\) 表示间距变化对加速度的影响有多强；\\(f_v^2/2\\) 是向目标速度松弛带来的阻尼；\\(f_{\\Delta v}f_v&gt;0\\) 是对接近速度作出反应带来的额外阻尼。对 OVM，\\(f=\\alpha[V(s)-v]\\)，有 \\(f_s=\\alpha V'\\)、\\(f_v=-\\alpha\\)、\\(f_{\\Delta v}=0\\)，条件化为 \\(V'\\le\\alpha/2\\)。IDM 多了额外阻尼项，但当 \\(a\\) 较小或 \\(T\\) 较短时，间距项仍然占上风。演示在每个密度上数值计算这个条件，画出失稳区。</p>
    <p>与 OVM 一样，这是针对小扰动的长波判据；有限环路、有限步长和大扰动（例如一辆车停下）都可能表现不同。</p>`,
  "model.idm.parameters": `
    <h2>参数</h2>
    <div class='table-wrap'><table class='model-table'>
      <thead><tr><th>符号</th><th>SUMO 属性</th><th>本页取值</th><th>含义</th></tr></thead>
      <tbody>
        <tr><td>\\(v_0\\)</td><td><code>maxSpeed</code></td><td>30 m/s</td><td>期望速度。</td></tr>
        <tr><td>\\(T\\)</td><td><code>tau</code></td><td>1.5 s</td><td>期望车头时距；\\(T\\) 越大，间距越大。</td></tr>
        <tr><td>\\(s_0\\)</td><td><code>minGap</code></td><td>2 m</td><td>停车时的间距。</td></tr>
        <tr><td>\\(a\\)</td><td><code>accel</code></td><td>1.0 m/s²</td><td>最大加速度。</td></tr>
        <tr><td>\\(b\\)</td><td><code>decel</code></td><td>1.5 m/s²</td><td>舒适减速度；不是硬上限。</td></tr>
        <tr><td>\\(\\delta\\)</td><td><code>delta</code></td><td>4</td><td>接近 \\(v_0\\) 时加速度减小的快慢。</td></tr>
        <tr><td>\\(\\ell\\)</td><td><code>length</code></td><td>5 m</td><td>车长。</td></tr>
      </tbody>
    </table></div>
    <p class='caption'>取自 <code>configs/ring/idm_sweep.toml</code>，目前仍是占位值。</p>`,
  "model.idm.sumo": `
    <h2>在 SUMO 中</h2>
    <p>SUMO 内置 IDM（<code>carFollowModel="IDM"</code>），\\(s_0\\) 由 <code>minGap</code> 给出。每个长度为 \\(\\Delta t\\) 的步长被分成若干个 0.25 s 的子步（\\(\\Delta t=1\\) s 时为 4 个），子步中假设前车速度不变，然后计算 \\(x'=x+\\Delta t\\,v'\\)。演示以同样方式实现，取环路实验的步长 \\(\\Delta t=1\\) s，与我们的 SUMO 环路扫描结果（<code>results/ring/idm_sweep.csv</code>）相差约 1%。</p>
    <p>步长会改变结果：同样的参数在 \\(\\Delta t=0.1\\) s 时明显更稳定。环路实验还设置了 <code>speedDev="0"</code> 和 <code>speedFactor="1"</code>，使所有车辆的 \\(v_0\\) 相同。</p>`,
  "model.idm.reference": `
    <h2>延伸阅读</h2>
    <ul>
      <li>M. Treiber、A. Hennecke 和 D. Helbing（2000），<em>Congested traffic states in empirical observations and microscopic simulations</em>，Physical Review E，62，1805–1824。<a href='https://doi.org/10.1103/PhysRevE.62.1805'>doi:10.1103/PhysRevE.62.1805</a></li>
      <li>M. Treiber 和 A. Kesting（2013），<em>Traffic Flow Dynamics</em>，Springer。涵盖 IDM、OVM 和车队稳定性的教材；交互模拟见 <a href='https://traffic-simulation.de/'>traffic-simulation.de</a>。</li>
      <li>R. E. Wilson 和 J. A. Ward（2011），<em>Car-following models: fifty years of linear stability analysis – a mathematical perspective</em>，Transportation Planning and Technology，34，3–18。</li>
    </ul>`
});
