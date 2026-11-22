// Public pages: keeps each range slider's filled share (--p) in step with its value, for the thin
// slider style in site.css. Sliders drawn later by the page scripts are picked up as well.
(function () {
  function paint(el) {
    const min = +el.min || 0, max = +el.max || 100, v = +el.value;
    el.style.setProperty("--p", (max > min ? (v - min) / (max - min) * 100 : 0) + "%");
  }
  function scan(root) { (root.querySelectorAll ? root : document).querySelectorAll('input[type="range"]').forEach(paint); }
  document.addEventListener("input", e => { if (e.target.matches && e.target.matches('input[type="range"]')) paint(e.target); });
  document.addEventListener("change", e => { if (e.target.matches && e.target.matches('input[type="range"]')) paint(e.target); });
  new MutationObserver(() => scan(document)).observe(document.documentElement, { childList: true, subtree: true });
  // Scripts may also set a slider's value directly (presets, playback), which fires no event.
  setInterval(() => scan(document), 400);
  scan(document);
})();
