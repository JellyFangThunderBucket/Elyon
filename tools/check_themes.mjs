import assert from "node:assert/strict";
import { THEMES } from "../elyon/web/themes.js";
const luminance = (color) =>
  color
    .slice(1)
    .match(/../g)
    .map((x) => parseInt(x, 16) / 255)
    .map((x) => (x <= 0.04045 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4))
    .reduce((sum, n, i) => sum + n * [0.2126, 0.7152, 0.0722][i], 0);
const contrast = (a, b) => {
  const x = luminance(a),
    y = luminance(b);
  return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05);
};
assert.equal(THEMES.length, 20);
assert.equal(new Set(THEMES.map((t) => t.id)).size, 20);
assert.equal(new Set(THEMES.map((t) => JSON.stringify(t.tokens))).size, 20);
let minimum = Infinity;
for (const theme of THEMES)
  for (const background of ["bg", "surface"])
    for (const foreground of [
      "fg",
      "muted",
      "accent",
      "error",
      "warning",
      "success",
    ]) {
      const ratio = contrast(
        theme.tokens[background],
        theme.tokens[foreground],
      );
      minimum = Math.min(minimum, ratio);
      assert.ok(
        ratio >= 4.5,
        `${theme.id}: ${foreground} on ${background} = ${ratio}`,
      );
    }
console.log(
  `20 unique themes; minimum text contrast ${minimum.toFixed(2)}:1 at full opacity.`,
);
