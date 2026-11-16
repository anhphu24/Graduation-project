document.addEventListener('DOMContentLoaded', () => {
  const menu = document.querySelector('.customer-menu');
  if (menu) {
    document.addEventListener('click', (event) => {
      if (!menu.contains(event.target)) menu.open = false;
    });
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && menu.open) {
        menu.open = false;
        menu.querySelector('summary')?.focus();
      }
    });
    window.addEventListener('pageshow', () => {
      if (window.matchMedia('(max-width:650px)').matches) menu.open = false;
    });
  }
  const bottom = document.querySelector('.v2-bottom-nav');
  if (bottom) {
    document.addEventListener('focusin', (event) => {
      if (event.target.matches('input:not([type=checkbox]):not([type=radio]), textarea, select')) bottom.classList.add('is-keyboard-hidden');
    });
    document.addEventListener('focusout', () => {
      bottom.classList.remove('is-keyboard-hidden');
    });
  }
  const sidebar = document.querySelector('.v2-shop-sidebar');
  const toggle = document.querySelector('[data-v2-shop-menu]');
  if (sidebar && toggle) {
    const close = () => { sidebar.classList.remove('is-open'); toggle.setAttribute('aria-expanded', 'false'); };
    toggle.addEventListener('click', () => {
      const opened = sidebar.classList.toggle('is-open');
      toggle.setAttribute('aria-expanded', String(opened));
    });
    document.addEventListener('click', (event) => {
      if (!sidebar.contains(event.target) && !toggle.contains(event.target)) close();
    });
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') { close(); toggle.focus(); }
    });
    sidebar.querySelectorAll('a').forEach(a => a.addEventListener('click', close));
    window.addEventListener('pageshow', close);
    window.addEventListener('resize', () => { if (window.innerWidth > 830) close(); });
  }
  const productSelect = document.querySelector('.v2-lot-field--product select');
  const previewImage = document.getElementById('v2-product-preview');
  const previewName = document.getElementById('v2-product-preview-name');
  const previewData = document.getElementById('v2-product-previews');
  if (productSelect && previewImage && previewName && previewData) {
    let items = [];
    try { items = JSON.parse(previewData.textContent); } catch (_) { items = []; }
    const fallback = previewImage.getAttribute('src');
    const render = () => {
      const selected = items.find(item => String(item.id) === productSelect.value);
      previewName.textContent = selected ? selected.name : '商品を選択してください';
      previewImage.src = selected?.image_url || fallback;
      previewImage.onerror = () => { previewImage.onerror = null; previewImage.src = fallback; };
    };
    productSelect.addEventListener('change', render);
    render();
  }
  document.querySelectorAll('form[data-v2-once]').forEach(form => {
    form.addEventListener('submit', (event) => {
      if (form.dataset.v2Submitting === 'true') { event.preventDefault(); return; }
      if (!form.reportValidity()) { event.preventDefault(); return; }
      form.dataset.v2Submitting = 'true';
      const btn = form.querySelector('button[type=submit]');
      if (btn) { btn.setAttribute('aria-disabled', 'true'); btn.classList.add('is-submitting'); }
    });
  });
});
