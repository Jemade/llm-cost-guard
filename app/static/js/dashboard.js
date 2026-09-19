document.addEventListener("DOMContentLoaded", () => {
  const refreshBtn = document.getElementById("refresh-btn");
  if (refreshBtn) {
    refreshBtn.addEventListener("click", () => {
      window.location.reload();
    });
  }

  // Auto-refresh every 30 seconds
  const autoRefreshCheckbox = document.getElementById("auto-refresh-toggle");
  let intervalId = null;

  function updateAutoRefresh() {
    if (autoRefreshCheckbox && autoRefreshCheckbox.checked) {
      intervalId = setInterval(() => {
        window.location.reload();
      }, 30000);
    } else if (intervalId) {
      clearInterval(intervalId);
      intervalId = null;
    }
  }

  if (autoRefreshCheckbox) {
    autoRefreshCheckbox.addEventListener("change", updateAutoRefresh);
    updateAutoRefresh();
  }
});
