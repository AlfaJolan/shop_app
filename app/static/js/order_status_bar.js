// static/js/order_status_bar.js

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

    // Вшиваем стили один раз, чтобы их не перебивали другие CSS
    if (!document.getElementById("order-status-bar-style")) {
      const style = document.createElement("style");
      style.id = "order-status-bar-style";
      style.textContent = `
        #order-status-bar {
          position: sticky !important;
          z-index: 1029 !important;
          background: #fff !important;
          border-bottom: 1px solid #dee2e6 !important;
          box-shadow: 0 2px 6px rgba(0,0,0,.05) !important;
          width: 100% !important;
        }

        #order-status-bar .order-status-bar__inner {
          max-width: 1320px !important;
          margin: 0 auto !important;
          padding: 12px 14px !important;
          display: grid !important;
          grid-template-columns: repeat(4, minmax(0, 1fr)) !important;
          gap: 10px !important;
          box-sizing: border-box !important;
        }

        #order-status-bar .order-status-chip {
          display: flex !important;
          justify-content: space-between !important;
          align-items: center !important;
          gap: 10px !important;
          padding: 10px 14px !important;
          border-radius: 14px !important;
          font-weight: 600 !important;
          font-size: 14px !important;
          text-decoration: none !important;
          transition: all .15s ease !important;
          background: #fff !important;
          border: 1px solid #e5e7eb !important;
          box-shadow: 0 1px 3px rgba(0,0,0,.06) !important;
          min-width: 0 !important;
          box-sizing: border-box !important;
        }

        #order-status-bar .order-status-chip:hover {
          transform: translateY(-1px) !important;
          box-shadow: 0 4px 10px rgba(0,0,0,.06) !important;
        }

        #order-status-bar .order-status-chip__label {
          font-weight: 700 !important;
          line-height: 1.1 !important;
          font-size: 14px !important;
          white-space: nowrap !important;
        }

        #order-status-bar .order-status-chip__count {
          min-width: 24px !important;
          height: 24px !important;
          padding: 0 8px !important;
          border-radius: 999px !important;
          background: #6b7280 !important;
          color: #fff !important;
          display: inline-flex !important;
          align-items: center !important;
          justify-content: center !important;
          font-size: 12px !important;
          font-weight: 800 !important;
          line-height: 1 !important;
          flex-shrink: 0 !important;
          transition: transform .22s ease, background-color .22s ease !important;
        }

        #order-status-bar .order-status-chip__count.is-updated {
          animation: orderStatusBounce .45s ease !important;
          background: #dc2626 !important;
        }

        #order-status-bar .order-status-chip.is-new {
          border-color: #93c5fd !important;
        }
        #order-status-bar .order-status-chip.is-new .order-status-chip__label {
          color: #2563eb !important;
        }

        #order-status-bar .order-status-chip.is-paid {
          border-color: #86efac !important;
        }
        #order-status-bar .order-status-chip.is-paid .order-status-chip__label {
          color: #15803d !important;
        }

        #order-status-bar .order-status-chip.is-packed {
          border-color: #fcd34d !important;
        }
        #order-status-bar .order-status-chip.is-packed .order-status-chip__label {
          color: #ca8a04 !important;
        }

        #order-status-bar .order-status-chip.is-shipped {
          border-color: #67e8f9 !important;
        }
        #order-status-bar .order-status-chip.is-shipped .order-status-chip__label {
          color: #0891b2 !important;
        }

        @keyframes orderStatusBounce {
          0% { transform: scale(1); }
          35% { transform: scale(1.18); }
          100% { transform: scale(1); }
        }

        /* Планшеты и телефоны */
        @media (max-width: 767.98px) {
          #order-status-bar .order-status-bar__inner {
            grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
            gap: 8px !important;
            padding: 10px 12px !important;
          }

          #order-status-bar .order-status-chip {
            padding: 9px 12px !important;
            border-radius: 12px !important;
            font-size: 13px !important;
          }

          #order-status-bar .order-status-chip__label {
            font-size: 13px !important;
          }

          #order-status-bar .order-status-chip__count {
            min-width: 22px !important;
            height: 22px !important;
            font-size: 11px !important;
            padding: 0 7px !important;
          }
        }

        /* Очень узкие экраны */
        @media (max-width: 420px) {
          #order-status-bar .order-status-bar__inner {
            grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
            gap: 8px !important;
            padding: 8px 10px !important;
          }

          #order-status-bar .order-status-chip {
            padding: 8px 10px !important;
          }

          #order-status-bar .order-status-chip__label {
            font-size: 12px !important;
          }
        }
      `;
      document.head.appendChild(style);
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