// GET /api/archive?u=<handle | subdomain | custom domain>  -> { name, pubs: [{ host, name }] }
// GET /api/archive?host=<host>&offset=N                     -> { n, posts: [...] } one page
//
// PAGING: the archive API caps a page at ~24 rows whatever `limit` asks for. A short page is NOT
// the last page (stopping there once dropped 19 posts from one export). The browser advances the
// offset by `n` (rows returned) and stops only when a page comes back empty. The browser drives the
// paging, one call per page, because a 2,440-post archive took 97 s to page server-side (Substack
// 429s bursts; 8 parallel pages were throttled within seconds) and a function call must stay short.
const { getJSON, cleanHost } = require("./_substack");

function row(host, pub, x) {
  return {
    host, pub, slug: x.slug, title: x.title || "", subtitle: x.subtitle || "",
    date: (x.post_date || "").slice(0, 10), audience: x.audience || "everyone",
    words: x.wordcount || 0, type: x.type || "newsletter",
    byline: x.publishedBylines && x.publishedBylines[0] ? x.publishedBylines[0].name : null,
  };
}

module.exports = async (req, res) => {
  const q = req.query || {};
  try {
    if (q.host) {
      const host = cleanHost(q.host), off = Math.max(0, parseInt(q.offset, 10) || 0);
      if (!host) return res.status(400).json({ error: "bad host" });
      const chunk = await getJSON(`https://${host}/api/v1/archive?sort=new&offset=${off}&limit=50`);
      const list = Array.isArray(chunk) ? chunk : [];
      res.setHeader("Cache-Control", "s-maxage=600, stale-while-revalidate=3600");
      return res.status(200).json({ n: list.length, posts: list.map((x) => row(host, q.pub || host, x)) });
    }

    const raw = String(q.u || "").trim().replace(/^@/, "").replace(/^https?:\/\//, "").replace(/\/.*$/, "");
    if (!raw) return res.status(400).json({ error: "Enter a Substack username." });
    let name = null, pubs = [];
    if (!raw.includes(".")) {
      if (!/^[\w-]{1,64}$/.test(raw)) return res.status(404).json({ error: `No Substack called "${raw}".` });
      try {
        const prof = await getJSON(`https://substack.com/api/v1/user/${encodeURIComponent(raw)}/public_profile`);
        name = prof.name || null;
        // One publication, never every newsletter the writer runs: the one whose subdomain is the
        // handle they typed, else their primary one. (aidanjude also runs randomaidan and
        // visionboards; merging them put Random posts in a Periodicals magazine, 2026-10-28.)
        const own = (prof.publicationUsers || []).map((pu) => pu.publication || {}).filter((p) => p.subdomain);
        const pick = own.find((p) => p.subdomain.toLowerCase() === raw.toLowerCase())
          || own.find((p) => prof.primaryPublication && p.subdomain === prof.primaryPublication.subdomain)
          || own[0];
        if (pick) pubs.push({ host: pick.custom_domain || `${pick.subdomain}.substack.com`, name: pick.name || pick.subdomain });
      } catch (e) { if (e.status && e.status !== 404) throw e; }
      if (!pubs.length) pubs = [{ host: `${raw.toLowerCase()}.substack.com`, name: raw }];
    } else {
      const h = cleanHost(raw);
      if (!h) return res.status(400).json({ error: "That doesn't look like a Substack address." });
      pubs = [{ host: h, name: h }];
    }
    // keep only publications that actually answer with posts
    const live = [];
    for (const p of pubs) {
      try {
        const first = await getJSON(`https://${p.host}/api/v1/archive?sort=new&offset=0&limit=1`);
        if (Array.isArray(first) && first.length) {
          live.push(p);
          if (!name && first[0].publishedBylines && first[0].publishedBylines[0]) name = first[0].publishedBylines[0].name;
        }
      } catch (e) { if (e.status === 429 || e.status >= 500) throw e; }
    }
    if (!live.length) return res.status(404).json({ error: `No Substack posts found for "${raw}". Check the spelling, or paste the newsletter's address.` });
    res.setHeader("Cache-Control", "s-maxage=600, stale-while-revalidate=3600");
    return res.status(200).json({ name: name || live[0].name, pubs: live });
  } catch (e) {
    return res.status(502).json({ error: "Substack is busy and didn't answer. Try again in a minute." });
  }
};
