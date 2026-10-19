# 食品ロス削減システム (Django)

UIUXのHTML/CSS/JavaScriptサンプルを、Djangoのアプリ単位に再配置した開発用プロジェクトです。

## 技術構成
- Python 3.10 以上 + Django 5.2 LTS
- HTML / CSS / JavaScript
- SQLite（開発用）
- 日本語設定、Asia/Tokyoタイムゾーン

## セットアップ（Windows）

```powershell
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

http://127.0.0.1:8000/ を開いてください。

## Djangoアプリ

| App | 役割 |
|---|---|
| core | 入口・お問い合わせ・共通機能 |
| accounts | 顧客/店舗ログイン・会員登録・パスワード画面 |
| products | 顧客トップ・商品一覧/詳細 |
| stores | 店舗管理画面（現状プレースホルダー） |
| reservations | 予約画面（現状プレースホルダー） |

共通テンプレート: `templates/base.html` / `customer_base.html` / `shop_base.html`

## 元のUIUXからの変換
- 元のHTMLを**10ページ**移し、Django Template継承に変換しました。
- `index.html`のインラインCSS → `static/css/entry.css`
- `customer/top.html`のインラインCSS/JS → `static/css/top.css` / `static/js/top.js`
- `customer/logout.html`のインラインCSS → `static/css/logout.css`
- 共通CSS/JS → `static/css/style.css` / `static/js/demo.js`
- 顧客・店舗の認証ヘッダー → `templates/includes/header.html`
- 顧客トップのナビ → `templates/includes/navbar.html`
- 画面間リンクをDjangoの `{% url %}` に変更しました。
- 元サンプルの食品画像ファイル（bread.jpg等）は未提供です。`static/images/`に追加すれば表示されます。追加まで`placeholder.svg`が表示されます。

## 現在の制限
- Login/Signup/Password/Contactフォームは `data-demo` のままです。`demo.js` は送信を止めるため、実際の認証/送信は行いません。
- 登録・検索・予約・店舗管理は未実装。画面が不足する機能は「開発中」ページを表示します。
- ログアウト確認もデザインのみです。リンク先をログインへ移すだけでは実際のセッションは終了しません。
- 画像などのメディアアップロード機能は未実装です。
- `STATIC_ROOT`/`MEDIA_ROOT` を本番環境向けに設定してください。`DEBUG=True` は開発専用です。
- GitHubに仮想環境、秘密鍵、`.env`、`db.sqlite3` をコミットしないでください。

## URL一覧

| パス | 画面 |
|---|---|
| `/` | 入口 |
| `/accounts/customer/login/` | 顧客ログイン |
| `/accounts/customer/signup/` | 顧客会員登録 |
| `/accounts/customer/forgot/` | 顧客パスワード再設定 |
| `/accounts/customer/logout/` | 顧客ログアウト確認（UIのみ） |
| `/accounts/shop/login/` | 店舗ログイン |
| `/accounts/shop/forgot/` | 店舗パスワード再設定 |
| `/contact/` | 顧客お問い合わせ |
| `/shop/contact/` | 店舗お問い合わせ |
| `/products/` | 顧客トップ |
| `/products/list/` | 商品一覧（未実装） |
| `/products/detail/` | 商品詳細（未実装） |
| `/stores/` | 店舗ダッシュボード（未実装） |
| `/reservations/history/` | 予約履歴（未実装） |
