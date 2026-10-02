(function () {
  "use strict";

  const P = window.PROJECT;
  const I = window.I18N;
  const TZ = "Asia/Singapore";
  const DAY = 86400000;

  // ---------- language ----------
  function initialLang() {
    try {
      const saved = localStorage.getItem("lang");
      if (saved === "en" || saved === "zh") return saved;
    } catch (e) { /* storage unavailable */ }
    return (navigator.language || "").toLowerCase().startsWith("zh") ? "zh" : "en";
  }
  let lang = initialLang();
  const tr = (v) => (v == null ? "" : typeof v === "string" ? v : v[lang] != null ? v[lang] : v.en);
  const U = () => I.ui[lang];

  // English text is the page's original markup; capture it once so we can switch back.
  const original = new Map();
  document.querySelectorAll("[data-i18n]").forEach((el) => original.set(el, el.innerHTML));
  const originalAria = new Map();
  document.querySelectorAll("[data-i18n-aria]").forEach((el) => originalAria.set(el, el.getAttribute("aria-label")));
  const originalTitle = document.title;

  function applyStatic() {
    const zh = I.static.zh;
    original.forEach((html, el) => {
      const key = el.dataset.i18n;
      el.innerHTML = lang === "zh" && zh[key] != null ? zh[key] : html;
    });
    originalAria.forEach((label, el) => {
      const key = el.dataset.i18nAria;
      el.setAttribute("aria-label", lang === "zh" && zh[key] != null ? zh[key] : label);
    });
    document.title = lang === "zh" ? zh["meta.title"] : originalTitle;
    document.documentElement.lang = lang === "zh" ? "zh-CN" : "en";
    document.getElementById("lang-toggle").textContent = U().switchTo;
  }

  // ---------- helpers ----------
  function h(tag, attrs, children) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v == null) continue;
      if (k === "class") node.className = v;
      else if (k === "text") node.textContent = v;
      else if (k === "style") node.style.cssText = v;
      else node.setAttribute(k, v);
    }
    for (const c of [].concat(children || [])) {
      if (c == null) continue;
      node.append(c instanceof Node ? c : document.createTextNode(c));
    }
    return node;
  }
  const dayStart = (d) => new Date(d + "T00:00:00+08:00");
  const dayEnd = (d) => new Date(d + "T23:59:59+08:00");
  function fmtDay(date, opts) {
    const base = lang === "zh" ? { month: "long", day: "numeric" } : { day: "numeric", month: "short" };
    return date.toLocaleDateString(lang === "zh" ? "zh-CN" : "en-GB", Object.assign(base, { timeZone: TZ }, opts));
  }
  function fmtTime(date) {
    return lang === "zh"
      ? date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", hourCycle: "h23", timeZone: TZ })
      : date.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", timeZone: TZ }).toLowerCase();
  }
  const clear = (id) => { const el = document.getElementById(id); el.replaceChildren(); return el; };

  const now = new Date();

  // ---------- next deadline ----------
  function renderNextDeadline() {
    const box = clear("next-deadline");
    const next = P.deadlines
      .map((d) => Object.assign({}, d, { at: new Date(d.date) }))
      .sort((a, b) => a.at - b.at)
      .find((d) => d.at > now);
    if (!next) {
      box.append(h("div", { class: "what" }, [h("strong", { text: U().allPassed })]));
      return;
    }
    const ms = next.at - now;
    const days = Math.floor(ms / DAY);
    const big = days >= 1 ? String(days) : String(Math.max(1, Math.ceil(ms / 3600000)));
    const unit = days >= 1 ? (days === 1 ? U().dayLeft : U().daysLeft) : U().hoursLeft;
    const when = lang === "zh"
      ? fmtDay(next.at, { weekday: "short" }) + " " + fmtTime(next.at) + U().tz
      : fmtDay(next.at, { weekday: "short" }) + ", " + fmtTime(next.at) + " " + U().tz;
    box.append(
      h("div", { class: "days" }, [big, h("small", { text: unit })]),
      h("div", { class: "what" }, [h("strong", { text: U().next + tr(next.label) }), when + " · " + tr(next.detail)])
    );
  }

  // ---------- timeline ----------
  function renderTimeline() {
    clear("timeline-status").textContent = tr(P.timelineStatus);

    const start = dayStart(P.timeline[0].start);
    const end = P.deadlines.map((d) => new Date(d.date)).sort((a, b) => b - a)[0];
    const pct = (t) => Math.min(100, Math.max(0, ((t - start) / (end - start)) * 100));
    // Anchor labels near the ends so they never spill past the bar.
    const anchor = (left) => (left > 85 ? "translateX(-100%)" : left < 15 ? "translateX(0)" : "translateX(-50%)");

    const bar = clear("timeline-bar");
    bar.append(h("div", { class: "track" }, [h("div", { class: "elapsed", style: "width:" + pct(now) + "%" })]));
    bar.append(h("span", { class: "marker-label start", style: "left:0;top:46px;transform:none", text: fmtDay(start) }));

    P.events.forEach((ev, i) => {
      const at = dayStart(ev.date);
      const left = pct(at);
      bar.append(h("div", { class: "marker " + ev.kind, style: "left:" + left + "%", title: tr(ev.label) }));
      bar.append(h("span", {
        class: "marker-label",
        style: "left:" + left + "%;top:" + (i % 2 ? 62 : 46) + "px;transform:" + anchor(left),
        text: fmtDay(at) + " · " + tr(ev.label)
      }));
    });

    if (now >= start && now <= end) {
      const left = pct(now);
      bar.append(h("div", { class: "marker today", style: "left:" + left + "%" }));
      bar.append(h("span", { class: "marker-label today", style: "left:" + left + "%;transform:" + anchor(left), text: U().today }));
    }

    const list = clear("timeline-list");
    P.timeline.forEach((ph) => {
      const s = dayStart(ph.start), e = dayEnd(ph.end);
      const state = now > e ? "past" : now >= s ? "current" : "upcoming";
      const range = ph.start === ph.end ? fmtDay(s) : fmtDay(s) + " – " + fmtDay(e);
      list.append(h("li", { class: "phase " + state }, [
        h("div", { class: "when" }, [range, state === "current" ? h("div", { class: "badge", text: U().now }) : null]),
        h("div", {}, [
          h("h3", { text: tr(ph.title) }),
          ph.note ? h("p", { class: "phase-note", text: tr(ph.note) }) : null,
          h("ul", {}, ph.items.map((it) => h("li", { text: tr(it) })))
        ])
      ]));
    });
  }

  // ---------- progress ----------
  const WEIGHT = { done: 1, doing: 0.5, todo: 0 };

  function counts(tasks) {
    const c = { done: 0, doing: 0, todo: 0 };
    tasks.forEach((t) => { c[t.status in c ? t.status : "todo"]++; });
    const score = tasks.reduce((s, t) => s + (WEIGHT[t.status] || 0), 0);
    return { c, total: tasks.length, pct: tasks.length ? Math.round((score / tasks.length) * 100) : 0 };
  }
  const countText = (n, key) => (lang === "zh" ? U()[key] + " " + n : n + " " + U()[key]);
  function barEl(k) {
    const label = [countText(k.c.done, "done"), countText(k.c.doing, "doing"), countText(k.c.todo, "todo")].join(", ");
    return h("div", { class: "bar", role: "img", "aria-label": label }, [
      h("div", { class: "seg-done", style: "width:" + (k.c.done / k.total) * 100 + "%" }),
      h("div", { class: "seg-doing", style: "width:" + (k.c.doing / k.total) * 100 + "%" })
    ]);
  }

  function renderProgress() {
    const all = counts(P.workstreams.flatMap((w) => w.tasks));
    clear("progress-summary").append(
      h("span", { class: "big", text: all.pct + "%" }),
      barEl(all),
      h("span", { class: "counts" }, [
        h("span", { text: countText(all.c.done, "done") }),
        h("span", { text: countText(all.c.doing, "doing") }),
        h("span", { text: countText(all.c.todo, "todo") })
      ])
    );

    const grid = clear("workstreams");
    P.workstreams.forEach((w) => {
      const k = counts(w.tasks);
      grid.append(h("article", { class: "card" }, [
        h("p", { class: "tag", text: tr(w.stage) }),
        h("div", { class: "ws-head" }, [h("h3", { text: tr(w.name) }), h("span", { class: "pct", text: k.pct + "%" })]),
        h("p", { class: "ws-owner" + (w.owner ? "" : " open"), text: w.owner ? U().owner + tr(w.owner) : U().unclaimed }),
        h("p", { class: "ws-summary", text: tr(w.summary) }),
        barEl(k),
        h("ul", { class: "tasks" }, w.tasks.map((t) => {
          const st = t.status in U().status ? t.status : "todo";
          return h("li", { class: st }, [
            h("span", { class: "status " + st, text: U().status[st] }),
            h("span", { class: "text", text: tr(t.text) })
          ]);
        }))
      ]));
    });
  }

  // ---------- resources ----------
  function renderResources() {
    const grid = clear("resources-list");
    P.resources.forEach((g) => {
      grid.append(h("article", { class: "card" }, [
        h("h3", { text: tr(g.group) }),
        h("ul", { class: "res-list" }, g.links.map((l) =>
          h("li", {}, [h("a", { href: l.url, target: "_blank", rel: "noopener", text: tr(l.label) }), h("span", { text: tr(l.note) })])
        ))
      ]));
    });
    document.getElementById("updated").textContent = U().updated + fmtDay(dayStart(P.updated), { year: "numeric" });
  }

  // ---------- ring-road demo (Nagel–Schreckenberg) ----------
  function ringDemo() {
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

      ctx.fillStyle = cssColor("--muted");
      ctx.font = "12px -apple-system, Segoe UI, sans-serif";
      ctx.textAlign = "center";
      ctx.fillText("NaSch · vmax " + VMAX + " · p " + P_SLOW, c, c + 4);
    }

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

    init();
    for (let i = 0; i < 40; i++) step(); // warm up so the first frame already shows structure
    prev = pos.slice();
    relabel();
    draw(1);
    requestAnimationFrame(frame);
    return { relabel };
  }

  // ---------- boot ----------
  function renderAll() {
    applyStatic();
    renderNextDeadline();
    renderTimeline();
    renderProgress();
    renderResources();
  }

  renderAll();
  const demo = ringDemo();

  document.getElementById("lang-toggle").addEventListener("click", () => {
    lang = lang === "zh" ? "en" : "zh";
    try { localStorage.setItem("lang", lang); } catch (e) { /* storage unavailable */ }
    renderAll();
    demo.relabel();
  });
})();
