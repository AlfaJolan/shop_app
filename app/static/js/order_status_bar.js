// static/js/order_status_bar.js

async function renderOrderStatusBar() {
  try {
    const resp = await fetch("/whoami", { credentials: "include" });
    const user = await resp.json();

    // Проверка роли
    if (!(user && ["admin", "seller", "picker"].includes(user.role))) {
      return; // гость → бар не нужен
    }

    // HTML для статус-бара
    const bar = document.createElement("div");
    bar.id = "order-status-bar";
    bar.className = "order-status-bar d-flex gap-3 justify-content-center py-2";

    bar.innerHTML = `
      <a href="/admin/orders/live?status=new" class="btn btn-outline-primary btn-sm">
        Новые <span id="status-new" class="badge bg-secondary">0</span>
      </a>
      <a href="/admin/orders/live?status=paid" class="btn btn-outline-success btn-sm">
        Оплачено <span id="status-paid" class="badge bg-secondary">0</span>
      </a>
      <a href="/admin/orders/live?status=packed" class="btn btn-outline-warning btn-sm">
        Собрано <span id="status-packed" class="badge bg-secondary">0</span>
      </a>
      <a href="/admin/orders/live?status=shipped" class="btn btn-outline-info btn-sm">
        Отправлено <span id="status-shipped" class="badge bg-secondary">0</span>
      </a>
    `;

    const navbar = document.querySelector("nav.navbar");
    if (navbar && !document.getElementById("order-status-bar")) {
      navbar.insertAdjacentElement("afterend", bar);

      // вычисляем высоту navbar → ставим отступ sticky панели
      const navHeight = navbar.offsetHeight;
      bar.style.top = navHeight + "px";
    }

    // CSS для панели и анимации
    if (!document.getElementById("order-status-style")) {
      const style = document.createElement("style");
      style.id = "order-status-style";
      style.textContent = `
        .order-status-bar {
          position: sticky;
          z-index: 1029;
          background: #fff;
          border-bottom: 1px solid #dee2e6;
          box-shadow: 0 2px 4px rgba(0,0,0,.05);
        }
        .order-status-bar .btn {
          font-weight: 500;
        }
        .status-updated {
          transition: background-color 0.6s ease, transform 0.3s ease;
          background-color: #dc3545 !important;
          transform: scale(1.2);
        }
      `;
      document.head.appendChild(style);
    }

    // Обновление числа с анимацией
    function updateStatus(el, newValue) {
      if (!el) return;
      const oldValue = parseInt(el.textContent, 10);
      if (oldValue !== newValue) {
        el.textContent = newValue;
        el.classList.add("status-updated");
        setTimeout(() => {
          el.classList.remove("status-updated");
        }, 600);
      }
    }

    // Подключение WS
    function connectWS() {
      const wsUrl =
        (location.protocol === "https:" ? "wss://" : "ws://") +
        location.host +
        "/admin/orders/status/ws/orders";

      const ws = new WebSocket(wsUrl);

      ws.onopen = () => console.log("✅ WS подключен:", wsUrl);
      ws.onclose = () => {
        console.log("❌ WS отключен, переподключение...");
        setTimeout(connectWS, 5000);
      };

      ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        if (msg.type === "status_counts") {
          for (const [status, count] of Object.entries(msg.counts)) {
            updateStatus(document.getElementById("status-" + status), count);
          }
        }
      };
    }

    connectWS();
  } catch (e) {
    console.error("Ошибка получения whoami:", e);
  }
}

document.addEventListener("DOMContentLoaded", renderOrderStatusBar);
