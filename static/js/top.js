/* Top画面：UIサンプルの商品検索・カテゴリーフィルター・現在地取得。
   DB検索や店舗検索API・予約処理はフェーズ3まで実装しない。 */

document.addEventListener('DOMContentLoaded', () => {
  'use strict';

  const form = document.getElementById('frSearchForm');
  const input = document.getElementById('frSearchInput');
  const chips = Array.from(document.querySelectorAll('#frCategoryList [data-category]'));
  const cards = Array.from(document.querySelectorAll('#frProductGrid .fr-product-card'));
  const empty = document.getElementById('frEmpty');
  const reset = document.getElementById('frReset');
  const productsSection = document.getElementById('products');
  let activeCategory = 'all';

  // 画面確認用：表示されているサンプル商品のみを絞り込む。
  function filterCards() {
    if (!input || !empty) return;
    const query = input.value.trim().toLocaleLowerCase('ja-JP');
    let visibleCount = 0;
    for (const card of cards) {
      const categoryMatches = activeCategory === 'all' || card.dataset.category === activeCategory;
      const textMatches = !query || (card.dataset.search || '').toLocaleLowerCase('ja-JP').includes(query);
      card.hidden = !(categoryMatches && textMatches);
      if (!card.hidden) visibleCount += 1;
    }
    empty.hidden = visibleCount > 0;
  }

  if (form && input && empty) {
    // JavaScriptが利用できる場合はトップ画面内でサンプル検索。
    // JS無効の場合は既存の /products/list/ へGET遷移。
    form.addEventListener('submit', (event) => {
      event.preventDefault();
      filterCards();
      productsSection?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
    input.addEventListener('input', filterCards);

    chips.forEach((chip) => chip.addEventListener('click', () => {
      activeCategory = chip.dataset.category || 'all';
      chips.forEach((item) => {
        const selected = item === chip;
        item.classList.toggle('is-active', selected);
        item.setAttribute('aria-pressed', String(selected));
      });
      filterCards();
    }));

    reset?.addEventListener('click', () => {
      input.value = '';
      chips.find((chip) => chip.dataset.category === 'all')?.click();
      input.focus();
    });
  }

  // 画像ファイルがない場合は既存のプレースホルダー画像に切り替える。
  const placeholder = document.getElementById('frProductGrid')?.dataset.placeholderUrl;
  document.querySelectorAll('.fr-product-photo img').forEach((img) => {
    const replaceMissing = () => {
      if (placeholder && !img.src.endsWith('/images/placeholder.svg')) {
        img.src = placeholder;
      }
    };
    img.addEventListener('error', replaceMissing);
    if (img.complete && img.naturalWidth === 0) replaceMissing();
  });

  // 既存の位置情報取得機能を維持（店舗検索は未接続）。
  const locationButton = document.getElementById('locationButton');
  const locationMessage = document.getElementById('locationMessage');
  locationButton?.addEventListener('click', () => {
    if (!locationMessage) return;
    if (!navigator.geolocation) {
      locationMessage.textContent = 'このブラウザでは位置情報を利用できません。';
      return;
    }
    locationMessage.textContent = '現在地を取得しています…';
    navigator.geolocation.getCurrentPosition(
      () => { locationMessage.textContent = '現在地を取得しました。店舗検索機能は準備中です。'; },
      (error) => { locationMessage.textContent = error.code === 1 ? '位置情報の利用が許可されませんでした。' : '現在地を取得できませんでした。'; },
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 60000 },
    );
  });
});
