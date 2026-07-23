document.querySelectorAll("[data-dual-list]").forEach((widget) => {
  const available = widget.querySelector("select:first-of-type");
  const selected = widget.querySelector("select:last-of-type");
  const move = (source, target) => {
    Array.from(source.selectedOptions).forEach((option) => target.append(option));
  };
  widget.querySelector("[data-dual-add]").addEventListener("click", () => move(available, selected));
  widget.querySelector("[data-dual-remove]").addEventListener("click", () => move(selected, available));
  widget.querySelector("[data-dual-add-all]").addEventListener("click", () => {
    Array.from(available.options).forEach((option) => { option.selected = true; });
    move(available, selected);
  });
  widget.querySelector("[data-dual-remove-all]").addEventListener("click", () => {
    Array.from(selected.options).forEach((option) => { option.selected = true; });
    move(selected, available);
  });
  widget.closest("form").addEventListener("submit", () => {
    Array.from(selected.options).forEach((option) => { option.selected = true; });
  });
});
