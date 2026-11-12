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
});
