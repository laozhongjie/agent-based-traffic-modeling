// Helpers shared by the hub (app.js) and the member pages (member.js):
// DOM building, dates in Singapore time, members, cross-review and task progress.

(function () {
  "use strict";

  const P = window.PROJECT;
  const Site = window.Site;
  const TZ = "Asia/Singapore";
  const U = Site.ui;

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
    const base = Site.lang === "zh" ? { month: "long", day: "numeric" } : { day: "numeric", month: "short" };
    return date.toLocaleDateString(Site.lang === "zh" ? "zh-CN" : "en-GB", Object.assign(base, { timeZone: TZ }, opts));
  }

  // ---------- members ----------
  const member = (m) => P.workstreams.find((w) => w.owner === m);
  // A member's display name, e.g. "B Guowei"; falls back to the letter alone.
  function memberLabel(m) {
    const w = member(m);
    return w && w.ownerName ? m + " " + Site.tr(w.ownerName) : m;
  }
  const memberHref = (m, base) => (base || "") + "member.html?m=" + m;

  // Each review ring runs reviewer → next member; the last reviews the first.
  function reviewRing(m) { return [P.review.outer, P.review.inner].find((r) => r.includes(m)); }
  function reviewee(m) { const r = reviewRing(m); return r ? r[(r.indexOf(m) + 1) % r.length] : null; }
  function reviewer(m) { const r = reviewRing(m); return r ? r[(r.indexOf(m) + r.length - 1) % r.length] : null; }

  // ---------- live task status ----------
  // live.js fills `live` from Firebase ({ taskId: status }); without it the status in project.js is used.
  const STATUSES = ["todo", "doing", "done"];
  const live = {};
  const liveListeners = [];
  const sync = { state: "connecting", save: null };
  function setLive(map) {
    Object.keys(live).forEach((k) => delete live[k]);
    Object.assign(live, map);
    liveListeners.forEach((fn) => fn());
  }
  function setSync(state, save) {
    sync.state = state;
    if (save !== undefined) sync.save = save;
    liveListeners.forEach((fn) => fn());
  }
  const onLive = (fn) => liveListeners.push(fn);
  function statusOf(t) {
    const st = (t.id && live[t.id]) || t.status;
    return STATUSES.includes(st) ? st : "todo";
  }
  const nextStatus = (st) => STATUSES[(STATUSES.indexOf(st) + 1) % STATUSES.length];

  // ---------- progress ----------
  const WEIGHT = { done: 1, doing: 0.5, todo: 0 };
  function counts(tasks) {
    const c = { done: 0, doing: 0, todo: 0 };
    tasks.forEach((t) => { c[statusOf(t)]++; });
    const score = tasks.reduce((s, t) => s + WEIGHT[statusOf(t)], 0);
    return { c, total: tasks.length, pct: tasks.length ? Math.round((score / tasks.length) * 100) : 0 };
  }
  const countText = (n, key) => (Site.lang === "zh" ? U()[key] + " " + n : n + " " + U()[key]);
  const countSpans = (k) => ["done", "doing", "todo"].map((key) => h("span", { text: countText(k.c[key], key) }));
  function barEl(k) {
    const label = ["done", "doing", "todo"].map((key) => countText(k.c[key], key)).join(", ");
    return h("div", { class: "bar", role: "img", "aria-label": label }, [
      h("div", { class: "seg-done", style: "width:" + (k.c.done / k.total) * 100 + "%" }),
      h("div", { class: "seg-doing", style: "width:" + (k.c.doing / k.total) * 100 + "%" })
    ]);
  }
  // Each task shows its title and a short explanation. With `onToggle`, the status chip is a button
  // that passes the task and its next status.
  function taskList(tasks, onToggle) {
    return h("ul", { class: "tasks detailed" }, tasks.map((t) => {
      const st = statusOf(t);
      let chip;
      if (onToggle) {
        chip = h("button", { type: "button", class: "status status-btn " + st, "data-task": t.id,
          title: U().toggleHint(U().status[nextStatus(st)]) }, U().status[st]);
        chip.addEventListener("click", () => onToggle(t, nextStatus(st)));
      } else {
        chip = h("span", { class: "status " + st, text: U().status[st] });
      }
      return h("li", { class: st }, [
        chip,
        h("div", { class: "task-body" }, [
          h("span", { class: "text", text: Site.tr(t.text) }),
          t.detail ? h("p", { class: "task-detail", text: Site.tr(t.detail) }) : null
        ])
      ]);
    }));
  }

  window.Team = {
    TZ, h, dayStart, dayEnd, fmtDay,
    member, memberLabel, memberHref, reviewee, reviewer,
    counts, countText, countSpans, barEl, taskList,
    live, sync, setLive, setSync, onLive, statusOf
  };
})();
