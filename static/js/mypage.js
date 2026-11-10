document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('form[data-disable-on-submit]').forEach((form) => {
    form.addEventListener('submit', (event) => {
      const button = event.submitter || form.querySelector('button[type="submit"]');
      if (!button || !form.checkValidity()) return;

      button.disabled = true;
      button.setAttribute('aria-busy', 'true');
      if (button.dataset.submittingLabel) {
        button.textContent = button.dataset.submittingLabel;
      }
    });
  });
});
