// Local dev server: serves public/ and runs api/*.js with Vercel-style req.query / res helpers.
const http = require("http"), fs = require("fs"), path = require("path"), url = require("url");
const ROOT = path.join(__dirname, ".."), PORT = +process.env.PORT || 4321;
const TYPES = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".ttf": "font/ttf", ".png": "image/png", ".jpg": "image/jpeg" };
http.createServer(async (req, res) => {
  const u = url.parse(req.url, true);
  if (u.pathname.startsWith("/api/")) {
    const f = path.join(ROOT, "api", u.pathname.slice(5).replace(/[^\w-]/g, "") + ".js");
    if (!fs.existsSync(f)) { res.statusCode = 404; return res.end("no"); }
    req.query = u.query;
    res.status = (c) => { res.statusCode = c; return res; };
    res.json = (o) => { res.setHeader("Content-Type", "application/json"); res.end(JSON.stringify(o)); };
    res.send = (b) => res.end(b);
    try { await require(f)(req, res); } catch (e) { res.statusCode = 500; res.end(String(e)); }
    return;
  }
  let p = path.join(ROOT, "public", decodeURIComponent(u.pathname));
  if (p.endsWith("/")) p += "index.html";
  if (!fs.existsSync(p)) { res.statusCode = 404; return res.end("not found"); }
  res.setHeader("Content-Type", TYPES[path.extname(p)] || "application/octet-stream");
  fs.createReadStream(p).pipe(res);
}).listen(PORT, () => console.log("http://localhost:" + PORT));
