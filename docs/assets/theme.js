// Day/night theme, shared by every page. Loaded in <head> without defer, so a saved
// theme is applied before the page is drawn. With nothing saved, the page follows the
// system setting (style.css). A page with a #theme-toggle button lets the visitor switch;
// the choice is saved and fires a "themechange" event on document for canvas redraws.

(function () {
  "use strict";

  const root = document.documentElement;
  try {
    const saved = localStorage.getItem("theme");
    if (saved === "light" || saved === "dark") root.dataset.theme = saved;
  } catch (e) { /* storage unavailable */ }

  function current() {
    if (root.dataset.theme) return root.dataset.theme;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  document.addEventListener("DOMContentLoaded", function () {
    const toggle = document.getElementById("theme-toggle");
    if (!toggle) return;
    toggle.addEventListener("click", function () {
      const next = current() === "dark" ? "light" : "dark";
      root.dataset.theme = next;
      try { localStorage.setItem("theme", next); } catch (e) { /* storage unavailable */ }
      document.dispatchEvent(new CustomEvent("themechange", { detail: next }));
    });
  });
})();
