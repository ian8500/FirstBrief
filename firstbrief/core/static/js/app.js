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

window.addEventListener("load", () => {
  if (document.querySelector("[data-auto-print]")) window.print();
});

document.addEventListener("submit", (event) => {
  const form = event.target;
  if (!(form instanceof HTMLFormElement) || !form.matches("[data-loading-form]")) return;
  const message = form.querySelector("[data-loading-message]");
  if (message instanceof HTMLElement) message.hidden = false;
});

document.addEventListener("click", (event) => {
  const target = event.target;
  if (!(target instanceof Element)) return;
  const link = target.closest("[data-loading-link]");
  if (!(link instanceof HTMLAnchorElement)) return;
  const message = document.querySelector("[data-dashboard-loading]");
  if (message instanceof HTMLElement) message.hidden = false;
});
