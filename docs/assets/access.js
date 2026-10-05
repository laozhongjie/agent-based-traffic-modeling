(function () {
  "use strict";

  const storageKey = "traffic-site-access";
  const root = document.documentElement;
  let unlocked = false;
  try {
    unlocked = sessionStorage.getItem(storageKey) === "granted";
  } catch {}
  if (unlocked) {
    delete root.dataset.siteLocked;
    return;
  }

  root.dataset.siteLocked = "true";

  document.addEventListener("DOMContentLoaded", function () {
    const gate = document.createElement("main");
    gate.className = "access-gate";
    gate.innerHTML = `
      <form class="access-card" aria-labelledby="access-title">
        <p class="eyebrow">PC5253 · Project site</p>
        <h1 id="access-title">Enter password / 输入密码</h1>
        <p>Enter the shared password to visit the project website.<br>请输入公用密码以访问项目网站。</p>
        <label for="access-password">Password / 访问密码</label>
        <input id="access-password" type="password" autocomplete="current-password" required aria-describedby="access-error">
        <p id="access-error" class="access-error" role="alert"></p>
        <button class="btn primary" type="submit">Enter / 进入网站</button>
      </form>`;
    document.body.prepend(gate);

    const form = gate.querySelector("form");
    const input = gate.querySelector("input");
    const error = gate.querySelector(".access-error");

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      if (input.value !== "pc5253" && input.value !== "PC5253") {
        error.textContent = "Incorrect password. Try again. / 密码错误，请重试。";
        input.setAttribute("aria-invalid", "true");
        input.select();
        return;
      }
      try {
        sessionStorage.setItem(storageKey, "granted");
      } catch {}
      delete root.dataset.siteLocked;
      gate.remove();
      const firstControl = document.querySelector("a, button, input");
      if (firstControl) firstControl.focus({ preventScroll: true });
    });

    input.addEventListener("input", function () {
      error.textContent = "";
      input.removeAttribute("aria-invalid");
    });
    input.focus({ preventScroll: true });
  });
})();
