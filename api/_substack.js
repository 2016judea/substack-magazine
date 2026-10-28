// Shared helpers for the Substack proxy. Substack's API is public and keyless, but it sends no
// CORS headers, so the browser can't call it directly.
const UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36";

// Substack rate-limits bursts with HTTP 429; back off (honouring Retry-After) rather than fail.
async function getJSON(url, tries = 5) {
  for (let a = 0; ; a++) {
    const r = await fetch(url, { headers: { "User-Agent": UA, Accept: "application/json" } });
    if (r.ok) return r.json();
    if ((r.status === 429 || r.status >= 500) && a < tries - 1) {
      const ra = +r.headers.get("retry-after");
      await new Promise((ok) => setTimeout(ok, ra > 0 && ra < 10 ? ra * 1000 : 800 * (a + 1)));
      continue;
    }
    const e = new Error(`HTTP ${r.status} for ${url}`); e.status = r.status; throw e;
  }
}

// A base is https://<sub>.substack.com or https://<custom domain>. Refuse anything that is not a
// plain public hostname, so the proxy can't be pointed at localhost or an IP.
function cleanHost(h) {
  h = String(h || "").trim().toLowerCase().replace(/^https?:\/\//, "").replace(/\/.*$/, "");
  if (!/^[a-z0-9-]+(\.[a-z0-9-]+)+$/.test(h)) return null;
  if (/^\d+(\.\d+)+$/.test(h) || h.endsWith(".local") || h.includes("localhost")) return null;
  return h;
}

module.exports = { UA, getJSON, cleanHost };
