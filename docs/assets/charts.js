// Small SVG line charts for the home page results.
// Chart.line(el, spec) draws into el and redraws when el changes width.
// spec = {
//   x: { label, min, max }, y: { label, min, max },
//   series: [{ name, color, line: [[x, y]...], band: [[x, lo, hi]...], dots: [[x, y]...] }],
//   hlines: [{ y, label }], marks: [{ x, color }]          (all optional)
// }
// color is a CSS custom property name such as "--accent", so charts follow the theme.

(function () {
  "use strict";

  const NS = "http://www.w3.org/2000/svg";
  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

  function niceStep(span, target) {
    const raw = span / target;
    const p = Math.pow(10, Math.floor(Math.log10(raw)));
    const m = raw / p;
    return (m <= 1 ? 1 : m <= 2 ? 2 : m <= 2.5 ? 2.5 : m <= 5 ? 5 : 10) * p;
  }
  function ticks(min, max, target) {
    const step = niceStep(max - min, target);
    const out = [];
    for (let v = Math.ceil(min / step) * step; v <= max + step * 1e-9; v += step) out.push(+v.toFixed(10));
    return out;
  }
  function node(tag, attrs, parent) {
    const el = document.createElementNS(NS, tag);
    Object.entries(attrs || {}).forEach(([k, v]) => el.setAttribute(k, v));
    if (parent) parent.append(el);
    return el;
  }

  function draw(el, spec) {
    const W = Math.max(280, el.clientWidth || 600);
    const H = Math.round(Math.min(320, Math.max(220, W * 0.55)));
    const pad = { l: 52, r: 14, t: 12, b: 42 };
    const all = spec.series.flatMap((s) => [...(s.line || []), ...(s.dots || []), ...(s.band || []).map((b) => [b[0], b[2]])]);
    const xmin = spec.x.min ?? Math.min(...all.map((p) => p[0]));
    const xmax = spec.x.max ?? Math.max(...all.map((p) => p[0]));
    const ymin = spec.y.min ?? 0;
    const ymax = spec.y.max ?? Math.max(...all.map((p) => p[1])) * 1.08;
    const sx = (v) => pad.l + (v - xmin) / (xmax - xmin) * (W - pad.l - pad.r);
    const sy = (v) => H - pad.b - (v - ymin) / (ymax - ymin) * (H - pad.t - pad.b);
    const ink = css("--text"), muted = css("--muted"), grid = css("--border");

    const svg = node("svg", { viewBox: `0 0 ${W} ${H}`, width: W, height: H, role: "img", "aria-label": spec.aria || "", class: "chart-svg" });
    svg.style.font = "12px -apple-system, Segoe UI, sans-serif";

    ticks(ymin, ymax, 4).forEach((v) => {
      node("line", { x1: pad.l, x2: W - pad.r, y1: sy(v), y2: sy(v), stroke: grid, "stroke-width": 1 }, svg);
      node("text", { x: pad.l - 6, y: sy(v) + 4, "text-anchor": "end", fill: muted }, svg).textContent = v;
    });
    ticks(xmin, xmax, Math.max(3, Math.floor(W / 90))).forEach((v) => {
      node("line", { x1: sx(v), x2: sx(v), y1: H - pad.b, y2: H - pad.b + 4, stroke: muted }, svg);
      node("text", { x: sx(v), y: H - pad.b + 17, "text-anchor": "middle", fill: muted }, svg).textContent = v;
    });
    node("line", { x1: pad.l, x2: W - pad.r, y1: H - pad.b, y2: H - pad.b, stroke: muted }, svg);
    node("text", { x: (pad.l + W - pad.r) / 2, y: H - 6, "text-anchor": "middle", fill: ink }, svg).textContent = spec.x.label;
    const yl = node("text", { x: 0, y: 0, "text-anchor": "middle", fill: ink, transform: `translate(13 ${(pad.t + H - pad.b) / 2}) rotate(-90)` }, svg);
    yl.textContent = spec.y.label;

    (spec.hlines || []).forEach((h) => {
      node("line", { x1: pad.l, x2: W - pad.r, y1: sy(h.y), y2: sy(h.y), stroke: muted, "stroke-dasharray": "5 4" }, svg);
      if (h.label) node("text", { x: W - pad.r - 4, y: sy(h.y) - 5, "text-anchor": "end", fill: muted }, svg).textContent = h.label;
    });

    spec.series.forEach((s) => {
      const c = css(s.color);
      if (s.band && s.band.length) {
        const pts = s.band.map((b) => `${sx(b[0])},${sy(b[2])}`).concat(s.band.slice().reverse().map((b) => `${sx(b[0])},${sy(b[1])}`));
        node("polygon", { points: pts.join(" "), fill: c, "fill-opacity": 0.14, stroke: "none" }, svg);
      }
      if (s.line && s.line.length) {
        node("polyline", { points: s.line.map((p) => `${sx(p[0])},${sy(p[1])}`).join(" "), fill: "none", stroke: c, "stroke-width": 2, "stroke-linejoin": "round" }, svg);
      }
      (s.dots || []).forEach((p) => {
        const dot = node("circle", { cx: sx(p[0]), cy: sy(p[1]), r: s.line ? 2.5 : 3.5, fill: c, "fill-opacity": s.line ? 0.55 : 0.9 }, svg);
        node("title", {}, dot).textContent = `${s.name}: ${spec.x.label} ${(+p[0]).toFixed(1)}, ${spec.y.label} ${(+p[1]).toPrecision(3)}`;
      });
    });

    (spec.marks || []).forEach((m) => {
      node("line", { x1: sx(m.x), x2: sx(m.x), y1: H - pad.b, y2: H - pad.b - 9, stroke: css(m.color), "stroke-width": 2.5 }, svg);
    });

    const legend = spec.series.length > 1 || spec.legend
      ? `<div class="chart-legend">${spec.series.map((s) => `<span><i style="background:${css(s.color)}"></i>${s.name}</span>`).join("")}</div>`
      : "";
    el.replaceChildren(svg);
    if (legend) el.insertAdjacentHTML("beforeend", legend);
  }

  function line(el, spec) {
    draw(el, spec);
    let w = el.clientWidth, raf;
    new ResizeObserver(() => {
      if (el.clientWidth === w) return;
      w = el.clientWidth;
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => draw(el, spec));
    }).observe(el);
    return { redraw: (next) => { if (next) spec = next; draw(el, spec); } };
  }

  window.Chart = { line };
})();
