// Planning map on the home page: for each road, how much more or less of the measured hour it is
// congested with a planning change than in the baseline, at every swept density; or the baseline's
// own congestion. Data: window.PLANNING_MAP (scripts/export_planning_map.py) and the road outlines
// in window.NETWORK.roads_bugis_all (scripts/city_clips.py). home-results.js loads both when the
// map's box comes near, then calls window.planningMap().
(function () {
  "use strict";

  window.planningMap = function () {
    const box = document.querySelector('[data-results="plan-map"]');
    const P = window.PLANNING_MAP;
    const roads = window.NETWORK && window.NETWORK.roads_bugis_all;
    if (!box || !P || !roads) return;

    const text = (en, zh) => (window.Site.lang === "zh" ? zh : en);
    const MODES = [
      { id: "closure", en: "Road closure", zh: "封路" },
      { id: "lanecut", en: "Lane cut", zh: "减少车道" },
      { id: "newlink", en: "New link", zh: "新增道路" },
      { id: "base", en: "Baseline congestion", zh: "基准路网的拥堵" }
    ];
    const MAX_HEIGHT = 620;
    const byId = new Map(roads.edges.map((e) => [e.id, e]));
    let mode = "closure", kIndex = P.densities.indexOf(12.5), zoomed = false, view = null, colors = {};

    function css(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }
    function rgb(hex) {
      const m = hex.replace("#", "");
      const n = parseInt(m.length === 3 ? m.replace(/./g, "$&$&") : m, 16);
      return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
    }
    function mix(a, b, t) { return `rgb(${a.map((x, i) => Math.round(x + (b[i] - x) * t)).join(",")})`; }
    function readColors() {
      colors = { road: css("--border"), ink: css("--text"), surface: rgb(css("--surface")), up: rgb(css("--jam")), down: rgb(css("--accent")) };
    }

    // The changed roads, for the overlay and the zoom box.
    function changedShapes(v) {
      const info = P.variants[v];
      if (!info) return [];
      return info.shapes ? info.shapes : info.edges.map((id) => (byId.get(id) || {}).shape).filter(Boolean);
    }
    function bounds() {
      if (!zoomed || mode === "base") return roads.boundary;
      const pts = changedShapes(mode).flat();
      const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
      const cx = (Math.min(...xs) + Math.max(...xs)) / 2, cy = (Math.min(...ys) + Math.max(...ys)) / 2;
      return [cx - 650, cy - 650, cx + 650, cy + 650];
    }

    function layout() {
      const canvas = els.map;
      const [x0, y0, x1, y1] = bounds();
      const aspect = (x1 - x0) / (y1 - y0);
      const width = Math.floor(Math.min(els.wrap.clientWidth, MAX_HEIGHT * aspect));
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
      return true;
    }

    function path(ctx, shape) {
      ctx.beginPath();
      shape.forEach(([x, y], j) => (j ? ctx.lineTo(view.sx(x), view.sy(y)) : ctx.moveTo(view.sx(x), view.sy(y))));
    }
    const lineWidth = (lanes) => Math.max(view.ratio, lanes * 3.2 * view.scale) * (zoomed ? 1 : 1.4);

    // Value of each road: change in percentage points (variants) or congested share in percent (base).
    function values() {
      const k = `${P.densities[kIndex]}`;
      return mode === "base" ? P.base[k] : P.change[mode][k];
    }
    function colour(v) {
      if (mode === "base") return v > 0 ? mix(colors.surface, colors.up, Math.min(1, v / 80)) : null;
      if (!v) return null;
      return mix(colors.surface, v > 0 ? colors.up : colors.down, 0.25 + 0.75 * Math.min(1, Math.abs(v) / 50));
    }

    function draw() {
      if (!view && !layout()) return;
      const ctx = els.map.getContext("2d");
      ctx.clearRect(0, 0, els.map.width, els.map.height);
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      ctx.strokeStyle = colors.road;
      roads.edges.forEach((e) => { ctx.lineWidth = lineWidth(e.lanes); path(ctx, e.shape); ctx.stroke(); });
      const vals = values();
      const order = P.roads.map((id, i) => i).filter((i) => vals[i]).sort((a, b) => Math.abs(vals[a]) - Math.abs(vals[b]));
      order.forEach((i) => {
        const e = byId.get(P.roads[i]);
        if (!e) return;
        ctx.strokeStyle = colour(vals[i]);
        ctx.lineWidth = lineWidth(e.lanes) * 1.6 + view.ratio;
        path(ctx, e.shape);
        ctx.stroke();
      });
      if (mode !== "base") {
        ctx.strokeStyle = colors.ink;
        ctx.lineWidth = Math.max(2.5 * view.ratio, 10 * view.scale);
        ctx.setLineDash(mode === "closure" ? [4 * view.ratio, 3 * view.ratio] : []);
        changedShapes(mode).forEach((s) => { path(ctx, s); ctx.stroke(); });
        ctx.setLineDash([]);
      }
      stats(vals);
    }

    function stats(vals) {
      const k = P.densities[kIndex];
      const seeds = P.seeds[`${mode === "base" ? "base" : mode}@${k}`] || [];
      const n = seeds.length ? Math.max(...seeds) : 0;
      let rows;
      if (mode === "base") {
        const congested = vals.filter((v) => v >= 50).length;
        rows = [[text("Roads congested at least half the hour", "至少半小时拥堵的道路"), `${congested} / ${vals.length}`],
                [text("Seeds", "种子数"), n]];
      } else {
        const up = vals.filter((v) => v > 0).length, down = vals.filter((v) => v < 0).length;
        rows = [[text("Roads congested more often", "更常拥堵的道路"), up],
                [text("Roads congested less often", "更少拥堵的道路"), down],
                [text("Seed pairs", "种子对数"), n]];
      }
      els.k.textContent = `${k} veh/km`;
      els.stats.innerHTML = rows.map(([a, b]) => `<dt>${a}</dt><dd>${b}</dd>`).join("");
      els.legend.innerHTML = mode === "base"
        ? `<span>0</span><span class="nm-ramp" style="background:linear-gradient(90deg, rgb(${colors.surface}), rgb(${colors.up}))"></span><span>${text("80% of the hour or more", "一小时的 80% 及以上")}</span>`
        : `<span>${text("less", "更少")}</span><span class="nm-ramp" style="background:linear-gradient(90deg, rgb(${colors.down}), rgb(${colors.surface}), rgb(${colors.up}))"></span><span>${text("more often congested", "更常拥堵")}</span>`;
    }

    function build() {
      box.className = "card nm-card";
      box.innerHTML = `<h3>${text("Change in congestion, road by road", "逐条道路的拥堵变化")}</h3>
        <p class="nm-intro">${text(
          "For each road, the change in the share of the measured hour it is congested with the planning change, against the baseline at the same density and seeds. A road is coloured only if every seed pair changes the same way by at least 0.05 of the hour. The black line marks the changed road.",
          "每条道路在规划改动后、相对于同一密度和种子下的基准路网，处于拥堵状态的时间占比的变化。只有所有种子对都朝同一方向变化、且变化至少为一小时的 0.05 时才着色。黑线标出被改动的道路。")}</p>
        <div class="nm-layout">
          <figure class="nm-map-fig"><div class="nm-map-wrap"><canvas class="nm-map" role="img" aria-label="${text("Map of the change in congestion per road", "每条道路拥堵变化的地图")}"></canvas></div>
            <figcaption class="nm-foot"><span class="sim-scale pm-legend"></span></figcaption></figure>
          <div class="nm-side">
            <div class="nm-group"><span class="nm-label" id="pm-mode">${text("Map", "地图")}</span>
              <div class="nm-choice pm-modes" role="group" aria-labelledby="pm-mode">${MODES.map((m) =>
                `<button type="button" class="btn${m.id === mode ? " primary" : ""}" data-mode="${m.id}" aria-pressed="${m.id === mode}">${text(m.en, m.zh)}</button>`).join("")}</div></div>
            <div class="viz-controls nm-controls"><label>${text("Density k (veh/km per lane)", "密度 k（veh/km，每车道）")}<output class="pm-k"></output>
              <input type="range" class="pm-slider" min="0" max="${P.densities.length - 1}" step="1" value="${kIndex}"></label>
              <span class="nm-range"><span>${P.densities[0]}</span><span>${P.densities[P.densities.length - 1]}</span></span></div>
            <div class="nm-group"><button type="button" class="btn pm-zoom" aria-pressed="${zoomed}">${zoomed ? text("Whole district", "整个片区") : text("Zoom to the change", "放大到改动处")}</button></div>
            <dl class="sim-stats nm-stats pm-stats"></dl>
          </div>
        </div>`;
      els = { map: box.querySelector(".nm-map"), wrap: box.querySelector(".nm-map-wrap"), k: box.querySelector(".pm-k"),
              stats: box.querySelector(".pm-stats"), legend: box.querySelector(".pm-legend"), zoom: box.querySelector(".pm-zoom") };
      els.zoom.disabled = mode === "base";
      view = null;
      draw();
    }

    let els = {};
    box.addEventListener("input", (e) => {
      if (!e.target.classList.contains("pm-slider")) return;
      kIndex = Number(e.target.value);
      draw();
    });
    box.addEventListener("click", (e) => {
      const b = e.target.closest("[data-mode], .pm-zoom");
      if (!b) return;
      if (b.classList.contains("pm-zoom")) zoomed = !zoomed;
      else { mode = b.dataset.mode; if (mode === "base") zoomed = false; }
      build();
    });

    readColors();
    build();
    window.Site.onChange(build);
    const recolour = () => { readColors(); draw(); };
    new MutationObserver(recolour).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", recolour);
    let raf;
    new ResizeObserver(() => { cancelAnimationFrame(raf); raf = requestAnimationFrame(() => { view = null; draw(); }); }).observe(box);
  };
})();
