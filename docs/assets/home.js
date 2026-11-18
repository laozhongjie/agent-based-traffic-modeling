// Public home page: language switch, ring-road demo and math.

(function () {
  "use strict";

  Site.init();
  const demo = window.ringDemo(Site.ui);
  Site.onChange(() => demo.relabel());
  Site.renderMath();
})();
