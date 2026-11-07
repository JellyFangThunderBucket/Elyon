import { mkdir, readFile, writeFile, rm, copyFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";
import { resolve, dirname } from "node:path";
import { execFileSync } from "node:child_process";
const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const output = resolve(root, "dist/iphone-demo");
// This build owns this generated directory only. No application/server files are copied.
await rm(output, { recursive: true, force: true });
await mkdir(resolve(output, "fixtures"), { recursive: true });
const assets = {
  "index.html": "device-demo.html",
  "device-demo.js": "device-demo.js",
  "device-demo.css": "device-demo.css",
  "mobile-console.js": "mobile-console.js",
  "mobile-console.css": "mobile-console.css",
  "network.js": "network.js",
  "page-runtime.js": "page-runtime.js",
  "themes.js": "themes.js",
  "fixtures/response.json": "fixtures/response.json",
};
const hashes = {};
for (const [destination, source] of Object.entries(assets)) {
  const path = resolve(root, "elyon/web", source);
  await copyFile(path, resolve(output, destination));
  hashes[destination] = createHash("sha256")
    .update(await readFile(path))
    .digest("hex");
}
let commit = "unavailable",
  dirty = null;
try {
  commit = execFileSync("git", ["rev-parse", "HEAD"], { cwd: root })
    .toString()
    .trim();
  dirty = Boolean(
    execFileSync("git", ["status", "--porcelain"], { cwd: root })
      .toString()
      .trim(),
  );
} catch {}
await writeFile(
  resolve(output, "manifest.json"),
  JSON.stringify(
    {
      format: "elyon-static-demo/1",
      version: "0.4.0",
      commit,
      dirty,
      source: "page-instrumentation",
      nativeBridge: false,
      broker: false,
      assets: hashes,
    },
    null,
    2,
  ) + "\n",
);
await writeFile(resolve(output, ".nojekyll"), "");
console.log(
  "Built dist/iphone-demo: static assets only; no broker, API, Chii, or credentials.",
);
