// Ring-road demo on each model page (#model-sim); buttons with data-preset load a set-up.
// The engine below has no DOM dependency so it can be checked in Node:
//   node -e 'const E = require("./docs/assets/model-sim.js"); ...'
// IDM follows SUMO's MSCFModel_IDM stepping (see idm.step).
// OVM uses the same update as sumo/ovm (and src/traffic_project/ovm.py): v' = max(0, v + dt*alpha*(V(s) - v)), x' = x + dt*v'.

(function () {
  "use strict";

  // ---------- engine ----------

  function makeRandom(seed) {
    let state = seed >>> 0 || 1;
    return () => (state = (Math.imul(1664525, state) + 1013904223) >>> 0) / 4294967296;
  }

  const MODELS = {
    nasch: {
      cell: 7.5, cells: 134, dt: 1, window: 300,
      defaults: { vmax: 5, p: 0.25 },
      get length() { return this.cells * this.cell; },
      maxDensity: 1000 / 7.5,
      init(sim) {
        // N distinct random cells, the usual NaSch start; vehicles start at rest
        const cells = Array.from({ length: this.cells }, (_, i) => i);
        for (let i = this.cells - 1; i > 0; i--) {
          const j = Math.floor(sim.random() * (i + 1));
          [cells[i], cells[j]] = [cells[j], cells[i]];
        }
        const chosen = cells.slice(0, sim.n).sort((a, b) => a - b);
        chosen.forEach((c, i) => { sim.x[i] = c; sim.v[i] = 0; });
      },
      step(sim) {
        const { n, x, v, params } = sim;
        const next = new Float64Array(n);
        for (let i = 0; i < n; i++) {
          const ahead = i === n - 1 ? x[0] + this.cells : x[i + 1];
          const gap = n === 1 ? Infinity : ahead - x[i] - 1;
          let speed = Math.min(v[i] + 1, params.vmax);
          speed = Math.min(speed, gap);
          if (speed > 0 && sim.random() < params.p) speed -= 1;
          next[i] = speed;
        }
        for (let i = 0; i < n; i++) { v[i] = next[i]; x[i] += next[i]; }
      },
      position(sim, i) { return (sim.x[i] % this.cells) * this.cell; },
      speed(sim, i) { return sim.v[i] * this.cell; },
      gap(sim, i) {
        const ahead = i === sim.n - 1 ? sim.x[0] + this.cells : sim.x[i + 1];
        return (ahead - sim.x[i] - 1) * this.cell;
      },
      vmax(params) { return params.vmax * this.cell; },
      // p = 0 exact fundamental diagram, in veh/km and veh/h (shown as a reference when p > 0)
      theory(params) {
        const points = [];
        for (let j = 0; j <= 200; j++) {
          const rho = j / 200;
          points.push([rho * 1000 / this.cell, Math.min(params.vmax * rho, 1 - rho) * 3600]);
        }
        return { curve: points, band: null, exact: params.p === 0 };
      }
    },

    ovm: {
      length: 1000, dt: 0.1, window: 300, carLength: 5,
      defaults: { alpha: 1, vmax: 25, sc: 18, d: 11.6 },
      maxDensity: 200,
      V(s, p) {
        const t = Math.tanh(p.sc / p.d);
        return p.vmax * (Math.tanh((s - p.sc) / p.d) + t) / (1 + t);
      },
      slope(s, p) {
        const t = Math.tanh(p.sc / p.d);
        const c = Math.cosh((s - p.sc) / p.d);
        return p.vmax / (p.d * (1 + t)) / (c * c);
      },
      uniformGap(n) { return this.length / n - this.carLength; },
      init(sim) {
        const s0 = this.uniformGap(sim.n);
        for (let i = 0; i < sim.n; i++) {
          sim.x[i] = i * this.length / sim.n + (sim.random() - 0.5) * 2 * sim.jitter;
          sim.v[i] = this.V(s0, sim.params);
        }
      },
      step(sim) {
        const { n, x, v, params, dt } = sim;
        const next = new Float64Array(n);
        for (let i = 0; i < n; i++) {
          const s = this.gap(sim, i);
          next[i] = Math.max(0, v[i] + dt * params.alpha * (this.V(s, params) - v[i]));
        }
        for (let i = 0; i < n; i++) { v[i] = next[i]; x[i] += dt * next[i]; }
      },
      position(sim, i) { return ((sim.x[i] % this.length) + this.length) % this.length; },
      speed(sim, i) { return sim.v[i]; },
      gap(sim, i) {
        const ahead = i === sim.n - 1 ? sim.x[0] + this.length : sim.x[i + 1];
        return sim.n === 1 ? Infinity : ahead - sim.x[i] - this.carLength;
      },
      vmax(params) { return params.vmax; },
      // uniform flow q = k V(s0) and the densities where V'(s0) > alpha/2
      theory(params) {
        const curve = [];
        let band = null;
        for (let k = 1; k <= this.maxDensity; k += 0.5) {
          const s = 1000 / k - this.carLength;
          curve.push([k, k * this.V(s, params) * 3.6]);
          if (this.slope(s, params) > params.alpha / 2) {
            band = band ? [band[0], k] : [k, k];
          }
        }
        return { curve, band, exact: true };
      },
      stability(n, params) {
        const s = this.uniformGap(n);
        return { slope: this.slope(s, params), limit: params.alpha / 2 };
      }
    },

    idm: {
      length: 1000, dt: 1, window: 300, carLength: 5,
      defaults: { v0: 30, T: 1.5, s0: 2, a: 1, b: 1.5, delta: 4 },
      maxDensity: 1000 / 7,
      accel(s, v, dv, p) {
        const star = p.s0 + Math.max(0, v * p.T + v * dv / (2 * Math.sqrt(p.a * p.b)));
        const gap = Math.max(s, 0.001);
        return p.a * (1 - Math.pow(v / p.v0, p.delta) - (star / gap) * (star / gap));
      },
      // equilibrium speed for gap s: 1 - (v/v0)^delta = ((s0 + vT)/s)^2
      equilibrium(s, p) {
        if (s <= p.s0) return 0;
        let lo = 0, hi = p.v0;
        for (let k = 0; k < 60; k++) {
          const mid = (lo + hi) / 2;
          if (this.accel(s, mid, 0, p) > 0) lo = mid; else hi = mid;
        }
        return lo;
      },
      uniformGap(n) { return this.length / n - this.carLength; },
      init(sim) {
        const s0 = this.uniformGap(sim.n);
        for (let i = 0; i < sim.n; i++) {
          sim.x[i] = i * this.length / sim.n + (sim.random() - 0.5) * 2 * sim.jitter;
          sim.v[i] = this.equilibrium(s0, sim.params);
        }
      },
      // As SUMO's MSCFModel_IDM::_v: the step is split into dt/0.25 s sub-steps (SUMO's default
      // stepping), the leader keeps its speed during the step, then x' = x + dt*v'.
      step(sim) {
        const { n, x, v, params, dt } = sim;
        const iterations = Math.max(1, Math.round(dt / 0.25));
        const next = new Float64Array(n);
        for (let i = 0; i < n; i++) {
          const lead = n === 1 ? v[i] : v[i === n - 1 ? 0 : i + 1];
          let gap = this.gap(sim, i);
          let speed = v[i];
          for (let k = 0; k < iterations; k++) {
            speed = Math.max(0, speed + dt / iterations * this.accel(gap, speed, speed - lead, params));
            gap -= Math.max(0, (speed - lead) * dt / iterations);
          }
          next[i] = speed;
        }
        for (let i = 0; i < n; i++) { v[i] = next[i]; x[i] += dt * next[i]; }
      },
      position(sim, i) { return ((sim.x[i] % this.length) + this.length) % this.length; },
      speed(sim, i) { return sim.v[i]; },
      gap(sim, i) {
        const ahead = i === sim.n - 1 ? sim.x[0] + this.length : sim.x[i + 1];
        return sim.n === 1 ? 1e6 : ahead - sim.x[i] - this.carLength;
      },
      vmax(params) { return params.v0; },
      // Linear (long-wavelength) string stability of a car-following law f(s, v, dv), dv = v - v_leader:
      // stable when f_v^2/2 + f_dv f_v - f_s >= 0. For OVM this is V'(s) <= alpha/2.
      margin(s, p) {
        const v = this.equilibrium(s, p);
        const h = 1e-4;
        const fs = (this.accel(s + h, v, 0, p) - this.accel(s - h, v, 0, p)) / (2 * h);
        const fv = (this.accel(s, v + h, 0, p) - this.accel(s, v - h, 0, p)) / (2 * h);
        const fdv = (this.accel(s, v, h, p) - this.accel(s, v, -h, p)) / (2 * h);
        return { fs, fv, fdv, value: fv * fv / 2 + fdv * fv - fs };
      },
      theory(params) {
        const curve = [];
        let band = null;
        for (let k = 1; k < this.maxDensity; k += 0.5) {
          const s = 1000 / k - this.carLength;
          curve.push([k, k * this.equilibrium(s, params) * 3.6]);
          if (this.margin(s, params).value < 0) band = band ? [band[0], k] : [k, k];
        }
        return { curve, band, exact: true };
      },
      stability(n, params) {
        const m = this.margin(this.uniformGap(n), params);
        return { slope: m.fs, limit: m.fv * m.fv / 2 + m.fdv * m.fv };
      }
    }
  };

  function densityToCount(model, k) {
    return Math.max(1, Math.round(k * model.length / 1000));
  }

  // OVM and IDM start as uniform flow with positions jittered by up to 0.5 m; NaSch starts at rest
  // on random cells. dt: step length in s (NaSch: always 1 s), default the model's.
  function createSim(name, params, n, seed, dt) {
    const model = MODELS[name];
    const sim = {
      name, model, n, dt: name === "nasch" ? 1 : dt || model.dt,
      params: Object.assign({}, params),
      x: new Float64Array(n), v: new Float64Array(n),
      time: 0, steps: 0, random: makeRandom(seed), jitter: 0.5
    };
    model.init(sim);
    return sim;
  }

  function step(sim) {
    sim.model.step(sim);
    sim.steps += 1;
    sim.time = sim.steps * sim.dt;
  }

  function measure(sim) {
    const { model, n } = sim;
    let sum = 0, minGap = Infinity, overlaps = 0;
    for (let i = 0; i < n; i++) {
      sum += model.speed(sim, i);
      const gap = model.gap(sim, i);
      if (gap < minGap) minGap = gap;
      if (gap < 0) overlaps += 1;
    }
    const density = n * 1000 / model.length;
    const meanSpeed = sum / n;
    return { density, meanSpeed, flow: density * meanSpeed * 3.6, minGap, overlaps };
  }

  const Engine = { MODELS, createSim, step, measure, densityToCount };
  if (typeof module !== "undefined" && module.exports) { module.exports = Engine; return; }
  window.ModelSim = Engine;


  // ---------- page ----------

  const root = document.getElementById("model-sim");
  if (!root) return;
  const name = root.dataset.model;
  const model = MODELS[name];
  const text = (en, zh) => window.Site.lang === "zh" ? zh : en;
  const fmt = (value, digits = 1) => Number.isFinite(value) ? value.toFixed(digits) : "–";

  // One adjustable parameter per model besides density.
  const UI = {
    nasch: { density: 20, kMax: 130, playback: 4, control: { key: "p", en: "Slowdown probability p", zh: "随机减速概率 p", min: 0, max: 0.6, step: 0.05, unit: "", digits: 2 } },
    ovm: { density: 50, kMax: 160, playback: 10, control: { key: "alpha", en: "Sensitivity α", zh: "敏感度 α", min: 0.3, max: 3, step: 0.05, unit: "s⁻¹", digits: 2 } },
    idm: { density: 50, kMax: 140, playback: 10, control: { key: "a", en: "Acceleration a", zh: "加速度 a", min: 0.3, max: 2.5, step: 0.1, unit: "m/s²", digits: 1 } }
  }[name];

  // stopAt: simulated time (s) at which the outlined car stops.
  const PRESETS = {
    "nasch-free": { density: 15, params: { p: 0 } },
    "nasch-ghost": { density: 20, params: { p: 0.25 } },
    "nasch-dense": { density: 45, params: { p: 0.25 } },
    "ovm-stable": { density: 20, stopAt: 10 },
    "ovm-unstable": { density: 50 },
    "ovm-alpha": { density: 50, params: { alpha: 2.5 }, stopAt: 10 },
    "idm-free": { density: 20, stopAt: 10 },
    "idm-stop": { density: 50, stopAt: 10 },
    "idm-strong": { density: 50, params: { a: 2 }, stopAt: 10 }
  };

  let params = Object.assign({}, model.defaults);
  let density = UI.density;
  let sim, history, flows, pendingStop = null;
  let running = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  let visible = true;
  let colors = null;
  let els = {};
  const carLength = model.carLength || model.cell;
  const xMax = Math.ceil(UI.kMax / 20) * 20;

  function reset() {
    sim = createSim(name, params, densityToCount(model, density), 1);
    sim.params = params; // the slider changes the running simulation
    history = [];
    flows = [];
    pendingStop = null;
    record();
  }

  function record() {
    const pos = new Float32Array(sim.n);
    const speed = new Float32Array(sim.n);
    const headway = new Float32Array(sim.n);
    for (let i = 0; i < sim.n; i++) {
      pos[i] = model.position(sim, i);
      speed[i] = model.speed(sim, i);
      headway[i] = Math.min(model.length, model.gap(sim, i) + carLength);
    }
    history.push({ pos, speed, headway });
    if (history.length > model.window) history.shift();
    flows.push(measure(sim).flow);
    if (flows.length > 60) flows.shift();
  }

  const averageFlow = () => flows.reduce((a, b) => a + b, 0) / flows.length;

  // ----- colours: speed is a magnitude, so one hue (jam red) from strong (stopped) to pale (vmax)

  function parseColor(value) {
    const v = value.trim();
    if (v.startsWith("#")) {
      const hex = v.length === 4 ? v.slice(1).split("").map(c => c + c).join("") : v.slice(1, 7);
      return [0, 2, 4].map(i => parseInt(hex.slice(i, i + 2), 16));
    }
    const m = v.match(/\d+(\.\d+)?/g);
    return m ? m.slice(0, 3).map(Number) : [128, 128, 128];
  }

  function readColors() {
    const style = getComputedStyle(document.documentElement);
    const get = key => parseColor(style.getPropertyValue(key));
    const jam = get("--jam"), surface = get("--surface");
    const dark = surface[0] + surface[1] + surface[2] < 3 * 128;
    const pale = jam.map((c, i) => Math.round(c + (surface[i] - c) * (dark ? 0.7 : 0.88)));
    const ramp = Array.from({ length: 64 }, (_, k) => jam.map((c, i) => Math.round(c + (pale[i] - c) * k / 63)));
    const pack = c => ((255 << 24) | (c[2] << 16) | (c[1] << 8) | c[0]) >>> 0;
    colors = {
      ramp, rampPacked: ramp.map(pack), surfacePacked: pack(surface), textPacked: pack(get("--text")),
      css: c => `rgb(${c[0]},${c[1]},${c[2]})`, text: get("--text"), road: get("--border")
    };
  }

  const speedIndex = speed => Math.round(Math.max(0, Math.min(1, speed / model.vmax(params))) * 63);

  // ----- drawing

  function drawRing() {
    const canvas = els.ring;
    const ratio = window.devicePixelRatio || 1;
    const size = Math.round(canvas.clientWidth * ratio);
    if (!size) return;
    if (canvas.width !== size) { canvas.width = size; canvas.height = size; }
    const ctx = canvas.getContext("2d");
    const centre = size / 2, radius = size * 0.4;
    ctx.clearRect(0, 0, size, size);
    ctx.lineWidth = size * 0.07;
    ctx.strokeStyle = colors.css(colors.road);
    ctx.beginPath(); ctx.arc(centre, centre, radius, 0, 2 * Math.PI); ctx.stroke();
    const dot = Math.max(2.5 * ratio, Math.min(5 * ratio, Math.PI * radius / sim.n * 0.8));
    for (let i = sim.n - 1; i >= 0; i--) {
      const angle = -Math.PI / 2 + model.position(sim, i) / model.length * 2 * Math.PI;
      ctx.fillStyle = colors.css(colors.ramp[speedIndex(model.speed(sim, i))]);
      ctx.beginPath(); ctx.arc(centre + radius * Math.cos(angle), centre + radius * Math.sin(angle), i === 0 ? dot * 1.5 : dot, 0, 2 * Math.PI); ctx.fill();
      if (i === 0) { ctx.lineWidth = 2 * ratio; ctx.strokeStyle = colors.css(colors.text); ctx.stroke(); }
    }
    ctx.fillStyle = colors.css(colors.text);
    ctx.textAlign = "center";
    ctx.font = `600 ${Math.round(15 * ratio)}px system-ui, sans-serif`;
    ctx.fillText(`t = ${fmt(sim.time, 0)} s`, centre, centre + 5 * ratio);
  }

  // Each car colours the road from its front up to its leader's front with its own speed, so the
  // diagram shows a speed field: jams are solid bands. The outlined car's path is drawn on top.
  function drawSpaceTime() {
    const canvas = els.spacetime;
    const width = canvas.width, height = canvas.height;
    const ctx = canvas.getContext("2d");
    const image = ctx.createImageData(width, height);
    const buffer = new Uint32Array(image.data.buffer);
    buffer.fill(colors.surfacePacked);
    const columnWidth = width / model.window;
    const offset = model.window - history.length;
    const fill = (column, position, length, colour) => {
      const x0 = Math.floor((offset + column) * columnWidth);
      const x1 = Math.floor((offset + column + 1) * columnWidth);
      const first = Math.floor(position / model.length * height);
      const rows = Math.max(1, Math.min(height, Math.ceil((position + length) / model.length * height) - first));
      for (let r = 0; r < rows; r++) {
        const y = height - 1 - (first + r) % height;
        for (let x = x0; x < x1; x++) buffer[y * width + x] = colour;
      }
    };
    history.forEach((sample, column) => {
      for (let i = 0; i < sample.pos.length; i++) {
        if (sample.headway[i] > 0) fill(column, sample.pos[i], sample.headway[i], colors.rampPacked[speedIndex(sample.speed[i])]);
      }
    });
    const mark = Math.max(2, Math.round(height / 120));
    history.forEach((sample, column) => fill(column, sample.pos[0], mark * model.length / height, colors.textPacked));
    ctx.putImageData(image, 0, 0);
  }

  // Axis from 0 to at least max in at most 7 round steps.
  function niceTicks(max) {
    const magnitude = Math.pow(10, Math.floor(Math.log10(max / 7)));
    const step = [1, 2, 2.5, 5, 10, 20].map(m => m * magnitude).find(s => Math.ceil(max / s) <= 7);
    const ticks = [];
    for (let y = 0; y < max + step - 1e-9; y += step) ticks.push(y);
    return { top: ticks[ticks.length - 1], ticks };
  }

  // Fundamental diagram: theory curve, linearly unstable band, and this run.
  function drawFd() {
    const box = els.fd;
    const width = Math.max(260, box.clientWidth);
    const height = 280;
    const left = 58, right = width - 16, top = 18, bottom = height - 46;
    const theory = model.theory(params);
    const curve = theory.curve.filter(p => p[0] <= xMax);
    const axis = niceTicks(Math.max(...curve.map(p => p[1])) * 1.02);
    const sx = k => left + k / xMax * (right - left);
    const sy = y => bottom - Math.min(y, axis.top) / axis.top * (bottom - top);
    let svg = "";
    axis.ticks.forEach(y => {
      svg += `<line class="viz-gridline" x1="${left}" x2="${right}" y1="${sy(y)}" y2="${sy(y)}"/>
        <text x="${left - 8}" y="${sy(y) + 4}" text-anchor="end">${fmt(y, 0)}</text>`;
    });
    for (let t = 0; t <= 4; t++) {
      const k = xMax * t / 4;
      svg += `<text x="${sx(k)}" y="${bottom + 18}" text-anchor="${t === 0 ? "start" : t === 4 ? "end" : "middle"}">${fmt(k, 0)}</text>`;
    }
    if (theory.band) {
      const [a, b] = theory.band;
      svg += `<rect class="sim-band" x="${sx(a)}" y="${top}" width="${Math.max(1, sx(Math.min(b, xMax)) - sx(a))}" height="${bottom - top}"/>
        <text class="sim-band-label" x="${(sx(a) + sx(Math.min(b, xMax))) / 2}" y="${top + 14}" text-anchor="middle">${text("unstable", "线性失稳")}</text>`;
    }
    const path = curve.map((p, i) => `${i ? "L" : "M"}${sx(p[0]).toFixed(1)} ${sy(p[1]).toFixed(1)}`).join("");
    svg += `<path class="sim-theory${theory.exact ? "" : " dashed"}" d="${path}"/>
      <circle class="sim-current" cx="0" cy="0" r="7"/>
      <path class="viz-axis" fill="none" d="M${left} ${top}V${bottom}H${right}"/>
      <text x="${left}" y="11">${text("Flow q (veh/h)", "流量 q（veh/h）")}</text>
      <text x="${(left + right) / 2}" y="${height - 6}" text-anchor="middle">${text("Density k (veh/km)", "密度 k（veh/km）")}</text>`;
    box.innerHTML = `<svg class="viz-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="${text("Fundamental diagram", "基本图")}">${svg}</svg>`;
    els.marker = { el: box.querySelector(".sim-current"), sx, sy };
    moveMarker();

    const theoryLabel = name === "nasch"
      ? (theory.exact ? text("exact result for p = 0", "p = 0 的精确解") : text("exact result for p = 0, for reference", "p = 0 的精确解（参考）"))
      : text("uniform flow (equilibrium)", "均匀流（平衡态）");
    let legend = `<li><span class="sim-key line${theory.exact ? "" : " dashed"}"></span>${theoryLabel}</li>`;
    if (theory.band) legend += `<li><span class="sim-key band"></span>${text("linearly unstable", "线性失稳区")} ${fmt(theory.band[0], 1)}–${fmt(theory.band[1], 1)} veh/km</li>`;
    else if (name !== "nasch") legend += `<li><span class="sim-key band"></span>${text("no linearly unstable density", "没有线性失稳的密度")}</li>`;
    legend += `<li><span class="sim-key current"></span>${text("this run, last 60 s", "当前模拟，最近 60 s")}</li>`;
    els.legend.innerHTML = legend;
  }

  function moveMarker() {
    if (!els.marker) return;
    els.marker.el.setAttribute("cx", els.marker.sx(density));
    els.marker.el.setAttribute("cy", els.marker.sy(averageFlow()));
  }

  function verdict() {
    if (name === "nasch") {
      const rho = sim.n / model.cells, critical = 1 / (params.vmax + 1);
      const head = `ρ = ${fmt(rho, 3)} ${rho <= critical ? "≤" : ">"} ρc = 1/(vmax+1) = ${fmt(critical, 3)}`;
      if (params.p !== 0) return `${head}. ${text("With p > 0 there is no exact result; ρc is only a reference.", "p > 0 时没有精确解，ρc 只作参考。")}`;
      return `${head} → ${rho <= critical ? text("free flow, q = vmax·ρ", "自由流，q = vmax·ρ") : text("congested, q = 1 − ρ", "拥堵，q = 1 − ρ")}`;
    }
    const s0 = model.uniformGap(sim.n);
    const st = model.stability(sim.n, params);
    const unstable = st.slope > st.limit;
    const result = unstable ? text("uniform flow is linearly unstable", "均匀流线性失稳") : text("uniform flow is linearly stable", "均匀流线性稳定");
    if (name === "ovm") return `s₀ = ${fmt(s0, 1)} m: V′(s₀) = ${fmt(st.slope, 2)} s⁻¹ ${unstable ? ">" : "≤"} α/2 = ${fmt(st.limit, 2)} s⁻¹ → ${result}`;
    return `s₀ = ${fmt(s0, 1)} m: f_s = ${fmt(st.slope, 3)} ${unstable ? ">" : "≤"} f_v²/2 + f_Δv·f_v = ${fmt(st.limit, 3)} → ${result}`;
  }

  function updateReadout() {
    const m = measure(sim);
    const minGap = name === "nasch" ? `${fmt(m.minGap / model.cell, 0)} ${text("cells", "格")}` : `${fmt(m.minGap, 1)} m`;
    const items = [
      [text("Density k", "密度 k"), `${fmt(density, 0)} veh/km · N = ${sim.n}`],
      [text("Mean speed", "平均车速"), `${fmt(m.meanSpeed, 1)} m/s · ${fmt(m.meanSpeed * 3.6, 0)} km/h`],
      [text("Flow q, last 60 s", "流量 q（最近 60 s）"), `${fmt(averageFlow(), 0)} veh/h`],
      [text("Smallest gap", "最小间距"), minGap + (m.overlaps ? text(` · ${m.overlaps} cars overlap`, ` · ${m.overlaps} 辆车重叠`) : "")]
    ];
    els.stats.innerHTML = items.map(([k, v]) => `<div><dt>${k}</dt><dd>${v}</dd></div>`).join("");
    els.stats.classList.toggle("sim-overlap", m.overlaps > 0);
    els.verdict.textContent = verdict();
    moveMarker();
  }

  function drawAll() {
    drawRing();
    drawSpaceTime();
    drawFd();
    updateReadout();
  }

  // ----- controls

  function slider(key, label, min, max, step, value, unit, digits) {
    return `<label>${label}<output data-out="${key}">${fmt(value, digits)}${unit ? " " + unit : ""}</output>
      <input type="range" data-key="${key}" min="${min}" max="${max}" step="${step}" value="${value}"></label>`;
  }

  function build() {
    const c = UI.control;
    root.innerHTML = `
      <h2 id="model-sim-title">${text("Ring-road demo", "环路演示")}</h2>
      <p class="viz-intro">${text(
        `Every car on this ${fmt(model.length, 0)} m ring follows the rule above and nothing else. The outlined car is the one that “Stop one car” brakes; its path is the thin line in the space–time diagram, whose colour shows the speed at each place and time.`,
        `这条 ${fmt(model.length, 0)} m 环路上的每辆车都只按上面的规则行驶。带描边的车就是「让一辆车停下」时被刹停的车，它的轨迹是时空图中那条细线；时空图的颜色表示每个时刻、每个位置上的车速。`)}</p>
      <div class="sim-layout">
        <figure class="sim-ring-fig"><figcaption>${text("Ring (clockwise)", "环路（顺时针行驶）")}</figcaption><canvas class="sim-ring" aria-label="${text("Cars on the ring, coloured by speed", "环路上的车辆，颜色表示车速")}"></canvas></figure>
        <figure class="sim-st-fig"><figcaption>${text("Space–time diagram: last 300 s; up = position along the ring", "时空图：最近 300 s；纵轴为环路上的位置")}</figcaption>
          <div class="sim-st-wrap"><canvas class="sim-st" width="600" height="300" aria-label="${text("Space–time diagram", "时空图")}"></canvas></div>
          <div class="sim-st-foot"><span>${text("time → now", "时间 → 现在")}</span>
            <span class="sim-scale"><span>0</span><span class="sim-ramp"></span><span>${fmt(model.vmax(params), 1)} m/s</span></span></div>
        </figure>
      </div>
      <div class="sim-actions">
        <button type="button" class="btn primary" data-act="play">${running ? text("Pause", "暂停") : text("Play", "播放")}</button>
        <button type="button" class="btn" data-act="reset">${text("Restart", "重新开始")}</button>
        <button type="button" class="btn" data-act="stop">${text("Stop one car", "让一辆车停下")}</button>
      </div>
      <dl class="sim-stats"></dl>
      <p class="sim-verdict"></p>
      <div class="viz-controls sim-controls">
        ${slider("density", text("Density k", "密度 k"), 5, UI.kMax, 1, density, "veh/km", 0)}
        ${slider(c.key, text(c.en, c.zh), c.min, c.max, c.step, params[c.key], c.unit, c.digits)}
      </div>
      <figure class="sim-fd-fig"><figcaption>${text("Fundamental diagram: flow against density", "基本图：流量与密度")}</figcaption>
        <div class="sim-fd"></div><ul class="sim-legend"></ul></figure>`;
    els = {
      ring: root.querySelector(".sim-ring"), spacetime: root.querySelector(".sim-st"),
      stats: root.querySelector(".sim-stats"), verdict: root.querySelector(".sim-verdict"),
      fd: root.querySelector(".sim-fd"), legend: root.querySelector(".sim-legend")
    };
    drawAll();
  }

  root.addEventListener("input", function (event) {
    const key = event.target.dataset.key;
    if (!key) return;
    const value = Number(event.target.value);
    const c = UI.control;
    if (key === "density") { density = value; reset(); }
    else params[key] = value;
    root.querySelector(`[data-out="${key}"]`).textContent = key === "density"
      ? `${fmt(value, 0)} veh/km` : `${fmt(value, c.digits)}${c.unit ? " " + c.unit : ""}`;
    drawAll();
  });

  root.addEventListener("click", function (event) {
    const button = event.target.closest("[data-act]");
    if (!button) return;
    const act = button.dataset.act;
    if (act === "play") {
      running = !running;
      button.textContent = running ? text("Pause", "暂停") : text("Play", "播放");
      return;
    }
    if (act === "reset") reset();
    else if (act === "stop") sim.v[0] = 0;
    drawAll();
  });

  document.addEventListener("click", function (event) {
    const button = event.target.closest("[data-preset]");
    const preset = button && PRESETS[button.dataset.preset];
    if (!preset) return;
    params = Object.assign({}, model.defaults, preset.params);
    density = preset.density;
    reset();
    pendingStop = preset.stopAt == null ? null : preset.stopAt;
    running = true;
    build();
    root.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
  });

  // ----- animation

  let last = null, owed = 0, lastReadout = 0;
  function frame(now) {
    requestAnimationFrame(frame);
    const elapsed = last === null ? 0 : Math.min(0.1, (now - last) / 1000);
    last = now;
    if (!running || !visible) return;
    owed += elapsed * UI.playback;
    const sampleEvery = Math.max(1, Math.round(1 / sim.dt));
    let sampled = false;
    while (owed >= sim.dt) {
      if (pendingStop !== null && sim.time >= pendingStop - 1e-9) { sim.v[0] = 0; pendingStop = null; }
      step(sim);
      owed -= sim.dt;
      if (sim.steps % sampleEvery === 0) { record(); sampled = true; }
    }
    drawRing();
    if (sampled) {
      drawSpaceTime();
      if (now - lastReadout > 250) { updateReadout(); lastReadout = now; }
    }
  }

  readColors();
  reset();
  build();
  window.Site.onChange(build);
  new IntersectionObserver(entries => { visible = entries[0].isIntersecting; }).observe(root);
  let resizeFrame;
  new ResizeObserver(() => {
    cancelAnimationFrame(resizeFrame);
    resizeFrame = requestAnimationFrame(() => { drawRing(); drawFd(); });
  }).observe(root);
  const recolour = () => { readColors(); drawAll(); };
  new MutationObserver(recolour).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", recolour);
  requestAnimationFrame(frame);
})();
