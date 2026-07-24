"use strict";

document.addEventListener("click", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) return;
  if (target.matches("[data-print]")) window.print();
  if (target.matches("[data-select-all], [data-select-none]")) {
    const checked = target.matches("[data-select-all]");
    document.querySelectorAll("input[name='selected']").forEach((input) => {
      if (input instanceof HTMLInputElement) input.checked = checked;
    });
  }
});
