// GET /api/post?host=<host>&slug=<slug>  -> { title, subtitle, date, audience, html }
const { getJSON, cleanHost } = require("./_substack");

module.exports = async (req, res) => {
  const host = cleanHost(req.query && req.query.host);
  const slug = String((req.query && req.query.slug) || "");
  if (!host || !/^[\w-]+$/.test(slug)) return res.status(400).json({ error: "bad request" });
  try {
    const d = await getJSON(`https://${host}/api/v1/posts/${slug}`);
    res.setHeader("Cache-Control", "s-maxage=3600, stale-while-revalidate=86400");
    return res.status(200).json({
      title: d.title || "", subtitle: d.subtitle || "", date: (d.post_date || "").slice(0, 10),
      audience: d.audience || "everyone", html: d.body_html || "",
    });
  } catch (e) {
    return res.status(e.status === 404 ? 404 : 502).json({ error: "Couldn't load that post." });
  }
};
