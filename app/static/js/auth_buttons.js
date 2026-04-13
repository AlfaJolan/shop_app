// static/js/auth_buttons.js

async function renderAuthButtons() {
  try {
    const resp = await fetch("/whoami", { credentials: "include" });
    const data = await resp.json();

    const container = document.getElementById("auth-buttons");
    if (!container) return;

    container.innerHTML = "";

    // --- Собираем действия в отдельные переменные, чтобы потом
    //     использовать их и для desktop-версии, и для mobile dropdown.
    //     Это позволяет не дублировать бизнес-логику по ролям в двух местах.
    let adminAction = "";
    let authAction = "";

    // Если залогинен
    if (data && data.role) {
      if (["admin", "seller", "picker"].includes(data.role)) {
        adminAction = `
          <a href="/admin/dashboard" class="btn btn-sm btn-outline-success">⚙️ Админка</a>
        `;
      }

      authAction = `
        <a href="/logout" class="btn btn-sm btn-outline-danger">🚪 Выйти</a>
      `;
    } else {
      // Если гость
      authAction = `
        <a href="/login" class="btn btn-sm btn-outline-primary">🔑 Войти</a>
      `;
    }

    // --- Отдельно собираем HTML корзины.
    //     В desktop-версии оставляем привычную длинную кнопку как и было.
    const desktopCartAction = `
      <a href="/cart" class="btn btn-sm btn-warning position-relative" id="cart-btn">
        🛒 Корзина (<span id="cart-count">${window.cart_count || 0}</span> шт,
        <span id="cart-sum">${window.cart_sum || 0}</span> ₸)
      </a>
    `;

    // --- Для мобильной версии делаем более компактный текст,
    //     чтобы dropdown выглядел чище и не был перегружен.
    const mobileCartAction = `
      <a href="/cart" class="auth-mobile-item auth-mobile-item-cart">
        <span>🛒 Корзина</span>
        <span class="auth-mobile-item-meta">
          <span id="cart-count-mobile">${window.cart_count || 0}</span> шт,
          <span id="cart-sum-mobile">${window.cart_sum || 0}</span> ₸
        </span>
      </a>
    `;

    // --- Рендерим сразу две версии:
    //     1) desktop-кнопки в ряд
    //     2) mobile dropdown
    //     Видимость между ними будет переключаться только CSS-ом.
    container.innerHTML = `
      <div class="auth-actions-desktop">
        ${adminAction}
        ${authAction}
        ${desktopCartAction}

        <button
          type="button"
          class="btn btn-sm btn-outline-danger clear-cart-btn"
          data-clear-cart="1"
        >
          🗑 Очистить
        </button>
      </div>

      <div class="auth-actions-mobile">
        <div class="dropdown w-100">
          <button
            class="btn btn-sm btn-outline-secondary auth-mobile-toggle dropdown-toggle w-100"
            type="button"
            data-bs-toggle="dropdown"
            data-bs-auto-close="outside"
            aria-expanded="false"
          >
            ☰ Меню
          </button>

          <div class="dropdown-menu auth-mobile-menu w-100">
            ${adminAction
              ? `
                <div class="auth-mobile-menu-section">
                  <a href="/admin/dashboard" class="auth-mobile-item">⚙️ Админка</a>
                </div>
              `
              : ""}

            <div class="auth-mobile-menu-section">
              ${
                data && data.role
                  ? `<a href="/logout" class="auth-mobile-item">🚪 Выйти</a>`
                  : `<a href="/login" class="auth-mobile-item">🔑 Войти</a>`
              }
            </div>

            <div class="auth-mobile-menu-section">
              ${mobileCartAction}
            </div>

            <div class="auth-mobile-menu-section auth-mobile-menu-section-danger">
              <button
                type="button"
                class="auth-mobile-item auth-mobile-item-danger clear-cart-btn"
                data-clear-cart="1"
              >
                🗑 Очистить корзину
              </button>
            </div>
          </div>
        </div>
      </div>
    `;

    // 🔹 Добавляем кнопку "Очистить корзину"
    // --- Раньше кнопка создавалась вручную через createElement и вставлялась после корзины.
    //     Теперь у нас две кнопки очистки: одна для desktop, вторая для mobile dropdown.
    //     Поэтому навешиваем общий обработчик на все элементы с data-clear-cart.
    const clearButtons = container.querySelectorAll('[data-clear-cart="1"]');

    const handleClearCart = async () => {
      const resp = await fetch("/cart/clear", {
        method: "POST",
        credentials: "include",
        headers: { Accept: "application/json" },
      });

      if (resp.ok) {
        // Обновляем счётчики
        const cartCount = document.getElementById("cart-count");
        const cartSum = document.getElementById("cart-sum");
        const cartCountMobile = document.getElementById("cart-count-mobile");
        const cartSumMobile = document.getElementById("cart-sum-mobile");

        if (cartCount) cartCount.textContent = 0;
        if (cartSum) cartSum.textContent = 0;
        if (cartCountMobile) cartCountMobile.textContent = 0;
        if (cartSumMobile) cartSumMobile.textContent = 0;

        // Дополнительно можно очистить страницу корзины
        if (window.location.pathname === "/cart") {
          const cartBody = document.getElementById("cart-body");
          const cartList = document.getElementById("cart-list");
          if (cartBody) cartBody.innerHTML = "";
          if (cartList) cartList.innerHTML = "";

          const cartTotal = document.getElementById("cart-total");
          const cartTotalMobile = document.getElementById("cart-total-mobile");

          if (cartTotal) cartTotal.textContent = "0 ₸";
          if (cartTotalMobile) cartTotalMobile.textContent = "Итого: 0 ₸";

          const emptyMsg = document.getElementById("empty-cart");
          if (emptyMsg) {
            emptyMsg.style.display = "block";
          } else {
            const p = document.createElement("p");
            p.id = "empty-cart";
            p.innerHTML = 'Корзина пуста. <a href="/" class="link-primary">Перейти в каталог</a>';
            document.querySelector("main .container").prepend(p);
          }
        }
      }
    };

    clearButtons.forEach((btn) => {
      btn.addEventListener("click", handleClearCart);
    });
  } catch (e) {
    console.error("Ошибка получения whoami", e);
  }
}

// вызвать при загрузке страницы
document.addEventListener("DOMContentLoaded", renderAuthButtons);