// Shared by every page: language switching and LaTeX rendering.
// Pages call Site.init(), render their own content, then Site.renderMath().
// Math is written as \( ... \) inline or \[ ... \] display, in HTML, i18n.js and data files alike.

(function () {
  "use strict";

  const I = window.I18N;

  function initialLang() {
    try {
      const saved = localStorage.getItem("lang");
      if (saved === "en" || saved === "zh") return saved;
    } catch (e) { /* storage unavailable */ }
    return (navigator.language || "").toLowerCase().startsWith("zh") ? "zh" : "en";
  }

  let lang = initialLang();
  const listeners = [];

  // English text is the page's original markup; capture it once so we can switch back.
  const original = new Map();
  const originalAria = new Map();
  let originalTitle = "";

  const MATH_OPTIONS = {
    delimiters: [
      { left: "\\[", right: "\\]", display: true },
      { left: "\\(", right: "\\)", display: false }
    ],
    throwOnError: false
  };

  function renderMath(root) {
    // If the KaTeX CDN is unreachable, formulas simply stay as LaTeX source.
    if (typeof window.renderMathInElement === "function") {
      window.renderMathInElement(root || document.body, MATH_OPTIONS);
    }
  }

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
    const titleKey = document.body.dataset.titleKey || "meta.title";
    document.title = lang === "zh" && zh[titleKey] != null ? zh[titleKey] : originalTitle;
    document.documentElement.lang = lang === "zh" ? "zh-CN" : "en";
    const toggle = document.getElementById("lang-toggle");
    if (toggle) toggle.textContent = I.ui[lang].switchTo;
  }

  function setLang(next) {
    lang = next;
    try { localStorage.setItem("lang", lang); } catch (e) { /* storage unavailable */ }
    applyStatic();
    listeners.forEach((fn) => fn(lang));
    renderMath();
  }

  function init() {
    document.querySelectorAll("[data-i18n]").forEach((el) => original.set(el, el.innerHTML));
    document.querySelectorAll("[data-i18n-aria]").forEach((el) => originalAria.set(el, el.getAttribute("aria-label")));
    originalTitle = document.title;
    const toggle = document.getElementById("lang-toggle");
    if (toggle) toggle.addEventListener("click", () => setLang(lang === "zh" ? "en" : "zh"));
    applyStatic();
  }

  window.Site = {
    get lang() { return lang; },
    tr: (v) => (v == null ? "" : typeof v === "string" ? v : v[lang] != null ? v[lang] : v.en),
    ui: () => I.ui[lang],
    onChange: (fn) => listeners.push(fn),
    renderMath,
    init
  };
})();
