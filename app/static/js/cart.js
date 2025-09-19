// static/js/cart.js
// ====================================
// Перехватываем формы "Добавить в корзину" и отправляем их через fetch.
// После ответа от сервера обновляем количество и сумму в шапке (#cart-count и #cart-sum).

document.addEventListener("DOMContentLoaded", () => {
    // Находим все формы добавления в корзину
    const forms = document.querySelectorAll("form.cart-add-form");
  
    forms.forEach((form) => {
      form.addEventListener("submit", async (e) => {
        e.preventDefault(); // блокируем стандартную отправку
  
        try {
          const formData = new FormData(form);
  
          // Отправляем через fetch
          const resp = await fetch(form.action, {
            method: form.method,
            body: formData,
            headers: {
              Accept: "application/json", // ⚡ говорим серверу, что хотим JSON
            },
          });
  
          if (!resp.ok) {
            console.error("Ошибка при добавлении в корзину", resp.status);
            return;
          }
  
          const data = await resp.json();
  
          // Обновляем количество и сумму в шапке
          const countEl = document.getElementById("cart-count");
          const sumEl = document.getElementById("cart-sum");
  
          if (countEl) countEl.textContent = data.total_items ?? 0;
          if (sumEl) sumEl.textContent = data.total_sum ?? 0;
        } catch (err) {
          console.error("Ошибка сети:", err);
        }
      });
    });
  
    // 🔹 Перехватываем формы обновления корзины
    document.querySelectorAll("form.cart-update-form").forEach((form) => {
      form.addEventListener("submit", async (e) => {
        e.preventDefault();
  
        try {
          const formData = new FormData(form);
          const resp = await fetch(form.action, {
            method: form.method,
            body: formData,
            headers: { Accept: "application/json" },
          });
  
          if (!resp.ok) {
            console.error("Ошибка при обновлении корзины", resp.status);
            return;
          }
  
          const data = await resp.json();
  
          // Обновляем количество и сумму в шапке
          const countEl = document.getElementById("cart-count");
          const sumEl = document.getElementById("cart-sum");
          if (countEl) countEl.textContent = data.total_items ?? 0;
          if (sumEl) sumEl.textContent = data.total_sum ?? 0;
  
          // Обновляем строку таблицы или карточку
          if (data.updated) {
            const row = document.querySelector(
              `[data-variant-id="${data.updated.variant_id}"]`
            );
            if (row) {
              const lineTotalEl = row.querySelector(".line-total");
              if (lineTotalEl) {
                lineTotalEl.textContent = data.updated.line_total.toFixed(2) + " ₸";
              }
              const qtyInput = row.querySelector('input[name="qty"]');
              if (qtyInput) qtyInput.value = data.updated.qty;
            }
          }
  
          // Обновляем итого
          const totalEl = document.getElementById("cart-total");
          const totalMobile = document.getElementById("cart-total-mobile");
          if (totalEl) totalEl.textContent = data.total_sum.toFixed(2) + " ₸";
          if (totalMobile)
            totalMobile.textContent = "Итого: " + data.total_sum.toFixed(2) + " ₸";
        } catch (err) {
          console.error("Ошибка сети:", err);
        }
      });
    });
  
    // 🔹 Перехватываем формы удаления из корзины
    document.querySelectorAll("form.cart-remove-form").forEach((form) => {
      form.addEventListener("submit", async (e) => {
        e.preventDefault();
  
        try {
          const formData = new FormData(form);
          const resp = await fetch(form.action, {
            method: form.method,
            body: formData,
            headers: { Accept: "application/json" },
          });
  
          if (!resp.ok) {
            console.error("Ошибка при удалении из корзины", resp.status);
            return;
          }
  
          const data = await resp.json();
  
          // Обновляем количество и сумму в шапке
          const countEl = document.getElementById("cart-count");
          const sumEl = document.getElementById("cart-sum");
          if (countEl) countEl.textContent = data.total_items ?? 0;
          if (sumEl) sumEl.textContent = data.total_sum ?? 0;
  
          // Убираем строку из DOM
          if (data.removed_variant) {
            document
              .querySelectorAll(`[data-variant-id="${data.removed_variant}"]`)
              .forEach((el) => el.remove());
          }
  
          // Обновляем итого
          const totalEl = document.getElementById("cart-total");
          const totalMobile = document.getElementById("cart-total-mobile");
          if (totalEl) totalEl.textContent = data.total_sum.toFixed(2) + " ₸";
          if (totalMobile)
            totalMobile.textContent = "Итого: " + data.total_sum.toFixed(2) + " ₸";
  
          // Если корзина пустая — показать сообщение
          if (data.total_items === 0) {
            const cartBody = document.getElementById("cart-body");
            const cartList = document.getElementById("cart-list");
            if (cartBody) cartBody.innerHTML = "";
            if (cartList) cartList.innerHTML = "";
            const emptyMsg = document.getElementById("empty-cart");
            if (emptyMsg) {
              emptyMsg.style.display = "block";
            } else {
              const p = document.createElement("p");
              p.id = "empty-cart";
              p.innerHTML =
                'Корзина пуста. <a href="/" class="link-primary">Перейти в каталог</a>';
              document.querySelector("main .container").prepend(p);
            }
          }
        } catch (err) {
          console.error("Ошибка сети:", err);
        }
      });
    });
  });
  