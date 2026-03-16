// static/js/order_status_bar.js v2

async function renderOrderStatusBar() {
  try {
    const resp = await fetch("/whoami", { credentials: "include" });
    const user = await resp.json();

    if (!(user && ["admin", "seller", "picker"].includes(user.role))) {
      return;
    }

    if (document.getElementById("order-status-bar")) {
      return;
    }

    const bar = document.createElement("div");
    bar.id = "order-status-bar";
    bar.className = "order-status-bar";

    bar.innerHTML = `
      <div class="order-status-bar__inner">
        <a href="/admin/orders/live?status=new" class="order-status-chip is-new">
          <span class="order-status-chip__label">Новые</span>
          <span id="status-new" class="order-status-chip__count">0</span>
        </a>

        <a href="/admin/orders/live?status=paid" class="order-status-chip is-paid">
          <span class="order-status-chip__label">Оплачено</span>
          <span id="status-paid" class="order-status-chip__count">0</span>
        </a>

        <a href="/admin/orders/live?status=packed" class="order-status-chip is-packed">
          <span class="order-status-chip__label">Собрано</span>
          <span id="status-packed" class="order-status-chip__count">0</span>
        </a>

        <a href="/admin/orders/live?status=shipped" class="order-status-chip is-shipped">
          <span class="order-status-chip__label">Отправлено</span>
          <span id="status-shipped" class="order-status-chip__count">0</span>
        </a>
      </div>
    `;

    const navbar = document.querySelector("nav.navbar");
    if (navbar) {
      navbar.insertAdjacentElement("afterend", bar);

      const updateStickyOffset = () => {
        const navHeight = navbar.offsetHeight || 0;
        bar.style.top = `${navHeight}px`;
      };

      updateStickyOffset();
      window.addEventListener("resize", updateStickyOffset);
    }

    function updateStatus(el, newValue) {
      if (!el) return;

      const oldValue = parseInt(el.textContent || "0", 10);
      if (oldValue !== newValue) {
        el.textContent = String(newValue);
        el.classList.remove("is-updated");
        void el.offsetWidth;
        el.classList.add("is-updated");
      }
    }

    function connectWS() {
      const wsUrl =
        (location.protocol === "https:" ? "wss://" : "ws://") +
        location.host +
        "/admin/orders/status/ws/orders";

      const ws = new WebSocket(wsUrl);

      ws.onopen = () => console.log("WS connected:", wsUrl);

      ws.onclose = () => {
        console.log("WS disconnected, reconnecting...");
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

      ws.onerror = (err) => {
        console.error("WS error:", err);
        ws.close();
      };
    }

    connectWS();
  } catch (e) {
    console.error("Ошибка получения whoami:", e);
  }
}

document.addEventListener("DOMContentLoaded", renderOrderStatusBar);