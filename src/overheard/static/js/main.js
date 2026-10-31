import { createStore } from "./core/store.js";

const store = createStore({ mode: 0 });
const buttons = [...document.querySelectorAll(".stepper button")];

buttons.forEach((b) => b.addEventListener("click", () => store.set({ mode: Number(b.dataset.mode) })));
document.addEventListener("keydown", (e) => {
  if (["1", "2", "3", "4"].includes(e.key) && !e.target.closest("input, textarea")) {
    store.set({ mode: Number(e.key) - 1 });
  }
});
store.subscribe(({ mode }) => {
  buttons.forEach((b) => b.setAttribute("aria-pressed", String(Number(b.dataset.mode) === mode)));
  document.body.dataset.mode = mode;
});
