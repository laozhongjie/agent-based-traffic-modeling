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

  // Units such as veh/km and km/h: wrap the slash in .u-sl (site.css) so it is drawn smaller.
  // Runs on prose only; formulas, code and already-wrapped text are left alone.
  const UNIT = /\b(veh|km|m|h|s)\/(km|h|s|lane)\b/g;
  function markUnits(root) {
    const walker = document.createTreeWalker(root || document.body, NodeFilter.SHOW_TEXT, {
      acceptNode: (n) => (UNIT.test(n.data) && (UNIT.lastIndex = 0, true) &&
        !n.parentElement.closest(".katex, script, style, code, pre, svg, canvas, .u-sl, .demo-controls"))
        ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT
    });
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach((n) => {
      const frag = document.createDocumentFragment();
      let last = 0;
      n.data.replace(UNIT, (m, a, b, i) => {
        frag.append(n.data.slice(last, i) + a);
        const sl = document.createElement("span");
        sl.className = "u-sl";
        sl.textContent = "/";
        frag.append(sl, b);
        last = i + m.length;
      });
      frag.append(n.data.slice(last));
      n.replaceWith(frag);
    });
  }

  function renderMath(root) {
    // If the KaTeX CDN is unreachable, formulas simply stay as LaTeX source.
    if (typeof window.renderMathInElement === "function") {
      window.renderMathInElement(root || document.body, MATH_OPTIONS);
    }
    markUnits(root);
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
