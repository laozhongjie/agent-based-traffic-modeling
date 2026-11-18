// Results on the home page, drawn from the exported data in window.RESULTS (scripts/export_web.py):
// the city network's baseline sweep and the four planning variants. The ring-road figures are images.
// The city replay map (network-map.js and its clips, about 4 MB) loads when its box comes near.
//
// Planning critical density, as in scripts/planning_figures.py (member D, agreed with E):
// v0 = the baseline's seed-mean speed at the lowest target density; the critical density of a
// variant is where its seed-mean speed curve falls to v0 / 2, interpolated linearly between the
// two target densities around the crossing. Maximum flow = the highest seed-mean flow.

(function () {
  "use strict";

  const R = window.RESULTS || {};
  const text = (en, zh) => (window.Site.lang === "zh" ? zh : en);
  const mean = (a) => a.reduce((s, v) => s + v, 0) / a.length;
  const rowsOf = (key) => {
    const d = R[key];
    return d ? d.rows.map((r) => Object.fromEntries(d.columns.map((c, j) => [c, r[j]]))) : [];
  };

  // Seed mean and range of `col` per density; `k` names the density column.
  function bySeed(rows, col, k) {
    const groups = new Map();
    rows.forEach((r) => {
      if (r[col] == null) return;
      if (!groups.has(r[k])) groups.set(r[k], []);
      groups.get(r[k]).push(r[col]);
    });
    const ks = [...groups.keys()].sort((a, b) => a - b);
    return {
      line: ks.map((x) => [x, mean(groups.get(x))]),
      band: ks.map((x) => [x, Math.min(...groups.get(x)), Math.max(...groups.get(x))]),
      dots: rows.filter((r) => r[col] != null).map((r) => [r[k], r[col]])
    };
  }
  function crossing(line, level) {
    for (let i = 1; i < line.length; i++) {
      const [k1, a] = line[i - 1], [k2, b] = line[i];
      if (b < level) return k1 + (a - level) * (k2 - k1) / (a - b);
    }
    return NaN;
  }

  // ---------- data ----------
  const plan = {
    base: rowsOf("planning/bugis_all_base_controller").concat(rowsOf("planning/bugis_all_base_controller_seeds4to10")),
    closure: rowsOf("planning/bugis_all_closure_controller"),
    lanecut: rowsOf("planning/bugis_all_lanecut_controller"),
    newlink: rowsOf("planning/bugis_all_newlink_controller").concat(rowsOf("planning/bugis_all_newlink_controller_seeds4to10"))
  };
  const VARIANTS = [
    { id: "base", color: "--text", en: "Baseline", zh: "基准路网" },
    { id: "closure", color: "--jam", en: "Road closure", zh: "封路" },
    { id: "lanecut", color: "--doing", en: "Lane cut", zh: "减少车道" },
    { id: "newlink", color: "--accent", en: "New link", zh: "新增道路" }
  ];
  const K = "city_k_target";
  const speed = Object.fromEntries(VARIANTS.map((v) => [v.id, bySeed(plan[v.id], "mean_speed_mps", K)]));
  const flow = Object.fromEntries(VARIANTS.map((v) => [v.id, bySeed(plan[v.id], "flow_veh_h", K)]));
  const v0 = plan.base.length ? speed.base.line[0][1] : NaN;
  const kc = Object.fromEntries(VARIANTS.map((v) => [v.id, crossing(speed[v.id].line, v0 / 2)]));
  const qmax = Object.fromEntries(VARIANTS.map((v) => [v.id, Math.max(...flow[v.id].line.map((p) => p[1]))]));
  // The city network section shows the baseline, seeds 1-3 (the extra seeds only cover 25-35 veh/km).
  const city = rowsOf("planning/bugis_all_base_controller");

  // ---------- charts ----------
  const charts = [];
  function chart(sel, specFn) {
    const el = document.querySelector(sel);
    if (!el) return;
    charts.push({ c: window.Chart.line(el, specFn()), specFn });
  }
  const kLane = () => text("density k (veh/km per lane)", "密度 k（veh/km，每车道）");

  if (city.length) {
    chart('[data-chart="city-flow"]', () => ({
      aria: text("Network flow against density", "路网流量–密度图"),
      x: { label: kLane(), min: 0 }, y: { label: text("flow q (veh/h per lane)", "流量 q（veh/h，每车道）") },
      series: [{ name: text("baseline", "基准路网"), color: "--accent", ...bySeed(city, "flow_veh_h", K) }]
    }));
    chart('[data-chart="city-speed"]', () => ({
      aria: text("Network mean speed against density", "路网平均车速–密度图"),
      x: { label: kLane(), min: 0 }, y: { label: text("mean speed (m/s)", "平均车速（m/s）") },
      hlines: [{ y: v0 / 2, label: text("half the near-empty speed", "接近空载车速的一半") }],
      marks: [{ x: kc.base, color: "--accent" }],
      series: [{ name: text("baseline", "基准路网"), color: "--accent", ...bySeed(city, "mean_speed_mps", K) }]
    }));
    chart('[data-chart="city-cluster"]', () => ({
      aria: text("Congested share of lane length against density", "拥堵车道长度占比–密度图"),
      x: { label: kLane(), min: 0 }, y: { label: text("share of lane length", "占车道总长度的比例"), max: 0.6 },
      series: [
        { name: text("all congested roads", "全部拥堵路段"), color: "--muted", ...bySeed(city, "city_congested_length_fraction", K) },
        { name: text("largest connected congested cluster", "最大连通拥堵簇"), color: "--jam", ...bySeed(city, "city_largest_cluster", K) }
      ]
    }));
  }

  if (plan.base.length) {
    const series = (data) => VARIANTS.map((v) => ({ name: text(v.en, v.zh), color: v.color, line: data[v.id].line, band: data[v.id].band }));
    // Zoomed to 7.5-20 veh/km, where the curves cross half the near-empty speed.
    const near = (s) => ({ ...s, line: s.line.filter((p) => p[0] >= 7.5 && p[0] <= 20), band: s.band.filter((p) => p[0] >= 7.5 && p[0] <= 20) });
    chart('[data-chart="plan-speed"]', () => ({
      aria: text("Mean speed against density for the four networks, near the critical point", "四种路网在临界点附近的平均车速–密度图"),
      x: { label: kLane(), min: 7.5, max: 20 }, y: { label: text("mean speed (m/s)", "平均车速（m/s）"), min: 2, max: 5 },
      hlines: [{ y: v0 / 2, label: text("half the near-empty speed", "接近空载车速的一半") }],
      marks: VARIANTS.map((v) => ({ x: kc[v.id], color: v.color })),
      series: series(speed).map(near)
    }));
    chart('[data-chart="plan-flow"]', () => ({
      aria: text("Flow against density for the four networks", "四种路网的流量–密度图"),
      x: { label: kLane(), min: 0 }, y: { label: text("flow q (veh/h per lane)", "流量 q（veh/h，每车道）") },
      series: series(flow)
    }));
  }

  function table() {
    const el = document.querySelector('[data-table="plan"]');
    if (!el || !plan.base.length) return;
    const f = (v, d) => (Number.isFinite(v) ? v.toFixed(d) : "–");
    const sign = (v, d) => (v > 0 ? "+" : v < 0 ? "−" : "") + Math.abs(v).toFixed(d);
    el.innerHTML = `<table><thead><tr><th>${text("Network", "路网")}</th><th>\\(\\rho_c\\) (veh/km)</th><th>${text("change", "变化")}</th>
      <th>${text("max. flow (veh/h per lane)", "最大流量（veh/h，每车道）")}</th><th>${text("change", "变化")}</th></tr></thead><tbody>${VARIANTS.map((v) => `<tr>
      <th scope="row"><span class="swatch-line" style="background:var(${v.color})"></span>${text(v.en, v.zh)}</th>
      <td>${f(kc[v.id], 2)}</td><td>${v.id === "base" ? "–" : `${sign(kc[v.id] - kc.base, 2)} (${sign(100 * (kc[v.id] - kc.base) / kc.base, 1)}%)`}</td>
      <td>${f(qmax[v.id], 1)}</td><td>${v.id === "base" ? "–" : sign(qmax[v.id] - qmax.base, 1)}</td></tr>`).join("")}</tbody></table>`;
  }

  function sources() {
    const el = document.querySelector('[data-results="sources"]');
    if (!el) return;
    const rows = Object.entries(R).map(([key, d]) => `<tr><th scope="row"><code>${key}</code></th><td>${d.rows.length}</td>
      <td><code>${d.config}</code></td><td><code>${d.git_commit}</code></td><td>${d.sumo_version.replace(/^Eclipse SUMO sumo /, "")}</td></tr>`).join("");
    el.innerHTML = `<h3>${text("Result tables", "结果表")}</h3><div class="table-wrap"><table><thead><tr><th>${text("Data", "数据")}</th>
      <th>${text("Valid runs", "有效运行")}</th><th>${text("Config", "配置")}</th><th>git commit</th><th>${text("SUMO version", "SUMO 版本")}</th></tr></thead>
      <tbody>${rows}</tbody></table></div>`;
  }

  function redraw() { charts.forEach(({ c, specFn }) => c.redraw(specFn())); }
  function render() { table(); sources(); window.Site.renderMath(); }
  render();
  window.Site.onChange(() => { redraw(); render(); });
  new MutationObserver(redraw).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", redraw);

  // ---------- city replay map, loaded on demand ----------
  const box = document.querySelector('[data-results="map"]');
  if (box) {
    const files = ["data/network/roads_bugis_all.js", "data/network/clip_bugis_all_k10.js",
      "data/network/clip_bugis_all_k25.js", "data/network/clip_bugis_all_k40.js", "assets/network-map.js"];
    const load = () => files.forEach((src) => {
      const s = document.createElement("script");
      s.src = src;
      s.async = false;   // keep the order: roads and clips before the map
      document.body.append(s);
    });
    const io = new IntersectionObserver((entries) => {
      if (!entries[0].isIntersecting) return;
      io.disconnect();
      load();
    }, { rootMargin: "600px 0px" });
    io.observe(box);
  }
})();
