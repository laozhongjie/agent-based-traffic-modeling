// Ring-road results: draws every experiment in window.RESULTS whose scenario is "ring".
// Data files come from scripts/export_web.py (docs/data/ring/<name>.js); ring.html loads them
// with <script> tags. Without data the placeholders on the page stay as they are.
(function () {
  "use strict";
  const experiments = Object.values(window.RESULTS || {}).filter((d) => d.scenario === "ring");
  if (!experiments.length) return;

  const text = (en, zh) => window.Site.lang === "zh" ? zh : en;
  const PLOT_HEIGHT = 245;

  // One series per experiment; each row becomes an object keyed by column name.
  const series = experiments.map((d, i) => ({
    data: d,
    index: i,
    label: d.model + (d.draft ? " *" : ""),
    rows: d.rows.map((r) => Object.fromEntries(d.columns.map((c, j) => [c, r[j]])))
  }));

  function niceStep(span) {
    const raw = span / 4;
    const p = Math.pow(10, Math.floor(Math.log10(raw)));
    const m = raw / p;
    return (m <= 1 ? 1 : m <= 2 ? 2 : m <= 2.5 ? 2.5 : m <= 5 ? 5 : 10) * p;
  }

  function axis(max) {
    const step = niceStep(max || 1);
    return { max: Math.ceil((max || 1) / step) * step, step };
  }

  function format(v, step) {
    const digits = (String(+step.toPrecision(6)).split(".")[1] || "").length;
    return v.toFixed(digits);
  }

  // Mean over seeds at each density, for the line through the points.
  function means(rows, x, y) {
    const groups = new Map();
    rows.forEach((r) => {
      const g = groups.get(r[x]) || [];
      g.push(r[y]);
      groups.set(r[x], g);
    });
    return [...groups].sort((a, b) => a[0] - b[0])
      .map(([k, ys]) => [k, ys.reduce((s, v) => s + v, 0) / ys.length]);
  }

  function plot(container, x, y, xLabel, yLabel) {
    const width = Math.max(240, container.clientWidth);
    const height = PLOT_HEIGHT;
    const all = series.flatMap((s) => s.rows);
    const xa = axis(Math.max(...all.map((r) => r[x])));
    const ya = axis(Math.max(...all.map((r) => r[y])));
    const left = Math.max(44, format(ya.max, ya.step).length * 7 + 18);
    const right = width - 14;
    const top = 28;
    const bottom = height - 44;
    const sx = (v) => left + v / xa.max * (right - left);
    const sy = (v) => bottom - v / ya.max * (bottom - top);

    let content = `<text x="${left}" y="14">${yLabel}</text>`;
    for (let v = 0; v <= ya.max + 1e-9; v += ya.step) {
      content += `<line class="viz-gridline" x1="${left}" y1="${sy(v)}" x2="${right}" y2="${sy(v)}"/>
        <text x="${left - 8}" y="${sy(v) + 4}" text-anchor="end">${format(v, ya.step)}</text>`;
    }
    for (let v = 0; v <= xa.max + 1e-9; v += xa.step) {
      content += `<text x="${sx(v)}" y="${bottom + 18}" text-anchor="middle">${format(v, xa.step)}</text>`;
    }
    content += `<path class="viz-axis" fill="none" d="M${left} ${top}V${bottom}H${right}"/>
      <text x="${(left + right) / 2}" y="${height - 4}" text-anchor="middle">${xLabel}</text>`;

    series.forEach((s) => {
      const line = means(s.rows, x, y).map(([a, b], i) => `${i ? "L" : "M"}${sx(a)} ${sy(b)}`).join(" ");
      content += `<g class="rr-series rr-s${s.index % 4}"><path class="rr-line" d="${line}"/>`;
      s.rows.forEach((r) => {
        content += `<circle class="rr-dot" cx="${sx(r[x])}" cy="${sy(r[y])}" r="4"><title>${r.run_id}
${xLabel}: ${r[x]}
${yLabel}: ${r[y]}</title></circle>`;
      });
      content += "</g>";
    });
    container.innerHTML = `<svg class="viz-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="${yLabel} – ${xLabel}"><title>${yLabel} – ${xLabel}</title>${content}</svg>`;
  }

  function legend() {
    return `<ul class="rr-legend">${series.map((s) =>
      `<li class="rr-s${s.index % 4}"><span class="rr-swatch"></span>${s.label} · ${s.data.name}</li>`).join("")}</ul>`;
  }

  function figure(key, caption) {
    return `<figure><figcaption>${caption}</figcaption><div data-plot="${key}"></div></figure>`;
  }

  const k = () => text("Density k (veh/km)", "密度 k (veh/km)");
  const PLOTS = {
    speed: () => ["mean_speed_mps", text("Mean speed (m/s)", "平均速度 (m/s)")],
    flow: () => ["flow_veh_h", text("Flow q (veh/h)", "流量 q (veh/h)")],
    phi: () => ["congested_fraction", text("Jammed fraction φ", "拥堵比例 φ")],
    chi: () => ["congested_fraction_var", text("Fluctuation χ = Var(φ)", "涨落 χ = Var(φ)")]
  };

  const fd = document.querySelector('[data-results="fd"]');
  const order = document.querySelector('[data-results="order"]');
  const provenance = document.querySelector('[data-results="provenance"]');

  function build() {
    const hover = text("Each dot is one run (hover for its run ID); the line joins the mean over seeds. * marks a draft from uncommitted code.",
      "每个点是一次运行（悬停可看运行编号），折线连接各密度下不同种子的平均值。* 表示来自未提交代码的草稿。");
    fd.className = "card rr-card wide";
    fd.innerHTML = `<h3>${text("1. Fundamental diagrams", "1. 基本图")}</h3>${legend()}
      <div class="viz-plots">${figure("speed", text("Speed–density", "速度–密度"))}${figure("flow", text("Flow–density", "流量–密度"))}</div>
      <p class="rr-note">${hover}</p>`;
    order.className = "card rr-card";
    order.innerHTML = `<h3>${text("2. Order parameter and fluctuations", "2. 序参量与涨落")}</h3>${legend()}
      ${figure("phi", text("Jammed fraction–density", "拥堵比例–密度"))}${figure("chi", text("Fluctuations–density", "涨落–密度"))}
      <p class="rr-note">${text("φ is the fraction of vehicles slower than the jam speed, averaged after the warm-up; χ is the variance of φ over the same period.",
        "φ 是速度低于拥堵阈值的车辆比例，取预热之后的时间平均；χ 是同一时段内 φ 的方差。")}</p>`;
    provenance.innerHTML = `<h3>${text("Loaded experiments", "已载入的实验")}</h3><div class="table-wrap"><table>
      <thead><tr><th>${text("Experiment", "实验")}</th><th>${text("Model", "模型")}</th><th>${text("Valid runs", "有效运行")}</th><th>${text("Config", "配置")}</th><th>git commit</th><th>${text("SUMO version", "SUMO 版本")}</th></tr></thead>
      <tbody>${series.map((s) => `<tr><th scope="row">${s.data.name}${s.data.draft ? ` <span class="chip decide">${text("Draft", "草稿")}</span>` : ""}</th>
        <td>${s.data.model}</td><td>${s.rows.length}${s.data.excluded_invalid ? text(` (${s.data.excluded_invalid} invalid excluded)`, `（已排除 ${s.data.excluded_invalid} 次无效运行）`) : ""}</td>
        <td><code>${s.data.config}</code> · <code>${s.data.config_sha256}</code></td><td><code>${s.data.git_commit}</code></td><td>${s.data.sumo_version.replace(/^Eclipse SUMO sumo /, "")}</td></tr>`).join("")}</tbody>
      </table></div>`;
    draw();
  }

  function draw() {
    document.querySelectorAll("[data-plot]").forEach((el) => {
      const [y, yLabel] = PLOTS[el.dataset.plot]();
      plot(el, "density_veh_km", y, k(), yLabel);
    });
  }

  window.Site.onChange(build);
  build();
  let frame;
  new ResizeObserver(() => {
    cancelAnimationFrame(frame);
    frame = requestAnimationFrame(draw);
  }).observe(fd);
})();
