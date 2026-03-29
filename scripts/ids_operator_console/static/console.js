(() => {
  document.documentElement.dataset.consoleEnhanced = "true";

  document.querySelectorAll("[data-client-stamp]").forEach((stamp) => {
    const raw = stamp.textContent?.trim();
    if (!raw) {
      return;
    }

    const parsed = new Date(raw);
    if (Number.isNaN(parsed.getTime())) {
      return;
    }

    stamp.title = raw;
    stamp.textContent = parsed.toLocaleString("vi-VN");
  });

  const body = document.body;
  const toggles = Array.from(document.querySelectorAll("[data-drawer-toggle]"));
  const closers = Array.from(document.querySelectorAll("[data-drawer-close]"));

  if (!body || toggles.length === 0) {
    return;
  }

  const setDrawerState = (open) => {
    body.dataset.navOpen = open ? "true" : "false";
    toggles.forEach((toggle) => {
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
  };

  toggles.forEach((toggle) => {
    toggle.addEventListener("click", () => {
      setDrawerState(body.dataset.navOpen !== "true");
    });
  });

  closers.forEach((closer) => {
    closer.addEventListener("click", () => {
      setDrawerState(false);
    });
  });

  window.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && body.dataset.navOpen === "true") {
      setDrawerState(false);
    }
  });

  window.addEventListener("resize", () => {
    if (window.innerWidth > 920 && body.dataset.navOpen === "true") {
      setDrawerState(false);
    }
  });
})();
