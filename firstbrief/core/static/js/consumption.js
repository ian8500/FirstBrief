(() => {
  const viewer = document.querySelector("[data-view-timer]");
  const closeForm = document.querySelector("[data-close-form]");
  if (!viewer || !closeForm) return;

  const activeInput = closeForm.querySelector('input[name="active_seconds"]');
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
    if (document.visibilityState === "visible" && document.hasFocus() && recentlyActive) {
      activeSeconds += 1;
    }
  }, 1000);

  closeForm.addEventListener("submit", () => {
    activeInput.value = String(activeSeconds);
  });

  const frame = document.querySelector("[data-pdf-frame]");
  const progress = document.querySelector("[data-reading-progress]");
  const readingStatus = document.querySelector("[data-reading-status]");
  const positionForm = document.querySelector("[data-position-form]");
  const pagesElement = document.getElementById("protected-pdf-pages");
  const pages = pagesElement ? JSON.parse(pagesElement.textContent || "[]") : [];
  let currentPage = Math.max(1, Number(viewer.dataset.lastPage || 1));
  const totalPages = Math.max(1, pages.length);

  const savePosition = async () => {
    if (!positionForm || !viewer.dataset.positionUrl) return;
    const csrf = positionForm.querySelector('input[name="csrfmiddlewaretoken"]');
    const session = positionForm.querySelector('input[name="view_session"]');
    const body = new URLSearchParams({
      csrfmiddlewaretoken: csrf?.value || "",
      view_session: session?.value || "",
      page: String(currentPage),
      total_pages: String(totalPages),
    });
    try {
      await fetch(viewer.dataset.positionUrl, {
        method: "POST",
        body,
        credentials: "same-origin",
        headers: { "X-Requested-With": "XMLHttpRequest" },
      });
    } catch (_error) {
      // Position persistence is helpful but must never block protected reading.
    }
  };

  const showPage = (page, { focusHeading = false } = {}) => {
    currentPage = Math.min(Math.max(Number(page) || 1, 1), totalPages);
    if (frame) {
      const base = frame.getAttribute("src")?.split("#")[0] || "";
      frame.setAttribute("src", `${base}#page=${currentPage}`);
    }
    if (progress) progress.value = currentPage;
    if (readingStatus) readingStatus.textContent = `Page ${currentPage} of ${totalPages}`;
    document.querySelectorAll("[data-page]").forEach((control) => {
      control.setAttribute(
        "aria-current",
        Number(control.dataset.page) === currentPage ? "page" : "false",
      );
    });
    void savePosition();
    if (focusHeading) document.getElementById("content-heading")?.focus();
  };

  document.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof Element)) return;
    const pageControl = target.closest("[data-page]");
    if (pageControl instanceof HTMLButtonElement) {
      showPage(pageControl.dataset.page);
    }
  });

  if (pages.length) showPage(currentPage);

  const search = document.querySelector("[data-pdf-search]");
  const searchStatus = document.querySelector("[data-search-status]");
  const searchResults = document.querySelector("[data-search-results]");
  search?.addEventListener("input", () => {
    const query = search.value.trim().toLocaleLowerCase();
    searchResults.replaceChildren();
    if (query.length < 2) {
      searchStatus.textContent = "Enter at least two characters.";
      return;
    }
    const matches = pages.filter((page) => page.text.toLocaleLowerCase().includes(query));
    searchStatus.textContent = `${matches.length} matching page${matches.length === 1 ? "" : "s"}.`;
    matches.slice(0, 50).forEach((page) => {
      const item = document.createElement("li");
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.page = String(page.page);
      button.textContent = `${page.label}: ${page.excerpt}`;
      item.append(button);
      searchResults.append(item);
    });
  });

  const dialog = document.querySelector("[data-help-dialog]");
  const openHelp = document.querySelector("[data-help-open]");
  const closeHelp = document.querySelector("[data-help-close]");
  let helpReturnFocus = null;
  const showHelp = () => {
    if (!(dialog instanceof HTMLDialogElement)) return;
    helpReturnFocus = document.activeElement;
    dialog.showModal();
    closeHelp?.focus();
  };
  const hideHelp = () => {
    if (!(dialog instanceof HTMLDialogElement) || !dialog.open) return;
    dialog.close();
    if (helpReturnFocus instanceof HTMLElement) helpReturnFocus.focus();
  };
  openHelp?.addEventListener("click", showHelp);
  closeHelp?.addEventListener("click", hideHelp);

  document.addEventListener("keydown", (event) => {
    const target = event.target;
    const editing =
      target instanceof HTMLInputElement ||
      target instanceof HTMLTextAreaElement ||
      target instanceof HTMLSelectElement;
    if (event.key === "?" && !editing) {
      event.preventDefault();
      showHelp();
    } else if (event.key === "/" && !editing && search instanceof HTMLElement) {
      event.preventDefault();
      search.focus();
    } else if (event.key.toLocaleLowerCase() === "j" && !editing && pages.length) {
      event.preventDefault();
      showPage(currentPage + 1);
    } else if (event.key.toLocaleLowerCase() === "k" && !editing && pages.length) {
      event.preventDefault();
      showPage(currentPage - 1);
    } else if (event.key === "[" && !editing) {
      const previous = document.querySelector('a[rel="prev"]');
      if (previous instanceof HTMLAnchorElement) previous.click();
    } else if (event.key === "]" && !editing) {
      const next = document.querySelector('a[rel="next"]');
      if (next instanceof HTMLAnchorElement) next.click();
    }
  });

  const lifecycleAlert = document.querySelector("[data-lifecycle-alert]");
  const lifecycleTitle = document.querySelector("[data-lifecycle-title]");
  const sessionInput = closeForm.querySelector('input[name="view_session"]');
  const checkStatus = async () => {
    if (!viewer.dataset.statusUrl || !sessionInput?.value) return;
    const url = new URL(viewer.dataset.statusUrl, window.location.origin);
    url.searchParams.set("view_session", sessionInput.value);
    try {
      const response = await fetch(url, { credentials: "same-origin" });
      if (!response.ok) return;
      const state = await response.json();
      if (state.lifecycle_changed || (state.mandatory_at_open && !state.can_clear)) {
        if (lifecycleTitle) {
          lifecycleTitle.textContent = state.version_changed
            ? "A newer message version is available."
            : `Message is now ${state.status_label}.`;
        }
        if (lifecycleAlert) lifecycleAlert.hidden = false;
        closeForm.querySelectorAll('input[value="clear"]').forEach((input) => {
          input.disabled = true;
        });
      }
    } catch (_error) {
      // The next poll or server-side close validation remains authoritative.
    }
  };
  void checkStatus();
  window.setInterval(checkStatus, 30_000);
})();
