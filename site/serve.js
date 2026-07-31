/* Minimal static server for local preview (dev.sh runs this in a container).
   Binds 0.0.0.0 so a published container port is reachable from the LAN. */
const http = require("http");
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(process.env.SITE_ROOT || path.join(__dirname, "_site"));
const PORT = Number(process.env.PORT) || 8080;
const MIME = {
  ".html": "text/html", ".css": "text/css", ".js": "text/javascript",
  ".json": "application/json", ".png": "image/png", ".svg": "image/svg+xml",
  ".ico": "image/x-icon", ".woff2": "font/woff2",
};

http
  .createServer((req, res) => {
    let p = path.normalize(path.join(ROOT, decodeURIComponent(req.url.split("?")[0])));
    if (!p.startsWith(ROOT)) { res.writeHead(403); return res.end(); }
    if (fs.existsSync(p) && fs.statSync(p).isDirectory()) p = path.join(p, "index.html");
    if (!fs.existsSync(p)) { res.writeHead(404); return res.end("not found"); }
    res.writeHead(200, { "content-type": MIME[path.extname(p)] || "application/octet-stream" });
    fs.createReadStream(p).pipe(res);
  })
  .listen(PORT, "0.0.0.0", () => console.log(`serving ${ROOT} on :${PORT}`));
