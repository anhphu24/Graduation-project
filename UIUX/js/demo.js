document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("form[data-demo]").forEach((form) =>
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const m = form.querySelector(".message");
      const pw = form.querySelector("[name=password]");
      const pw2 = form.querySelector("[name=password_confirm]");
      if (pw && pw2 && pw.value !== pw2.value) {
        m.textContent = "パスワードが一致しません。";
        return;
      }
      m.textContent = "現在、この手続きはご利用いただけません。";
    }),
  );
  document.querySelectorAll("[data-toggle-password]").forEach((btn) =>
    btn.addEventListener("click", () => {
      const field = document.getElementById(btn.dataset.togglePassword);
      if (field) {
        field.type = field.type === "password" ? "text" : "password";
        btn.textContent = field.type === "password" ? "表示" : "非表示";
      }
    }),
  );
});
