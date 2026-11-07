import { THEMES, applyTheme } from "./themes.js";
const key = "elyon.workbench.theme.v1";
let selected = "basalt-circuit";
try {
  selected = localStorage.getItem(key) || selected;
} catch {}
const apply = (id) => {
  selected = applyTheme(document.documentElement, id).id;
  document
    .querySelectorAll("[data-workbench-theme]")
    .forEach((b) =>
      b.setAttribute(
        "aria-pressed",
        String(b.dataset.workbenchTheme === selected),
      ),
    );
};
for (const theme of THEMES) {
  const button = document.createElement("button");
  button.dataset.workbenchTheme = theme.id;
  button.setAttribute("aria-label", theme.name);
  const swatches = document.createElement("span");
  swatches.className = "theme-swatches";
  for (const color of [
    theme.tokens.bg,
    theme.tokens.surface,
    theme.tokens.accent,
  ]) {
    const i = document.createElement("i");
    i.style.background = color;
    swatches.append(i);
  }
  const label = document.createElement("span");
  label.textContent = theme.name;
  button.append(swatches, label);
  button.onclick = () => {
    apply(theme.id);
    try {
      localStorage.setItem(key, selected);
      document.querySelector("#theme-save-state").textContent = "Theme saved.";
    } catch {
      document.querySelector("#theme-save-state").textContent =
        "Theme applied for this session; storage is unavailable.";
    }
  };
  document.querySelector("#workbench-themes").append(button);
}
apply(selected);
