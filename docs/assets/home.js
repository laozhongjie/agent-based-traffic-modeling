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

})();
