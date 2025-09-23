document.addEventListener("DOMContentLoaded", () => {
  let role = (window.currentRole || "guest").trim().toLowerCase();

  document.querySelectorAll(".col[data-roles]").forEach(el => {
    const allowed = el.dataset.roles
      .split(",")
      .map(r => r.trim().toLowerCase());

    if (!allowed.includes(role)) {
      el.style.display = "none";
    }
  });
});
