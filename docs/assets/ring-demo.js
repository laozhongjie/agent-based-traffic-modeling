// Ring-road demo (Nagel–Schreckenberg) on the home page and the team workspace.
// Needs a canvas#ring, input#density, output#density-out, #demo-stats and button#play.
// U() returns the page's UI strings; only U().pause and U().play are used.

(function () {
  "use strict";

  window.ringDemo = function (U) {
    const canvas = document.getElementById("ring");
    const ctx = canvas.getContext("2d");
    const slider = document.getElementById("density");
    const out = document.getElementById("density-out");
    const stats = document.getElementById("demo-stats");
    const btn = document.getElementById("play");

    const L = 120, VMAX = 5, P_SLOW = 0.25, STEP_MS = 260;
    const CELL_M = 7.5;
    let pos = [], vel = [], prev = [];
    let running = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let visible = true, lastStep = 0, history = [];

    function init() {
      const n = Math.round((slider.value / 100) * L);
      const cells = Array.from({ length: L }, (_, i) => i);
      for (let i = L - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [cells[i], cells[j]] = [cells[j], cells[i]]; }
      pos = cells.slice(0, n).sort((a, b) => a - b);
      vel = pos.map(() => 0);
      prev = pos.slice();
      history = [];
      const vehKm = (n / (L * CELL_M)) * 1000;
      out.textContent = slider.value + "% · " + Math.round(vehKm) + " veh/km";
    }

    function step() {
      const n = pos.length;
      prev = pos.slice();
      const nv = vel.slice();
      for (let i = 0; i < n; i++) {
        const gap = (pos[(i + 1) % n] - pos[i] - 1 + L) % L;
        let v = Math.min(vel[i] + 1, VMAX);
        v = Math.min(v, n === 1 ? VMAX : gap);
        if (v > 0 && Math.random() < P_SLOW) v--;
        nv[i] = v;
      }
      vel = nv;
      pos = pos.map((p, i) => (p + vel[i]) % L);
      const mean = n ? vel.reduce((a, b) => a + b, 0) / n : 0;
      history.push(mean);
      if (history.length > 30) history.shift();
      const avg = history.reduce((a, b) => a + b, 0) / history.length;
      const kmh = avg * CELL_M * 3.6;
      const flow = (n / (L * CELL_M)) * 1000 * kmh;
      stats.textContent = Math.round(kmh) + " km/h · " + Math.round(flow) + " veh/h";
    }

    function cssColor(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }
    function hexToRgb(hex) {
      const m = hex.replace("#", "");
      const n = parseInt(m.length === 3 ? m.replace(/./g, "$&$&") : m, 16);
      return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
    }
    function mix(a, b, t) { return a.map((x, i) => Math.round(x + (b[i] - x) * t)); }

    function draw(frac) {
      const dpr = window.devicePixelRatio || 1;
      const size = canvas.clientWidth || 360;
      if (canvas.width !== Math.round(size * dpr)) { canvas.width = canvas.height = Math.round(size * dpr); }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const c = size / 2, R = size * 0.38;
      ctx.clearRect(0, 0, size, size);

      ctx.strokeStyle = cssColor("--surface-2");
      ctx.lineWidth = size * 0.075;
      ctx.beginPath(); ctx.arc(c, c, R, 0, Math.PI * 2); ctx.stroke();
      ctx.strokeStyle = cssColor("--border");
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 6]);
      ctx.beginPath(); ctx.arc(c, c, R, 0, Math.PI * 2); ctx.stroke();
      ctx.setLineDash([]);

      const jam = hexToRgb(cssColor("--jam")), mid = hexToRgb(cssColor("--doing")), free = hexToRgb(cssColor("--free"));
      const carLen = ((Math.PI * 2 * R) / L) * 0.8, carW = size * 0.045;
      for (let i = 0; i < pos.length; i++) {
        let d = pos[i] - prev[i]; if (d < 0) d += L;
        const p = prev[i] + d * frac;
        const a = (p / L) * Math.PI * 2 - Math.PI / 2;
        const t = vel[i] / VMAX;
        const rgb = t < 0.5 ? mix(jam, mid, t * 2) : mix(mid, free, (t - 0.5) * 2);
        ctx.save();
        ctx.translate(c + R * Math.cos(a), c + R * Math.sin(a));
        ctx.rotate(a + Math.PI / 2);
        ctx.fillStyle = "rgb(" + rgb.join(",") + ")";
        ctx.beginPath();
        if (ctx.roundRect) ctx.roundRect(-carLen / 2, -carW / 2, carLen, carW, 2); else ctx.rect(-carLen / 2, -carW / 2, carLen, carW);
        ctx.fill();
        ctx.restore();
      }

      // Centre label "NaSch · v_max = 5 · p = 0.25", the symbols set like the KaTeX formulas on the site.
      ctx.fillStyle = cssColor("--muted");
      ctx.textAlign = "left";
      const parts = LABEL_PARTS.map(([text, font, dy]) => { ctx.font = font; return [text, font, dy || 0, ctx.measureText(text).width]; });
      let x = c - parts.reduce((w, p) => w + p[3], 0) / 2;
      for (const [text, font, dy, w] of parts) { ctx.font = font; ctx.fillText(text, x, c + 5 + dy); x += w; }
    }
    const UI_FONT = "13px -apple-system, Segoe UI, sans-serif", SERIF = ', "Times New Roman", serif';
    const MATH_IT = "italic 15px KaTeX_Math" + SERIF, MATH_RM = "15px KaTeX_Main" + SERIF;
    const LABEL_PARTS = [["NaSch", UI_FONT], ["  ·  ", UI_FONT], ["v", MATH_IT], ["max", "11px KaTeX_Main" + SERIF, 3],
      [" = " + VMAX, MATH_RM], ["  ·  ", UI_FONT], ["p", MATH_IT], [" = " + P_SLOW, MATH_RM]];
    // Canvas text does not trigger web-font loading; load the KaTeX fonts, then redraw.
    if (document.fonts) Promise.all([MATH_IT, MATH_RM].map((f) => document.fonts.load(f))).then(() => draw(1), () => {});

    function frame(t) {
      if (running && visible) {
        if (!lastStep) lastStep = t;
        while (t - lastStep >= STEP_MS) { step(); lastStep += STEP_MS; }
        draw((t - lastStep) / STEP_MS);
      } else {
        lastStep = 0;
      }
      requestAnimationFrame(frame);
    }

    const relabel = () => { btn.textContent = running ? U().pause : U().play; };
    slider.addEventListener("input", () => { init(); draw(1); });
    btn.addEventListener("click", () => { running = !running; relabel(); });
    if ("IntersectionObserver" in window) {
      new IntersectionObserver((es) => { visible = es[0].isIntersecting; }).observe(canvas);
    }
    document.addEventListener("visibilitychange", () => { visible = !document.hidden; });
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => draw(1));
    document.addEventListener("themechange", () => draw(1));

    init();
    for (let i = 0; i < 40; i++) step(); // warm up so the first frame already shows structure
    prev = pos.slice();
    relabel();
    draw(1);
    requestAnimationFrame(frame);
    return { relabel };
  };
})();
