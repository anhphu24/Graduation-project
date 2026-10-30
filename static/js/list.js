
document.addEventListener("DOMContentLoaded", function () {
    const params = new URLSearchParams(window.location.search);

    const pageType = params.get("type") === "bargain"
        ? "bargain"
        : "near_expiry";

    const pageTitle = document.getElementById("pageTitle");
    const pageDescription = document.getElementById("pageDescription");
    const breadcrumbCurrent = document.getElementById("breadcrumbCurrent");

    const expirySearchArea = document.getElementById("expirySearchArea");
    const budgetSearchArea = document.getElementById("budgetSearchArea");
    const listResults = document.getElementById("listResults");

    const resultHeading = document.getElementById("resultHeading");
    const resultDescription = document.getElementById("resultDescription");
    const resultCount = document.getElementById("resultCount");

    const productGrid = document.getElementById("productGrid");
    const emptyMessage = document.getElementById("emptyMessage");

    const budgetInput = document.getElementById("budgetInput");
    const budgetSearchButton = document.getElementById("budgetSearchButton");
    const budgetError = document.getElementById("budgetError");

    if (!productGrid) {
        return;
    }

    // Djangoから表示された商品を取得
    const productCards = Array.from(
        productGrid.querySelectorAll(".list-product-card")
    );

    // 予算検索結果を表示
    function searchBudgetProducts() {
        if (!budgetInput) {
            return;
        }

        const inputValue = budgetInput.value.trim();

        if (budgetError) {
            budgetError.hidden = true;
            budgetError.textContent = "";
        }

        // 未入力の場合
        if (inputValue === "") {
            if (budgetError) {
                budgetError.textContent =
                    "予算を入力してください。";
                budgetError.hidden = false;
            }

            budgetInput.focus();
            return;
        }

        const budget = Number(inputValue);

        // 入力値チェック
        if (!Number.isSafeInteger(budget) || budget <= 0) {
            if (budgetError) {
                budgetError.textContent =
                    "1円以上の予算を正しく入力してください。";
                budgetError.hidden = false;
            }

            budgetInput.focus();
            return;
        }

        let visibleCount = 0;

        // 現在のページの商品を予算で絞り込む
        productCards.forEach(function (card) {
            const price = Number(card.dataset.price);

            const isVisible =
                Number.isFinite(price) &&
                price <= budget;

            card.hidden = !isVisible;
            card.style.display = isVisible ? "" : "none";

            if (isVisible) {
                visibleCount++;
            }
        });

        // 検索後に商品一覧を表示
        if (listResults) {
            listResults.hidden = false;
        }

        if (resultHeading) {
            resultHeading.textContent =
                budget.toLocaleString() + "円以内の商品一覧";
        }

        if (resultDescription) {
            resultDescription.textContent =
                "現在のページから予算以内の商品を表示しています。";
        }

        if (resultCount) {
            resultCount.textContent =
                visibleCount + "件の商品（このページ）";
        }

        if (emptyMessage) {
            emptyMessage.hidden = visibleCount > 0;
        }
    }

    // 画面の切り替え
    if (pageType === "bargain") {

        // お買い得商品：予算検索画面
        if (pageTitle) {
            pageTitle.textContent =
                "予算からお買い得商品を探す";
        }

        if (pageDescription) {
            pageDescription.textContent =
                "ご希望の予算に合わせて、おトクな商品を見つけましょう。";
        }

        if (breadcrumbCurrent) {
            breadcrumbCurrent.textContent =
                "お買い得商品検索";
        }

        if (expirySearchArea) {
            expirySearchArea.hidden = true;
        }

        if (budgetSearchArea) {
            budgetSearchArea.hidden = false;
        }

        // 検索するまで商品一覧を非表示
        if (listResults) {
            listResults.hidden = true;
        }

    } else {

        // 消費期限間近の商品一覧
        if (pageTitle) {
            pageTitle.textContent =
                "消費期限間近の商品一覧";
        }

        if (pageDescription) {
            pageDescription.textContent =
                "まだおいしく食べられる商品を、おトクに購入して食品ロスを減らしましょう。";
        }

        if (breadcrumbCurrent) {
            breadcrumbCurrent.textContent =
                "消費期限間近の商品";
        }

        if (expirySearchArea) {
            expirySearchArea.hidden = false;
        }

        if (budgetSearchArea) {
            budgetSearchArea.hidden = true;
        }

        // 商品一覧を最初から表示
        if (listResults) {
            listResults.hidden = false;
        }

        if (resultHeading) {
            resultHeading.textContent =
                "消費期限間近の商品一覧";
        }

        if (resultDescription) {
            resultDescription.textContent =
                "現在予約できる商品を表示しています。";
        }
    }

    // 検索ボタン
    if (budgetSearchButton) {
        budgetSearchButton.addEventListener(
            "click",
            searchBudgetProducts
        );
    }

    // Enterキーで検索
    if (budgetInput) {
        budgetInput.addEventListener("keydown", function (event) {
            if (event.key === "Enter") {
                event.preventDefault();
                searchBudgetProducts();
            }
        });
    }
});
