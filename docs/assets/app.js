(function () {
  "use strict";

  const P = window.PROJECT;
  const Site = window.Site;
  const DAY = 86400000;
  const tr = Site.tr;
  const U = Site.ui;
  const { TZ, h, dayStart, dayEnd, fmtDay, memberLabel, memberHref, reviewee, reviewer, counts, countSpans, barEl } = window.Team;

  // ---------- helpers ----------
  function fmtTime(date) {
    return Site.lang === "zh"
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
    const when = Site.lang === "zh"
      ? fmtDay(next.at, { weekday: "short" }) + " " + fmtTime(next.at) + "（" + U().tz + "）"
      : fmtDay(next.at, { weekday: "short" }) + ", " + fmtTime(next.at) + " " + U().tz;
    box.append(
      h("div", { class: "days" }, [big, h("small", { text: unit })]),
      h("div", { class: "what" }, [
        h("strong", { text: U().next + tr(next.label) }),
        h("span", { text: when }),
        h("span", { text: tr(next.detail) })
      ])
    );
  }

  // ---------- timeline ----------
  function renderTimeline() {
    clear("timeline-status").textContent = tr(P.timelineStatus);
    // The selected member's colour becomes the timeline's theme colour.
    const section = document.getElementById("timeline");
    section.classList.remove(...P.workstreams.map((w) => "m-" + w.owner));
    if (timelineWho !== "all") section.classList.add("m-" + timelineWho);

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
        class: "marker-label " + ev.kind,
        style: "left:" + left + "%;top:" + (i % 2 ? 62 : 46) + "px;transform:" + anchor(left),
        text: fmtDay(at) + " · " + tr(ev.label)
      }));
    });

    if (now >= start && now <= end) {
      const left = pct(now);
      bar.append(h("div", { class: "marker today", style: "left:" + left + "%" }));
      bar.append(h("span", { class: "marker-label today", style: "left:" + left + "%;transform:" + anchor(left), text: U().today }));
    }

    const members = P.workstreams.map((w) => w.owner);
    const filter = clear("timeline-filter");
    filter.append(h("span", { class: "label", text: U().showOnly }));
    ["all"].concat(members).forEach((m) => {
      const b = h("button", { type: "button", class: m === "all" ? null : "m-" + m, "aria-pressed": String(timelineWho === m), text: m === "all" ? U().everyone : memberLabel(m) });
      b.addEventListener("click", () => { timelineWho = m; saveWho(m); renderTimeline(); });
      filter.append(b);
    });

    const chip = (m) => h("span", { class: "who " + (m === "all" ? "all" : "m-" + m), text: m === "all" ? U().group : m });
    const list = clear("timeline-list");
    P.timeline.forEach((ph) => {
      const s = dayStart(ph.start), e = dayEnd(ph.end);
      const state = now > e ? "past" : now >= s ? "current" : "upcoming";
      const range = ph.start === ph.end ? fmtDay(s) : fmtDay(s) + " – " + fmtDay(e);
      const items = ph.items.filter((it) => timelineWho === "all" || it.who === "all" || [].concat(it.who).includes(timelineWho));
      list.append(h("li", { class: "phase " + state }, [
        h("div", { class: "when" }, [range, state === "current" ? h("div", { class: "badge", text: U().now }) : null]),
        h("div", {}, [
          h("h3", { text: tr(ph.title) }),
          ph.note ? h("p", { class: "phase-note", text: tr(ph.note) }) : null,
          h("ul", { class: "who-items" }, items.map((it) =>
            h("li", {}, [h("span", { class: "chips" }, [].concat(it.who).map(chip)), h("span", { text: tr(it) })])))
        ])
      ]));
    });
  }

  // Per-viewer timeline filter; storage may be unavailable.
  function loadWho() { try { return localStorage.getItem("timeline-who") || "all"; } catch (e) { return "all"; } }
  function saveWho(m) { try { localStorage.setItem("timeline-who", m); } catch (e) { /* storage unavailable */ } }
  let timelineWho = loadWho();

  // ---------- progress: one row per member, beside the cross-review diagram ----------
  function renderProgress() {
    const all = counts(P.workstreams.flatMap((w) => w.tasks));
    clear("progress-summary").append(
      h("span", { class: "big", text: all.pct + "%" }),
      barEl(all),
      h("span", { class: "counts" }, countSpans(all))
    );

    const list = clear("workstreams");
    P.workstreams.forEach((w) => {
      const k = counts(w.tasks);
      list.append(h("div", { class: "ws ws-row" + (w.owner ? " m-" + w.owner : "") }, [
        h("div", { class: "ws-row-head" }, [
          h("span", { class: "assign-badge", text: w.owner || "?" }),
          h("div", { class: "ws-row-title" }, [
            h("strong", { text: tr(w.name) }),
            h("span", { class: "ws-owner" + (w.owner ? "" : " open"), text: w.owner ? U().owner + tr(w.ownerName || w.owner) : U().unclaimed })
          ]),
          h("span", { class: "pct", text: k.pct + "%" })
        ]),
        barEl(k),
        h("p", { class: "ws-counts" }, countSpans(k))
      ]));
    });
  }

  // ---------- task assignment: one card per member, linking to the member's page ----------
  function renderAssignments() {
    const list = clear("assignments");
    P.workstreams.filter((w) => w.owner).forEach((w) => {
      const m = w.owner;
      const out = reviewee(m), inn = reviewer(m);
      list.append(h("a", { class: "card exp-card ws assign m-" + m, href: memberHref(m) }, [
        h("p", { class: "tag", text: tr(w.stage) }),
        h("div", { class: "assign-top" }, [
          h("span", { class: "assign-badge", text: m }),
          h("h3", { text: tr(w.ownerName || m) })
        ]),
        h("p", { class: "assign-ws", text: tr(w.name) }),
        h("p", { class: "assign-meta" }, [
          out ? h("span", {}, U().reviewing(out).join("")) : null,
          inn ? h("span", {}, U().reviewedBy(inn).join("")) : null,
          h("span", { text: U().taskCount(w.tasks.length) })
        ]),
        h("span", { class: "exp-foot" }, h("span", { class: "exp-open", text: U().openTasks }))
      ]));
    });
  }

  // ---------- cross-review ----------
  function svg(tag, attrs, children) {
    const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (const [k, v] of Object.entries(attrs || {})) node.setAttribute(k, v);
    for (const c of [].concat(children || [])) node.append(c);
    return node;
  }

  // Outer ring: A (top) and E (bottom) review each other. Inner ring: the experiment loop.
  // Review arcs run clockwise from reviewer to reviewee; dashed arrows are hand-offs between the rings.
  function reviewSvg(R, label) {
    const cx = 220, cy = 237;
    const root = svg("svg", { viewBox: "0 0 440 474", role: "img", "aria-label": label });
    const defs = svg("defs");
    R.outer.concat(R.inner, ["flow"]).forEach((k) => defs.append(svg("marker", {
      id: "review-arrow-" + k, class: k === "flow" ? "flow" : "m-" + k, viewBox: "0 0 10 10", refX: 9, refY: 5,
      markerWidth: 9, markerHeight: 9, markerUnits: "userSpaceOnUse", orient: "auto"
    }, svg("path", { d: "M0,0 L10,5 L0,10 z" }))));
    root.append(defs);

    function ring(members, cls, rad, r, start) {
      const n = members.length;
      const ang = (i) => start + (2 * Math.PI * i) / n;
      const pt = (a) => [cx + rad * Math.cos(a), cy + rad * Math.sin(a)].map((v) => +v.toFixed(1));
      const trim = (r + 6) / rad;
      const g = svg("g", { class: cls });
      members.forEach((m, i) => {
        const [x0, y0] = pt(ang(i) + trim), [x1, y1] = pt(ang(i + 1) - trim);
        g.append(svg("path", { class: "arc m-" + m, d: `M${x0},${y0} A${rad},${rad} 0 0 1 ${x1},${y1}`, "marker-end": `url(#review-arrow-${m})` }));
      });
      members.forEach((m, i) => {
        const [x, y] = pt(ang(i));
        g.append(svg("g", { class: "node m-" + m }, [svg("circle", { cx: x, cy: y, r }), svg("text", { x, y }, m)]));
      });
      return g;
    }
    function flow(x, y0, y1, text, side) {
      return svg("g", { class: "flow" }, [
        svg("line", { x1: x, y1: y0, x2: x, y2: y1, "marker-end": "url(#review-arrow-flow)" }),
        svg("text", { x: x + (side === "end" ? -8 : 8), y: (y0 + y1) / 2, "text-anchor": side }, tr(R.flows[text]))
      ]);
    }

    const outerR = 175, haloR = 96;
    root.append(svg("circle", { class: "halo", cx, cy, r: haloR }));
    root.append(ring(R.outer, "outer", outerR, 24, -Math.PI / 2));
    root.append(ring(R.inner, "inner", 58, 22, -Math.PI / 2));
    const [top, bottom] = R.outer;
    root.append(svg("text", { class: "role m-" + top, x: cx, y: cy - outerR - 46 }, tr(R.roles[top])));
    root.append(svg("text", { class: "role m-" + bottom, x: cx, y: cy + outerR + 48 }, tr(R.roles[bottom])));
    const yTop = cy - outerR + 30, yHaloTop = cy - haloR - 4, yHaloBot = cy + haloR + 4, yBot = cy + outerR - 30;
    root.append(flow(cx, yTop, yHaloTop, "tools", "start"));
    root.append(flow(cx - 16, yHaloBot, yBot, "results", "end"));
    root.append(flow(cx + 16, yBot, yHaloBot, "methods", "start"));
    return root;
  }

  function renderReview() {
    const R = P.review;
    const pairs = (m) => m.map((x, i) => U().reviews(x, m[(i + 1) % m.length]));
    const label = pairs(R.outer).concat(pairs(R.inner)).join(", ");
    // Names and workstreams are listed in the progress column beside the diagram, so no legend here.
    clear("review-map").append(reviewSvg(R, label));
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

  // ---------- nav menus ----------
  // Hover and keyboard focus open a group's menu in CSS; a tap toggles it here, for touch screens.
  function navMenus() {
    document.getElementById("nav-members").append(...P.workstreams.filter((w) => w.owner).map((w) =>
      h("a", { href: memberHref(w.owner) }, [h("span", { class: "who m-" + w.owner, text: w.owner }), " " + tr(w.ownerName || "")])));
    const groups = [...document.querySelectorAll(".nav-group")];
    const close = (g) => {
      g.classList.remove("open");
      g.querySelector(".nav-top").setAttribute("aria-expanded", "false");
    };
    groups.forEach((g) => {
      const top = g.querySelector(".nav-top");
      top.addEventListener("click", () => {
        const open = !g.classList.contains("open");
        groups.forEach(close);
        if (open) { g.classList.add("open"); top.setAttribute("aria-expanded", "true"); } else top.blur();
      });
      g.querySelectorAll("a").forEach((a) => a.addEventListener("click", () => { close(g); a.blur(); }));
    });
    document.addEventListener("click", (e) => { if (!e.target.closest(".nav-group")) groups.forEach(close); });
    document.addEventListener("keydown", (e) => {
      if (e.key !== "Escape") return;
      groups.forEach(close);
      if (document.activeElement && document.activeElement.closest(".nav-group")) document.activeElement.blur();
    });
  }

  // ---------- boot ----------
  function renderAll() {
    renderNextDeadline();
    renderAssignments();
    renderTimeline();
    renderProgress();
    renderReview();
    renderResources();
  }

  Site.init();
  navMenus();
  renderAll();
  const demo = ringDemo();
  Site.onChange(() => { renderAll(); demo.relabel(); });
  window.Team.onLive(() => { renderAssignments(); renderProgress(); });
  Site.renderMath();
})();
