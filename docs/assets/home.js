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

  // Where the domed demo panel meets the findings band, round the two inner corners with a fillet.
  // The panel is clip-path: ellipse(50% 63% at 50% 63%) (site.css), so the fillet circle is fitted to that ellipse.
  const hero = document.querySelector(".hero");
  const panel = hero && hero.querySelector(".demo");
  if (panel) {
    const R = 44;
    const NS = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(NS, "svg");
    svg.setAttribute("aria-hidden", "true");
    svg.style.cssText = "position:absolute;left:0;top:0;overflow:visible;pointer-events:none;fill:var(--alt)";
    const path = document.createElementNS(NS, "path");
    svg.append(path);
    hero.style.position = "relative";
    hero.append(svg);
    const narrow = window.matchMedia("(max-width: 760px)");

    const draw = () => {
      if (narrow.matches) { path.removeAttribute("d"); return; }
      const h = hero.getBoundingClientRect(), p = panel.getBoundingClientRect();
      svg.setAttribute("width", h.width);
      svg.setAttribute("height", h.height);
      const ex = p.left - h.left + p.width / 2, rx = p.width / 2, ry = 0.63 * p.height;
      const ey = p.top - h.top + ry, floor = p.top - h.top + p.height;
      const tBottom = Math.asin((floor - ey) / ry);
      const pt = (t) => [ex + rx * Math.cos(t), ey + ry * Math.sin(t)];
      // Nearest point of the ellipse's lower right arc to (cx, cy).
      const nearest = (cx, cy) => {
        let best = [Infinity, 0];
        for (let i = 0; i <= 600; i++) {
          const t = tBottom * i / 600, [x, y] = pt(t), d = Math.hypot(x - cx, y - cy);
          if (d < best[0]) best = [d, t];
        }
        return best;
      };
      // Slide the circle along the floor until it just touches the ellipse.
      let lo = pt(tBottom)[0], hi = lo + 6 * R;
      for (let i = 0; i < 40; i++) {
        const mid = (lo + hi) / 2;
        if (nearest(mid, floor - R)[0] < R) lo = mid; else hi = mid;
      }
      const c = hi, tTouch = nearest(c, floor - R)[1];
      const side = (m) => {
        const X = (x) => (m ? 2 * ex - x : x).toFixed(1);
        let d = `M${X(pt(tBottom)[0])},${floor + 1}`;
        for (let i = 0; i <= 24; i++) {
          const [x, y] = pt(tBottom + (tTouch - tBottom) * i / 24);
          d += `L${X(x)},${y.toFixed(1)}`;
        }
        return d + `A${R},${R} 0 0 ${m ? 1 : 0} ${X(c)},${floor}L${X(c)},${floor + 1}Z`;
      };
      path.setAttribute("d", side(false) + side(true));
    };
    new ResizeObserver(draw).observe(hero);
    narrow.addEventListener("change", draw);
  }

})();
