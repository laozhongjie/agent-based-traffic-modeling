(function () {
  "use strict";
  const root = document.getElementById("model-viz");
  if (!root) return;
  const model = root.dataset.model;
  const values = model === "nasch" ? { speed: 3, gap: 2, probability: 0.3 }
    : model === "ovm" ? { headway: 25, speed: 10, sensitivity: 0.6 }
      : { gap: 35, speed: 20, leader: 16, headway: 1.5 };
  let randomDraw = 0.23;
  let seed = 5253;
  const text = (en, zh) => window.Site.lang === "zh" ? zh : en;
  const number = (value, digits = 1) => value.toFixed(digits);

  function control(key, label, min, max, step, unit, digits = 1) {
    return `<label for="viz-${key}">${label}<output for="viz-${key}" data-value="${key}" data-unit="${unit}" data-digits="${digits}"></output>
      <input id="viz-${key}" data-control="${key}" type="range" min="${min}" max="${max}" step="${step}" value="${values[key]}"></label>`;
  }

  function figure(key, label) {
    return `<figure><figcaption>${label}</figcaption><div data-figure="${key}"></div></figure>`;
  }

  function svg(width, height, label, content) {
    return `<svg class="viz-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="${label}"><title>${label}</title>${content}</svg>`;
  }

  function makePlot(key, config) {
    const container = root.querySelector(`[data-figure="${key}"]`);
    const width = Math.max(240, container.clientWidth);
    const height = 245;
    const left = Math.max(52, Math.max(number(config.yMin, config.yDigits ?? 1).length, number(config.yMax, config.yDigits ?? 1).length) * 7 + 16);
    const right = width - 18;
    const top = 32;
    const bottom = height - 48;
    const scaleX = value => left + (value - config.xMin) / (config.xMax - config.xMin) * (right - left);
    const scaleY = value => bottom - (value - config.yMin) / (config.yMax - config.yMin) * (bottom - top);
    let content = `<text x="${left}" y="16">${config.yLabel}</text>`;
    for (let tick = 0; tick <= 3; tick++) {
      const xValue = config.xMin + tick * (config.xMax - config.xMin) / 3;
      const yValue = config.yMin + tick * (config.yMax - config.yMin) / 3;
      const xPosition = scaleX(xValue);
      const yPosition = scaleY(yValue);
      content += `<line class="viz-gridline" x1="${left}" y1="${yPosition}" x2="${right}" y2="${yPosition}"/>
        <text x="${left - 8}" y="${yPosition + 4}" text-anchor="end">${number(yValue, config.yDigits ?? 1)}</text>
        <text x="${xPosition}" y="${bottom + 20}" text-anchor="${tick === 0 ? "start" : tick === 3 ? "end" : "middle"}">${number(xValue, config.xDigits ?? 0)}</text>`;
    }
    content += `<path class="viz-axis" fill="none" d="M${left} ${top}V${bottom}H${right}"/>
      <text x="${(left + right) / 2}" y="${height - 4}" text-anchor="middle">${config.xLabel}</text>`;
    if (config.reference != null) {
      const yPosition = scaleY(config.reference);
      content += `<line class="viz-reference" x1="${left}" y1="${yPosition}" x2="${right}" y2="${yPosition}"/>`;
    }
    const samples = Array.from({ length: 121 }, (_, index) => {
      const xValue = config.xMin + index * (config.xMax - config.xMin) / 120;
      return `${index === 0 ? "M" : "L"}${scaleX(xValue)} ${scaleY(config.evaluate(xValue))}`;
    });
    content += `<path class="viz-curve" d="${samples.join(" ")}"/>`;
    if (config.selected != null) {
      const xPosition = scaleX(config.selected);
      const yPosition = scaleY(config.evaluate(config.selected));
      content += `<line class="viz-reference" x1="${xPosition}" y1="${bottom}" x2="${xPosition}" y2="${yPosition}"/>
        <circle class="viz-dot" cx="${xPosition}" cy="${yPosition}" r="5"><title>${config.xLabel}: ${number(config.selected)}, ${config.yLabel}: ${number(config.evaluate(config.selected))}</title></circle>`;
    }
    container.innerHTML = svg(width, height, config.label, content);
  }

  function road(distance, netGap) {
    const container = root.querySelector('[data-figure="road"]');
    const width = Math.max(240, container.clientWidth);
    const start = 24;
    const scale = (width - 48) / 90;
    const vehicleWidth = 5 * scale;
    const leaderPosition = start + (distance + (netGap ? 5 : 0)) * scale;
    const measureStart = start + vehicleWidth;
    const measureEnd = netGap ? leaderPosition : leaderPosition + vehicleWidth;
    const content = `<line class="viz-axis" x1="8" y1="87" x2="${width - 8}" y2="87"/>
      <rect class="viz-car" x="${start}" y="46" width="${vehicleWidth}" height="28" rx="3"/>
      <rect class="viz-leader" x="${leaderPosition}" y="46" width="${vehicleWidth}" height="28" rx="3"/>
      <text x="${start}" y="108">${text("Follower i", "后车 i")}</text>
      <text x="${Math.max(90, leaderPosition + vehicleWidth)}" y="36" text-anchor="end">${text("Leader i+1", "前车 i+1")}</text>
      <line class="viz-axis" x1="${measureStart}" y1="134" x2="${measureEnd}" y2="134"/>
      <path class="viz-axis" d="M${measureStart} 128V140M${measureEnd} 128V140"/>
      <text x="${width / 2}" y="160" text-anchor="middle">${netGap ? "s" : "h"} = ${number(distance)} m · ${text("direction →", "行驶方向 →")}</text>`;
    container.innerHTML = svg(width, 175, text("Vehicle spacing diagram", "车辆间距示意图"), content);
  }

  function renderNasch() {
    const accelerated = Math.min(values.speed + 1, 5);
    const safeSpeed = Math.min(accelerated, values.gap);
    const braking = randomDraw < values.probability;
    const finalSpeed = braking ? Math.max(safeSpeed - 1, 0) : safeSpeed;
    const distanceUnit = text(finalSpeed === 1 ? "cell" : "cells", "格");
    const speeds = [accelerated, safeSpeed, finalSpeed, finalSpeed];
    root.querySelector(".viz-steps").innerHTML = [text("1. Accelerate", "1. 加速"), text("2. Keep a gap", "2. 间距限制"), text("3. Random braking", "3. 随机减速"), text("4. Move", "4. 移动")]
      .map((label, index) => `<li><strong>${label}</strong>${index === 3 ? text("Move", "前进") : "v ="} ${speeds[index]} ${index === 3 ? distanceUnit : text("cells/step", "格/步")}</li>`).join("");
    const container = root.querySelector('[data-figure="road"]');
    const width = Math.max(240, container.clientWidth);
    const cellWidth = (width - 16) / 12;
    let content = "";
    [0, 1].forEach(row => {
      const yPosition = 34 + row * 86;
      const follower = row === 0 ? 0 : finalSpeed;
      const leader = values.gap + 1;
      content += `<text x="8" y="${yPosition - 10}">${row === 0 ? text("Before the step", "更新前") : text("Follower after the step", "后车更新后")}</text>`;
      for (let index = 0; index < 12; index++) {
        const xPosition = 8 + index * cellWidth;
        const occupied = index === follower;
        content += `<rect class="${occupied ? "viz-occupied" : index === leader ? "viz-leader" : "viz-cell"}" x="${xPosition + 1}" y="${yPosition}" width="${cellWidth - 2}" height="28" rx="2"/>`;
        if (occupied || index === leader) content += `<text x="${xPosition + cellWidth / 2}" y="${yPosition + 19}" text-anchor="middle">${occupied ? "i" : "i+1"}</text>`;
      }
      content += `<text x="8" y="${yPosition + 49}">${row === 0 ? `g = ${values.gap} · ${text("empty cells ahead", "前方空格数")}` : `${text("Distance moved", "移动距离")} = ${finalSpeed} ${distanceUnit}`}</text>`;
    });
    container.innerHTML = svg(width, 180, text("NaSch cells before and after one follower update", "NaSch 后车单步更新前后的格子位置"), content);
    root.querySelector(".viz-result").textContent = text(
      `Random draw u ≈ ${number(randomDraw, 3)}; p = ${number(values.probability, 2)}. ${braking ? "Random braking is selected (u < p)." : "No random braking (u ≥ p)."} The follower moves ${finalSpeed} ${distanceUnit}.`,
      `随机数 u ≈ ${number(randomDraw, 3)}；p = ${number(values.probability, 2)}。${braking ? "本次触发随机减速（u < p）。" : "本次不触发随机减速（u ≥ p）。"}后车最终前进 ${finalSpeed} 格。`);
  }

  function optimalVelocity(headway) {
    return 30 / (1 + Math.tanh(25 / 8)) * (Math.tanh((headway - 25) / 8) + Math.tanh(25 / 8));
  }

  function renderOvm() {
    const target = optimalVelocity(values.headway);
    const acceleration = values.sensitivity * (target - values.speed);
    road(values.headway, false);
    makePlot("velocity", {
      xMin: 0, xMax: 60, yMin: 0, yMax: 32, yDigits: 0,
      xLabel: text("Headway h (m)", "车头间距 h（m）"), yLabel: "V(h) (m/s)",
      evaluate: optimalVelocity, selected: values.headway,
      label: text("Desired speed rises with headway", "期望速度随车头间距增大而上升")
    });
    makePlot("response", {
      xMin: 0, xMax: 8, yMin: 0, yMax: 32, yDigits: 0, xDigits: 1,
      xLabel: text("Time t (s)", "时间 t（s）"), yLabel: "v(t) (m/s)", reference: target,
      evaluate: time => target + (values.speed - target) * Math.exp(-values.sensitivity * time),
      label: text("Speed relaxes toward the fixed target", "实际速度趋向固定的期望速度")
    });
    root.querySelector(".viz-result").textContent = text(
      `V(h) = ${number(target)} m/s; current v = ${number(values.speed)} m/s. Initial acceleration = ${number(acceleration)} m/s² (${acceleration >= 0 ? "accelerating" : "braking"}). Relaxation time 1/α = ${number(1 / values.sensitivity)} s.`,
      `期望速度 V(h) = ${number(target)} m/s；当前速度 v = ${number(values.speed)} m/s。初始加速度为 ${number(acceleration)} m/s²（${acceleration >= 0 ? "加速" : "减速"}），松弛时间 1/α = ${number(1 / values.sensitivity)} s。`);
  }

  function renderIdm() {
    const targetGap = 2 + Math.max(0, values.speed * values.headway + values.speed * (values.speed - values.leader) / (2 * Math.sqrt(2)));
    const freeTerm = 1 - (values.speed / 30) ** 4;
    const evaluate = gap => freeTerm - (targetGap / gap) ** 2;
    const acceleration = evaluate(values.gap);
    road(values.gap, true);
    makePlot("acceleration", {
      xMin: 10, xMax: 80, yMin: Math.floor(Math.min(evaluate(10), -1)), yMax: 1,
      xLabel: text("Net gap s (m)", "净间距 s（m）"),
      yLabel: text("Acceleration (m/s²)", "加速度（m/s²）"),
      yDigits: 1, reference: 0, evaluate, selected: values.gap,
      label: text("Acceleration responds to the gap; below zero means braking", "加速度随净间距变化，低于零表示减速")
    });
    root.querySelector(".viz-result").textContent = text(
      `Closing speed Δv = ${number(values.speed - values.leader)} m/s; desired gap s* = ${number(targetGap)} m; actual gap s = ${number(values.gap)} m. Acceleration = ${number(acceleration, 2)} m/s² (${acceleration >= 0 ? "accelerating" : "braking"}).`,
      `接近速度 Δv = ${number(values.speed - values.leader)} m/s；期望间距 s* = ${number(targetGap)} m，实际净间距 s = ${number(values.gap)} m。加速度为 ${number(acceleration, 2)} m/s²（${acceleration >= 0 ? "加速" : "减速"}）。`);
    root.querySelector(".viz-terms").textContent = text(
      `Acceleration terms: free road ${number(freeTerm, 2)} − following ${number((targetGap / values.gap) ** 2, 2)} = ${number(acceleration, 2)} m/s².`,
      `加速度分解：自由道路项 ${number(freeTerm, 2)} − 跟车项 ${number((targetGap / values.gap) ** 2, 2)} = ${number(acceleration, 2)} m/s²。`);
  }

  function update() {
    root.querySelectorAll("[data-value]").forEach(output => {
      output.textContent = `${number(values[output.dataset.value], Number(output.dataset.digits))} ${output.dataset.unit}`;
    });
    if (model === "nasch") renderNasch();
    else if (model === "ovm") renderOvm();
    else renderIdm();
  }

  function build() {
    let title;
    let intro;
    let controls;
    let figures;
    let note;
    if (model === "nasch") {
      title = text("See the four rules in one step", "图解：四条规则如何完成一次更新");
      intro = text("Change the starting speed, empty cells and braking probability. Follow the speed through each rule, then compare the car's position.", "调整初始速度、前方空格数和减速概率，观察每条规则怎样改变速度，再看车辆最终移动到哪里。");
      controls = control("speed", text("Initial speed v", "初始速度 v"), 0, 5, 1, text("cells/step", "格/步"), 0)
        + control("gap", text("Empty cells g", "前方空格数 g"), 0, 8, 1, text("cells", "格"), 0)
        + control("probability", text("Slowdown probability p", "减速概率 p"), 0, 1, 0.05, "", 2);
      figures = `<ol class="viz-steps"></ol>${figure("road", text("One lane, one follower update →", "单车道上的后车单步更新 →"))}
        <button type="button" class="btn viz-action" data-action="draw">${text("Draw another random event", "重新抽取随机数")}</button>`;
      note = text("Illustration only. vmax = 5 cells/step. The leader's old position is shown as a reference; this isolates one follower update rather than simulating all cars. A fixed random sequence makes the demonstration reproducible.", "原理示意：最大速度为 5 格/步。前车位置保留在更新前，作为间距参考；这里仅演示后车的一步更新，不是所有车辆的完整模拟。固定随机序列便于重复查看。");
    } else if (model === "ovm") {
      title = text("See how headway sets the target speed", "图解：间距决定目标，敏感度决定响应");
      intro = text("Open the gap to raise the desired speed. Change the current speed to switch between acceleration and braking; increase sensitivity to reach the target faster.", "拉大车头间距，期望速度就会上升；调整当前速度，可看到加速或减速；提高敏感度，则更快接近期望速度。");
      controls = control("headway", text("Headway h", "车头间距 h"), 5, 60, 1, "m")
        + control("speed", text("Current speed v", "当前速度 v"), 0, 30, 1, "m/s")
        + control("sensitivity", text("Sensitivity α", "敏感度 α"), 0.2, 3, 0.1, "s⁻¹");
      figures = figure("road", text("Headway is measured from front to front", "车头间距：两车相同参考点之间的距离"))
        + `<div class="viz-plots">${figure("velocity", text("Desired-speed curve · dot = selected headway", "期望速度曲线 · 圆点为所选间距"))}${figure("response", text("Speed response · dashed line = target", "速度响应 · 虚线为期望速度"))}</div>`;
      note = text("Illustration only. vmax = 30 m/s, hc = 25 m, d = 8 m, vehicle length = 5 m. The response curve holds headway fixed and uses the exact relaxation solution; it is not a multi-car simulation.", "原理示意：最大期望速度为 30 m/s，hc = 25 m，d = 8 m，车长为 5 m。响应曲线保持间距不变，使用松弛方程的精确解，不是多车模拟。");
    } else {
      title = text("See when following turns into braking", "图解：距离和接近速度如何触发制动");
      intro = text("Reduce the gap or increase your speed relative to the leader. Watch the desired gap grow and the acceleration move below zero.", "缩短净间距，或让本车比前车更快，观察期望间距怎样变化，以及加速度何时降到零以下。");
      controls = control("gap", text("Net gap s", "净间距 s"), 10, 80, 1, "m")
        + control("speed", text("Follower speed v", "本车速度 v"), 0, 30, 1, "m/s")
        + control("leader", text("Leader speed", "前车速度"), 0, 30, 1, "m/s")
        + control("headway", text("Desired time headway T", "期望时距 T"), 0.8, 2.5, 0.1, "s");
      figures = figure("road", text("Net gap excludes the length of the vehicle", "净间距：不包含车长的两车空隙"))
        + figure("acceleration", text("Acceleration versus gap · dot = current state", "加速度随间距变化 · 圆点为当前状态"))
        + '<p class="viz-terms"></p>';
      note = text("Illustration only. v0 = 30 m/s, s0 = 2 m, a = 1 m/s², b = 2 m/s², δ = 4, vehicle length = 5 m. The curve evaluates the raw IDM acceleration at fixed speeds; large negative values are not capped at comfortable braking b. This is not a trajectory or a SUMO result.", "原理示意：v0 = 30 m/s，s0 = 2 m，a = 1 m/s²，b = 2 m/s²，δ = 4，车长为 5 m。曲线在固定速度下计算 IDM 原始加速度；负值没有按舒适减速度 b 截断。这不是车辆轨迹或 SUMO 结果。");
    }
    root.innerHTML = `<h2 id="model-viz-title">${title}</h2><p class="viz-intro">${intro}</p>
      <div class="viz-controls">${controls}</div>${figures}<p class="viz-result" aria-live="polite"></p><p class="viz-note">${note}</p>`;
    update();
  }

  root.addEventListener("input", function (event) {
    const key = event.target.dataset.control;
    if (!key) return;
    values[key] = Number(event.target.value);
    update();
  });
  root.addEventListener("click", function (event) {
    if (!event.target.closest('[data-action="draw"]')) return;
    seed = (Math.imul(1664525, seed) + 1013904223) >>> 0;
    randomDraw = seed / 4294967296;
    update();
  });
  window.Site.onChange(build);
  build();
  let resizeFrame;
  const observer = new ResizeObserver(function () {
    cancelAnimationFrame(resizeFrame);
    resizeFrame = requestAnimationFrame(update);
  });
  observer.observe(root);
})();
