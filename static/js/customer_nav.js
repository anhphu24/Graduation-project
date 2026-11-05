document.addEventListener('DOMContentLoaded', () => {
  'use strict';

  const mobileMenu = window.matchMedia('(max-width: 650px)');
  const menus = document.querySelectorAll('.customer-menu');

  function syncMenuState() {
    menus.forEach((menu) => {
      if (mobileMenu.matches) {
        menu.removeAttribute('open');
      } else {
        menu.setAttribute('open', '');
      }
    });
  }

  syncMenuState();
  mobileMenu.addEventListener?.('change', syncMenuState);

  document.querySelectorAll('.customer-nav__link').forEach((link) => {
    link.addEventListener('click', () => {
      if (mobileMenu.matches) link.closest('.customer-menu')?.removeAttribute('open');
    });
  });
});
