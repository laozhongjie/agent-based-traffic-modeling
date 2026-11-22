// Marks the results part in view in the sticky sub-navigation (index.html).
(function () {
  const links = [...document.querySelectorAll(".subnav a")];
  const parts = links.map(a => document.querySelector(a.getAttribute("href"))).filter(Boolean);
  if (!parts.length) return;
  function update() {
    const y = 140;
    let current = null;
    for (const p of parts) if (p.getBoundingClientRect().top <= y) current = p;
    const end = document.getElementById("results").getBoundingClientRect().bottom;
    if (end < y) current = null;
    links.forEach(a => a.classList.toggle("on", current && a.getAttribute("href") === "#" + current.id));
  }
  addEventListener("scroll", update, { passive: true });
  addEventListener("resize", update);
  update();
})();
