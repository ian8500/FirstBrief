(() => {
  const viewer = document.querySelector("[data-view-timer]");
  const form = document.querySelector("[data-close-form]");
  if (!viewer || !form) return;

  const input = form.querySelector('input[name="active_seconds"]');
  const idleSeconds = Number(viewer.dataset.idleSeconds || 60);
  let activeSeconds = 0;
  let lastActivity = Date.now();

  const noteActivity = () => {
    lastActivity = Date.now();
  };
  ["pointerdown", "keydown", "scroll", "touchstart"].forEach((eventName) => {
    document.addEventListener(eventName, noteActivity, { passive: true });
  });

  window.setInterval(() => {
    const recentlyActive = Date.now() - lastActivity <= idleSeconds * 1000;
    if (document.visibilityState === "visible" && recentlyActive) {
      activeSeconds += 1;
    }
  }, 1000);

  form.addEventListener("submit", () => {
    input.value = String(activeSeconds);
  });
})();
