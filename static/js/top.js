/* UIUX サンプル customer/top.html から移動 */

      const locationButton = document.getElementById("locationButton");

      const locationMessage = document.getElementById("locationMessage");

      locationButton.addEventListener("click", function () {
        if (!navigator.geolocation) {
          locationMessage.textContent =
            "このブラウザでは位置情報を利用できません。";

          return;
        }

        locationMessage.textContent = "現在地を取得しています…";

        navigator.geolocation.getCurrentPosition(
          function (position) {
            locationMessage.textContent =
              "現在地を取得しました。店舗検索機能は準備中です。";

            // 開発担当者が店舗データと連携する際に使用
            // position.coords.latitude
            // position.coords.longitude
          },

          function (error) {
            if (error.code === 1) {
              locationMessage.textContent =
                "位置情報の利用が許可されませんでした。";
            } else {
              locationMessage.textContent = "現在地を取得できませんでした。";
            }
          },

          {
            enableHighAccuracy: false,
            timeout: 10000,
            maximumAge: 60000,
          },
        );
      });
