/* Local preview only. Deploy the built files to an HTTPS static host for iPhone use. */
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { resolve, dirname, extname } from "node:path";
import { fileURLToPath } from "node:url";
const root = resolve(
  dirname(fileURLToPath(import.meta.url)),
  "../dist/iphone-demo",
);
const i = process.argv.indexOf("--port"),
  port = i < 0 ? 4173 : Number(process.argv[i + 1]);
if (!Number.isInteger(port) || port < 0 || port > 65535)
  throw Error("Invalid --port");
const allowed = new Set([
  "index.html",
  "device-demo.js",
  "device-demo.css",
  "mobile-console.js",
  "mobile-console.css",
  "network.js",
  "page-runtime.js",
  "themes.js",
  "fixtures/response.json",
  "manifest.json",
]);
const mime = {
  ".html": "text/html",
  ".js": "text/javascript",
  ".css": "text/css",
  ".json": "application/json",
};
const server = createServer(async (req, res) => {
  req.socket.setTimeout(3000);
  const path = (req.url || "/").split("?")[0];
  let file = path === "/" ? "index.html" : path.slice(1);
  if (!["GET", "HEAD"].includes(req.method) || !allowed.has(file)) {
    res.writeHead(404);
    res.end("Not found");
    return;
  }
  try {
    const data = await readFile(resolve(root, file));
    res.writeHead(200, {
      "Content-Type": mime[extname(file)],
      "Content-Length": data.length,
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
    });
    res.end(req.method === "HEAD" ? undefined : data);
  } catch {
    res.writeHead(404);
    res.end("Build the demo first: npm run build:demo");
  }
});
server.listen(port, "127.0.0.1", () =>
  console.log(`Elyon static demo: http://127.0.0.1:${server.address().port}`),
);
