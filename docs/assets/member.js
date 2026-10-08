// Member page: one member's workstream, tasks, cross-review and schedule.
// The member comes from ?m=<letter>; an unknown letter falls back to the first member.

(function () {
  "use strict";

  const P = window.PROJECT;
  const Site = window.Site;
  const tr = Site.tr;
  const U = Site.ui;
  const { h, dayStart, dayEnd, fmtDay, member, memberLabel, memberHref, reviewee, reviewer, counts, countSpans, barEl, taskList } = window.Team;

  const owners = P.workstreams.filter((w) => w.owner).map((w) => w.owner);
  const asked = (new URLSearchParams(location.search).get("m") || "").toUpperCase();
  const m = owners.includes(asked) ? asked : owners[0];
  const w = member(m);
  const now = new Date();

  const fill = (id, ...nodes) => { const el = document.getElementById(id); el.replaceChildren(...nodes.filter((n) => n != null)); return el; };
  const chip = (x) => h("span", { class: "who " + (x === "all" ? "all" : "m-" + x), text: x === "all" ? U().group : x });
  const personLink = (x) => h("a", { class: "member-link m-" + x, href: memberHref(x) }, [chip(x), " " + tr(member(x).ownerName || "")]);

  function renderNav() {
    const nav = document.getElementById("member-nav");
    nav.querySelectorAll(".member-tab").forEach((a) => a.remove());
    owners.forEach((x) => nav.append(h("a", {
      class: "member-tab m-" + x, href: memberHref(x), "aria-current": x === m ? "page" : null, text: memberLabel(x)
    })));
  }

  function renderHead() {
    const k = counts(w.tasks);
    fill("member-head",
      h("div", { class: "member-title" }, [
        h("span", { class: "assign-badge", text: m }),
        h("div", {}, [
          h("p", { class: "eyebrow", text: tr(w.stage) }),
          h("h1", { text: tr(w.name) }),
          h("p", { class: "ws-owner", text: U().owner + tr(w.ownerName || m) })
        ])
      ]),
      h("p", { class: "lede", text: tr(w.summary) }),
      h("div", { class: "progress-summary" }, [
        h("span", { class: "big", text: k.pct + "%" }),
        barEl(k),
        h("span", { class: "counts" }, countSpans(k))
      ])
    );
  }

  function renderTasks() {
    fill("member-tasks-h").textContent = U().tasksH;
    fill("member-tasks", taskList(w.tasks));
  }

  function renderReview() {
    const out = reviewee(m), inn = reviewer(m);
    const role = P.review.roles[m];
    fill("member-review-h").textContent = U().reviewH;
    fill("member-review",
      role ? h("p", { class: "member-role", text: tr(role) }) : null,
      h("ul", { class: "member-review-list" }, [
        out ? h("li", {}, U().reviewing(personLink(out)).concat(h("span", { class: "sub", text: tr(member(out).name) }))) : null,
        inn ? h("li", {}, U().reviewedBy(personLink(inn)).concat(h("span", { class: "sub", text: tr(member(inn).name) }))) : null
      ])
    );
  }

  // Timeline phases with this member's items and whole-group items.
  function renderSchedule() {
    fill("member-schedule-h").textContent = U().scheduleH;
    fill("member-schedule-note").textContent = U().scheduleNote;
    const mine = (it) => it.who === "all" || [].concat(it.who).includes(m);
    fill("member-schedule", ...P.timeline.filter((ph) => ph.items.some(mine)).map((ph) => {
      const s = dayStart(ph.start), e = dayEnd(ph.end);
      const state = now > e ? "past" : now >= s ? "current" : "upcoming";
      const range = ph.start === ph.end ? fmtDay(s) : fmtDay(s) + " – " + fmtDay(e);
      return h("li", { class: "phase " + state }, [
        h("div", { class: "when" }, [range, state === "current" ? h("div", { class: "badge", text: U().now }) : null]),
        h("div", {}, [
          h("h3", { text: tr(ph.title) }),
          ph.note ? h("p", { class: "phase-note", text: tr(ph.note) }) : null,
          h("ul", { class: "who-items" }, ph.items.filter(mine).map((it) =>
            h("li", {}, [h("span", { class: "chips" }, [].concat(it.who).map(chip)), h("span", { text: tr(it) })])))
        ])
      ]);
    }));
  }

  function renderAll() {
    document.getElementById("member").className = "wrap member-page m-" + m;
    ["member-tasks-card", "member-review-card"].forEach((id) => { document.getElementById(id).classList.add("m-" + m); });
    document.title = memberLabel(m) + " · " + tr(w.name) + " · Agent-Based Traffic Modeling";
    renderNav();
    renderHead();
    renderTasks();
    renderReview();
    renderSchedule();
  }

  Site.init();
  renderAll();
  Site.onChange(renderAll);
})();
