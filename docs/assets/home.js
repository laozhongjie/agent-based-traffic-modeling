// Public home page: language switch, ring-road demo and math.

(function () {
  "use strict";

  Site.init();
  const demo = window.ringDemo(Site.ui);
  Site.onChange(() => demo.relabel());
  Site.renderMath();

  // Figures open at full size in a new tab.
  document.querySelectorAll(".fig-card img").forEach((img) => {
    const a = document.createElement("a");
    a.href = img.getAttribute("src");
    a.target = "_blank";
    a.rel = "noopener";
    img.replaceWith(a);
    a.append(img);
  });

  // Tabs: a [data-tabs] box holds buttons [data-tab] and panels [data-panel] with the same names.
  document.querySelectorAll("[data-tabs]").forEach((box) => {
    const buttons = [...box.querySelectorAll(":scope > .tab-list [data-tab]")];
    const panels = [...box.querySelectorAll(":scope > [data-panel]")];
    const show = (name) => {
      buttons.forEach((b) => {
        const on = b.dataset.tab === name;
        b.classList.toggle("primary", on);
        b.setAttribute("aria-selected", on);
      });
      panels.forEach((p) => { p.hidden = p.dataset.panel !== name; });
    };
    buttons.forEach((b) => b.addEventListener("click", () => show(b.dataset.tab)));
  });
})();
