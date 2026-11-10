// City-network map: replays the trajectory clips in window.CLIPS on the roads in window.NETWORK.
// Data files come from scripts/city_clips.py (docs/data/network/); network.html loads them with
// <script defer> tags (GUIDE section 6, "Website files"). Without a clip the map placeholder stays.
// Speeds are worked out here from the clips' positions, in m/s, with km/h beside them as on the
// model pages; positions are rounded to 1 m, so a speed over one 1 s step is good to about 1 m/s.
(function () {
  "use strict";
  const box = document.querySelector('[data-results="map"]');
  const network = window.NETWORK || {};
  const clips = Object.entries(window.CLIPS || {})
    .map(([key, clip]) => ({ key, clip, roads: network["roads_" + clip.net] }))
    .filter((c) => c.roads)
    .sort((a, b) => a.clip.density_veh_km - b.clip.density_veh_km);
  if (!box || !clips.length) return;

  const text = (en, zh) => window.Site.lang === "zh" ? zh : en;
  const fmt = (value, digits = 1) => Number.isFinite(value) ? value.toFixed(digits) : "–";
  const PLAYBACK = 5;      // simulated seconds per second on screen
  const MAX_HEIGHT = 640;  // px; the Bugis net is taller than wide
  const LANE_M = 3.2;      // drawn width of one lane in m (SUMO's default lane width)

  // Colour scale top: the speed limit most roads of the net have (50 km/h in Bugis).
  function commonLimit(roads) {
    const counts = new Map();
    roads.edges.forEach((e) => counts.set(e.speed_kmh, (counts.get(e.speed_kmh) || 0) + 1));
    return [...counts].sort((a, b) => b[1] - a[1] || a[0] - b[0])[0][0];
  }

  // Absolute positions per frame (NaN while a car is missing, mid-teleport) and the speed of each
  // car's move into the frame. A car's first frame, or its first after a gap, has no move into it,
  // so it takes the speed of its next move.
  const decoded = new Map();
  function decode(entry) {
    if (decoded.has(entry.key)) return decoded.get(entry.key);
    const clip = entry.clip, n = clip.car_ids.length, frames = clip.frames.length;
    const pos = new Float32Array(frames * n * 2).fill(NaN);
    const speed = new Float32Array(frames * n).fill(NaN);
    const x = new Float64Array(n), y = new Float64Array(n), seen = new Uint8Array(n);
    clip.frames.forEach((frame, f) => {
      for (let i = 0; i < n; i++) {
        const dx = frame[2 * i], dy = frame[2 * i + 1];
        if (dx === null) continue;
        if (seen[i]) { x[i] += dx; y[i] += dy; } else { x[i] = dx; y[i] = dy; seen[i] = 1; }
        const at = f * n + i;
        pos[2 * at] = x[i];
        pos[2 * at + 1] = y[i];
        if (f > 0 && !Number.isNaN(pos[2 * (at - n)])) speed[at] = Math.hypot(dx, dy) / clip.step_s;
      }
    });
    for (let f = 0; f + 1 < frames; f++) {
      for (let i = 0; i < n; i++) {
        const at = f * n + i;
        if (Number.isNaN(speed[at]) && !Number.isNaN(pos[2 * at])) speed[at] = speed[at + n];
      }
    }
    const d = { n, frames, pos, speed, vTop: commonLimit(entry.roads) / 3.6 };
    decoded.set(entry.key, d);
    return d;
  }

  // ----- colours: as on the model pages' ring demo, one hue (jam red) from strong (stopped) to
  // pale (the colour scale's top), here less pale so that fast cars stay visible on the roads

  function parseColor(value) {
    const v = value.trim();
    if (v.startsWith("#")) {
      const hex = v.length === 4 ? v.slice(1).split("").map((c) => c + c).join("") : v.slice(1, 7);
      return [0, 2, 4].map((i) => parseInt(hex.slice(i, i + 2), 16));
    }
    const m = v.match(/\d+(\.\d+)?/g);
    return m ? m.slice(0, 3).map(Number) : [128, 128, 128];
  }

  let colors = null;
  function readColors() {
    const style = getComputedStyle(document.documentElement);
    const get = (key) => parseColor(style.getPropertyValue(key));
    const jam = get("--jam"), surface = get("--surface");
    const dark = surface[0] + surface[1] + surface[2] < 3 * 128;
    const pale = jam.map((c, i) => Math.round(c + (surface[i] - c) * (dark ? 0.55 : 0.72)));
    const css = (c) => `rgb(${c[0]},${c[1]},${c[2]})`;
    const ramp = Array.from({ length: 64 }, (_, k) => css(jam.map((c, i) => Math.round(c + (pale[i] - c) * k / 63))));
    colors = { ramp, unknown: css(get("--muted")), road: css(get("--border")), gradient: `linear-gradient(to right, ${css(jam)}, ${css(pale)})` };
  }

  const speedIndex = (speed, top) => Math.round(Math.max(0, Math.min(1, speed / top)) * 63);

  // ----- state

  let current = 0;      // index into clips
  let time = 0;         // frames since the clip's first, fractional while playing
  let running = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  let visible = true;
  let els = {}, view = null, roadLayer = null, shownFrame = -1;

  const entry = () => clips[current];
  const frameIndex = () => Math.floor(time + 1e-9);

  // ----- drawing

  // Fit the net's boundary into the card, at most MAX_HEIGHT tall; the roads go to a layer of their own.
  function layout() {
    const canvas = els.map;
    const [x0, y0, x1, y1] = entry().roads.boundary;
    const aspect = (x1 - x0) / (y1 - y0);
    const width = Math.floor(Math.min(els.mapWrap.clientWidth, MAX_HEIGHT * aspect));
    if (!width) return false;
    const height = Math.round(width / aspect);
    const ratio = window.devicePixelRatio || 1;
    canvas.style.width = width + "px";
    canvas.style.height = height + "px";
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);
    const pad = 6 * ratio;
    const scale = Math.min((canvas.width - 2 * pad) / (x1 - x0), (canvas.height - 2 * pad) / (y1 - y0));
    view = { ratio, scale, sx: (x) => pad + (x - x0) * scale, sy: (y) => canvas.height - pad - (y - y0) * scale };
    drawRoads();
    return true;
  }

  // Each road along lane 0's outline, as wide as its lanes (at least 1 px).
  function drawRoads() {
    roadLayer = roadLayer || document.createElement("canvas");
    roadLayer.width = els.map.width;
    roadLayer.height = els.map.height;
    const ctx = roadLayer.getContext("2d");
    ctx.clearRect(0, 0, roadLayer.width, roadLayer.height);
    ctx.strokeStyle = colors.road;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    entry().roads.edges.forEach((e) => {
      ctx.lineWidth = Math.max(view.ratio, e.lanes * LANE_M * view.scale);
      ctx.beginPath();
      e.shape.forEach(([x, y], j) => j ? ctx.lineTo(view.sx(x), view.sy(y)) : ctx.moveTo(view.sx(x), view.sy(y)));
      ctx.stroke();
    });
  }

  // Cars at the current time, moving in a straight line between frames. Each car is coloured by
  // the speed of the move under way; slow cars are drawn last, on top.
  function drawMap() {
    if (!view) return;
    const canvas = els.map, ctx = canvas.getContext("2d");
    const d = decode(entry());
    const f = frameIndex(), a = time - f, g = Math.min(f + 1, d.frames - 1);
    const moving = a > 1e-6 && g > f;
    const radius = Math.max(1.4 * view.ratio, 2.5 * view.scale);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(roadLayer, 0, 0);
    const bins = Array.from({ length: 65 }, () => []);   // 0-63 by speed, 64: speed unknown
    for (let i = 0; i < d.n; i++) {
      const at = f * d.n + i;
      if (Number.isNaN(d.pos[2 * at])) continue;
      const s = d.speed[(moving ? g : f) * d.n + i];
      bins[Number.isNaN(s) ? 64 : speedIndex(s, d.vTop)].push(i);
    }
    const order = [64].concat(Array.from({ length: 64 }, (_, k) => 63 - k));
    order.forEach((b) => {
      if (!bins[b].length) return;
      ctx.fillStyle = b === 64 ? colors.unknown : colors.ramp[b];
      ctx.beginPath();
      bins[b].forEach((i) => {
        const at = f * d.n + i, next = g * d.n + i;
        let x = d.pos[2 * at], y = d.pos[2 * at + 1];
        if (moving && !Number.isNaN(d.pos[2 * next])) {
          x += (d.pos[2 * next] - x) * a;
          y += (d.pos[2 * next + 1] - y) * a;
        }
        const px = view.sx(x), py = view.sy(y);
        ctx.moveTo(px + radius, py);
        ctx.arc(px, py, radius, 0, 2 * Math.PI);
      });
      ctx.fill();
    });
  }

  // Readout for the whole frame: the time, the cars on the map and their mean speed.
  function updateReadout() {
    const { clip } = entry(), d = decode(entry()), f = frameIndex();
    shownFrame = f;
    let cars = 0, sum = 0, counted = 0;
    for (let i = 0; i < d.n; i++) {
      const at = f * d.n + i;
      if (Number.isNaN(d.pos[2 * at])) continue;
      cars++;
      if (!Number.isNaN(d.speed[at])) { sum += d.speed[at]; counted++; }
    }
    const mean = counted ? sum / counted : NaN;
    const t = clip.begin_s + f * clip.step_s;
    els.slider.value = f;
    els.time.textContent = `${fmt(t, 0)} s`;
    els.slider.setAttribute("aria-valuetext", `t = ${fmt(t, 0)} s`);
    const items = [
      [text("Density k", "密度 k"), text(`${fmt(clip.density_veh_km, 0)} veh/km per lane`, `每车道 ${fmt(clip.density_veh_km, 0)} veh/km`)],
      [text("Cars on the map", "地图上的车辆"), text(`${cars} of ${clip.n_vehicles}`, `${cars} / ${clip.n_vehicles}`)],
      [text("Mean speed", "平均车速"), `${fmt(mean, 1)} m/s · ${fmt(mean * 3.6, 0)} km/h`]
    ];
    els.stats.innerHTML = items.map(([k, v]) => `<div><dt>${k}</dt><dd>${v}</dd></div>`).join("");
  }

  function drawAll() {
    if (layout()) drawMap();
    updateReadout();
  }

  // ----- page

  function build() {
    const { clip } = entry(), d = decode(entry());
    const last = clip.begin_s + (d.frames - 1) * clip.step_s;
    box.className = "card nm-card";
    box.innerHTML = `<h3>${text("Network map: replay of SUMO runs", "路网地图：SUMO 运行回放")}</h3>
      <p class="nm-intro">${text(
        `One run at each density, seed ${clip.seed}: ${fmt(d.frames * clip.step_s, 0)} s from t = ${fmt(clip.begin_s, 0)} s, one frame every ${clip.step_s} s, played at ${PLAYBACK}× speed. Each dot is a car, coloured by its speed; grey lines are the roads, wider with more lanes.`,
        `每个密度各取一次运行（种子 ${clip.seed}）：从 t = ${fmt(clip.begin_s, 0)} s 起 ${fmt(d.frames * clip.step_s, 0)} s，每 ${clip.step_s} s 一帧，以 ${PLAYBACK} 倍速播放。每个点是一辆车，颜色表示车速；灰线是道路，车道越多线越宽。`)}</p>
      <div class="nm-layout">
        <figure class="nm-map-fig">
          <div class="nm-map-wrap"><canvas class="nm-map" role="img" aria-label="${text("Map of the network with each car coloured by speed", "路网地图，每辆车的颜色表示车速")}"></canvas></div>
          <figcaption class="nm-foot"><span class="sim-scale"><span>0</span><span class="nm-ramp"></span><span>${fmt(d.vTop, 1)} m/s (${fmt(d.vTop * 3.6, 0)} km/h) ${text("or faster", "及以上")}</span></span>
            <span>${text("the scale's top is the speed limit of most roads", "色标上限为大多数道路的限速")}</span></figcaption>
        </figure>
        <div class="nm-side">
          <div class="nm-group"><span class="nm-label" id="nm-density">${text("Density k (veh/km per lane)", "密度 k（veh/km，每车道）")}</span>
            <div class="nm-choice" role="group" aria-labelledby="nm-density">${clips.map((c, i) =>
              `<button type="button" class="btn${i === current ? " primary" : ""}" data-clip="${i}" aria-pressed="${i === current}">${fmt(c.clip.density_veh_km, 0)}</button>`).join("")}</div></div>
          <div class="nm-group"><button type="button" class="btn primary nm-play" data-act="play">${running ? text("Pause", "暂停") : text("Play", "播放")}</button></div>
          <div class="viz-controls nm-controls"><label>${text("Time t", "时间 t")}<output data-out="time"></output>
            <input type="range" data-key="time" min="0" max="${d.frames - 1}" step="1" value="${frameIndex()}"></label>
            <span class="nm-range"><span>${fmt(clip.begin_s, 0)} s</span><span>${fmt(last, 0)} s</span></span></div>
          <dl class="sim-stats nm-stats"></dl>
        </div>
      </div>
      <p class="nm-note">${text(
        `Speeds come from each car's position change over one ${clip.step_s} s step; positions are rounded to 1 m, so a speed is good to about 1 m/s. Cars missing from a frame are mid-teleport and are not drawn, so the map can show fewer cars than the run has. Run IDs and sources are under Data.`,
        `车速由每辆车在一个 ${clip.step_s} s 时间步内的位置变化算出；位置取整到 1 m，所以车速误差约 1 m/s。某一帧中缺少的车辆正处于瞬移中，不画出，所以地图上的车辆可能少于该次运行的车辆数。运行编号与数据来源见“数据”部分。`)}</p>`;
    els = {
      map: box.querySelector(".nm-map"), mapWrap: box.querySelector(".nm-map-wrap"),
      slider: box.querySelector('[data-key="time"]'), time: box.querySelector('[data-out="time"]'),
      stats: box.querySelector(".nm-stats")
    };
    box.querySelector(".nm-ramp").style.background = colors.gradient;
    drawAll();
    buildProvenance();
  }

  // Run IDs and sources of every loaded clip, beside the Data line (GUIDE section 5).
  function buildProvenance() {
    const el = document.querySelector('[data-results="provenance"]');
    if (!el) return;
    const nets = [...new Set(clips.map((c) => c.clip.net))].map((net) => network["roads_" + net]);
    el.innerHTML = `<h3>${text("Loaded trajectory clips", "已载入的轨迹片段")}</h3><div class="table-wrap"><table>
      <thead><tr><th>${text("Clip", "片段")}</th><th>${text("Run", "运行")}</th><th>${text("Frames", "帧")}</th><th>${text("Config", "配置")}</th><th>git commit</th><th>${text("SUMO version", "SUMO 版本")}</th></tr></thead>
      <tbody>${clips.map(({ key, clip }) => `<tr><th scope="row">${key}</th>
        <td><code>${clip.run_id}</code>${clip.rerun_check && clip.rerun_check.identical ? text(
          `, a rerun of <code>${clip.sweep_run_id}</code> with the same running and halting counts and mean speed at each of its first ${clip.rerun_check.steps} steps`,
          `，重跑 <code>${clip.sweep_run_id}</code>，前 ${clip.rerun_check.steps} 步每步的运行车辆数、停车车辆数和平均车速都与之相同`) : ""}</td>
        <td>${clip.frames.length} × ${clip.step_s} s ${text("from", "起于")} ${fmt(clip.begin_s, 0)} s</td>
        <td><code>${clip.config}</code> · <code>${clip.config_sha256}</code></td><td><code>${clip.git_commit}</code></td><td>${clip.sumo_version.replace(/^Eclipse SUMO sumo /, "")}</td></tr>`).join("")}</tbody>
      </table></div>
      <p class="nm-source">${nets.map((r) => text(`Roads: <code>${r.net}</code>, ${r.edges.length} roads.`, `道路：<code>${r.net}</code>，共 ${r.edges.length} 条。`)).join(" ")}</p>`;
  }

  // ----- controls

  box.addEventListener("input", function (event) {
    if (event.target.dataset.key !== "time") return;
    time = Number(event.target.value);
    drawMap();
    updateReadout();
  });

  box.addEventListener("click", function (event) {
    const button = event.target.closest("[data-clip], [data-act]");
    if (!button) return;
    if (button.dataset.act === "play") {
      running = !running;
      button.textContent = running ? text("Pause", "暂停") : text("Play", "播放");
      return;
    }
    const next = Number(button.dataset.clip);
    if (next === current) return;
    const net = entry().clip.net;
    current = next;
    time = Math.min(time, decode(entry()).frames - 1);   // keep the time, to compare densities
    box.querySelectorAll("[data-clip]").forEach((b) => {
      const on = Number(b.dataset.clip) === current;
      b.classList.toggle("primary", on);
      b.setAttribute("aria-pressed", on);
    });
    if (entry().clip.net !== net) layout();
    drawMap();
    updateReadout();
  });

  // ----- animation

  let last = null;
  function frame(now) {
    requestAnimationFrame(frame);
    const elapsed = last === null ? 0 : Math.min(0.1, (now - last) / 1000);
    last = now;
    if (!running || !visible) return;
    const d = decode(entry());
    time += elapsed * PLAYBACK / entry().clip.step_s;
    if (time > d.frames - 1) time = 0;   // loop
    drawMap();
    if (frameIndex() !== shownFrame) updateReadout();
  }

  readColors();
  build();
  window.Site.onChange(build);
  new IntersectionObserver((entries) => { visible = entries[0].isIntersecting; }).observe(box);
  let resizeFrame;
  new ResizeObserver(() => {
    cancelAnimationFrame(resizeFrame);
    resizeFrame = requestAnimationFrame(() => { if (layout()) drawMap(); });
  }).observe(box);
  const recolour = () => {
    readColors();
    box.querySelector(".nm-ramp").style.background = colors.gradient;
    if (layout()) drawMap();
  };
  new MutationObserver(recolour).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", recolour);
  requestAnimationFrame(frame);
})();
