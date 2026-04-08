// static/js/auth_buttons.js

async function renderAuthButtons() {
  try {
    const resp = await fetch("/whoami", { credentials: "include" });
    const data = await resp.json();

    const container = document.getElementById("auth-buttons");
    container.innerHTML = "";

    // Если залогинен
    if (data && data.role) {
      if (["admin", "seller", "picker"].includes(data.role)) {
        container.innerHTML += `
          <a href="/admin/dashboard" class="btn btn-sm btn-outline-success">⚙️ Админка</a>
        `;
      }
      container.innerHTML += `
        <a href="/logout" class="btn btn-sm btn-outline-danger">🚪 Выйти</a>
      `;
    } else {
      // Если гость
      container.innerHTML += `
        <a href="/login" class="btn btn-sm btn-outline-primary">🔑 Войти</a>
      `;
    }

    // Добавляем корзину
    container.innerHTML += `
      <a href="/cart" class="btn btn-sm btn-warning position-relative" id="cart-btn">
        🛒 Корзина (<span id="cart-count">${window.cart_count || 0}</span> шт,
        <span id="cart-sum">${window.cart_sum || 0}</span> ₸)
      </a>
    `;

    // 🔹 Добавляем кнопку "Очистить корзину"
    const clearBtn = document.createElement("button");
    clearBtn.id = "clear-cart";
    clearBtn.className = "btn btn-sm btn-outline-danger";
    clearBtn.textContent = "🗑 Очистить";

    clearBtn.onclick = async () => {
      const resp = await fetch("/cart/clear", {
        method: "POST",
        credentials: "include",
        headers: { Accept: "application/json" },
      });

      if (resp.ok) {
        // Обновляем счётчики
        document.getElementById("cart-count").textContent = 0;
        document.getElementById("cart-sum").textContent = 0;

        // Дополнительно можно очистить страницу корзины
        if (window.location.pathname === "/cart") {
          const cartBody = document.getElementById("cart-body");
          const cartList = document.getElementById("cart-list");
          if (cartBody) cartBody.innerHTML = "";
          if (cartList) cartList.innerHTML = "";
          document.getElementById("cart-total").textContent = "0 ₸";
          document.getElementById("cart-total-mobile").textContent = "Итого: 0 ₸";
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

    // Вставляем кнопку сразу после корзины
    const cartBtn = document.getElementById("cart-btn");
    if (cartBtn) {
      cartBtn.insertAdjacentElement("afterend", clearBtn);
    }
  } catch (e) {
    console.error("Ошибка получения whoami", e);
  }
}

// вызвать при загрузке страницы
document.addEventListener("DOMContentLoaded", renderAuthButtons);
