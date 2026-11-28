import { readFile, realpath, stat } from "node:fs/promises";
import { createServer } from "node:http";
import { extname, join, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import site from "../_data/site.js";

const contentTypes = {
  ".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8", ".mjs": "text/javascript; charset=utf-8",
  ".json": "application/json", ".xml": "application/rss+xml; charset=utf-8",
  ".wasm": "application/wasm", ".svg": "image/svg+xml", ".png": "image/png",
  ".webp": "image/webp", ".ico": "image/x-icon", ".woff2": "font/woff2",
};

// Serve the real build at its GitHub Pages project prefix. Missing resources
// remain 404s; an HTML fallback would hide broken RSS or Pagefind paths.
export async function startBuiltSite({
  root = fileURLToPath(new URL("../_site/", import.meta.url)),
  pathPrefix = site.pathPrefix,
} = {}) {
  const directory = await realpath(root);
  if (!pathPrefix.startsWith("/") || !pathPrefix.endsWith("/")) {
    throw new Error("The build server requires an absolute path prefix ending in /");
  }
  const inside = path => path === directory || path.startsWith(directory + sep);
  const server = createServer(async (request, response) => {
    const reject = status => { response.writeHead(status); response.end(); };
    try {
      if (!["GET", "HEAD"].includes(request.method)) return reject(405);
      const address = new URL(request.url, "http://127.0.0.1");
      const pathname = decodeURIComponent(address.pathname);
      if (!pathname.startsWith(pathPrefix) || /[\\\0]/.test(pathname)) return reject(404);
      let file = resolve(directory, pathname.slice(pathPrefix.length));
      if (!inside(file)) return reject(404);
      if ((await stat(file)).isDirectory()) {
        if (!pathname.endsWith("/")) {
          response.writeHead(301, { Location: address.pathname + "/" + address.search });
          return response.end();
        }
        file = join(file, "index.html");
      }
      if (!inside(await realpath(file))) return reject(404);
      const bytes = await readFile(file);
      response.writeHead(200, {
        "Content-Type": contentTypes[extname(file)] ?? "application/octet-stream",
        "Content-Length": bytes.length, "Cache-Control": "no-store",
      });
      response.end(request.method === "HEAD" ? undefined : bytes);
    } catch (error) {
      reject(error instanceof URIError ? 400 : ["ENOENT", "ENOTDIR"].includes(error.code) ? 404 : 500);
    }
  });
  server.requestTimeout = server.headersTimeout = 10_000;
  await new Promise((accept, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", accept);
  });
  const origin = `http://127.0.0.1:${server.address().port}`;
  return {
    origin,
    url(path = "") {
      if (/^(?:[a-z][a-z\d+.-]*:|\/\/)/i.test(path)) throw new Error("Expected a local site path");
      return origin + (path.startsWith(pathPrefix) ? path : pathPrefix + path.replace(/^\//, ""));
    },
    close: () => new Promise((accept, reject) => {
      server.close(error => error ? reject(error) : accept());
      server.closeAllConnections();
    }),
  };
}
