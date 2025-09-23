async function renderAuthButtons() {
  try {
    const resp = await fetch("/whoami", { credentials: "include" });
    const data = await resp.json();

    const container = document.getElementById("auth-buttons");
    container.innerHTML = "";

    if (data && data.role) {
      // Если залогинен
      if (["admin", "seller", "picker"].includes(data.role)) {
        container.innerHTML += `<a href="/admin" class="btn btn-sm btn-outline-success">⚙️ Админка</a>`;
      }
      container.innerHTML += `<a href="/logout" class="btn btn-sm btn-outline-danger">🚪 Выйти</a>`;
    } else {
      // Если гость
      container.innerHTML = `<a href="/login" class="btn btn-sm btn-outline-primary">🔑 Войти</a>`;
    }

    // Корзину оставляем как есть
    container.innerHTML += `
      <a href="/cart" class="btn btn-sm btn-warning position-relative">
        🛒 Корзина (<span id="cart-count">${window.cart_count || 0}</span> шт,
        <span id="cart-sum">${window.cart_sum || 0}</span> ₸)
      </a>
    `;
  } catch (e) {
    console.error("Ошибка получения whoami", e);
  }
}

// вызвать при загрузке страницы
document.addEventListener("DOMContentLoaded", renderAuthButtons);