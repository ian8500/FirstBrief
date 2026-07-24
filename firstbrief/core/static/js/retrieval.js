(() => {
  const widgets = document.querySelectorAll("[data-autosuggest]");
  for (const widget of widgets) {
    const input = widget.querySelector("input");
    const list = widget.querySelector("datalist");
    const status = widget.querySelector("[data-suggest-status]");
    if (!input || !list || !status) continue;
    if (!input.getAttribute("list")) input.setAttribute("list", list.id);
    let controller = null;
    input.addEventListener("input", async () => {
      const term = input.value.trim();
      list.replaceChildren();
      if (controller) controller.abort();
      if (term.length < 3) {
        status.textContent = "Enter at least three characters.";
        return;
      }
      controller = new AbortController();
      try {
        const response = await fetch(`${widget.dataset.url}?q=${encodeURIComponent(term)}`, {
          credentials: "same-origin",
          headers: { Accept: "application/json" },
          signal: controller.signal,
        });
        if (!response.ok) throw new Error("Suggestion request failed");
        const payload = await response.json();
        for (const item of payload.results) {
          const option = document.createElement("option");
          option.value = item.value;
          option.label = item.label;
          list.append(option);
        }
        status.textContent = `${payload.results.length} suggestion${payload.results.length === 1 ? "" : "s"} available.`;
      } catch (error) {
        if (error.name !== "AbortError") status.textContent = "Suggestions are unavailable.";
      }
    });
  }
})();
