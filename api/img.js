// GET /api/img?u=<original image url>  -> a JPEG, resized for print by Substack's own CDN.
// pdf-lib embeds only JPEG and PNG, and Substack serves WebP/AVIF to browsers, so ask the CDN for
// f_jpg explicitly. Only Substack's image hosts are allowed.
const { UA } = require("./_substack");
const OK = /^https:\/\/(substack-post-media\.s3\.amazonaws\.com|substackcdn\.com|bucketeer-[\w-]+\.s3\.amazonaws\.com)\//;

module.exports = async (req, res) => {
  const u = String((req.query && req.query.u) || "");
  if (!OK.test(u)) return res.status(400).send("bad url");
  const src = u.startsWith("https://substackcdn.com/") ? u
    : `https://substackcdn.com/image/fetch/w_1600,c_limit,f_jpg,q_auto:good/${encodeURIComponent(u)}`;
  try {
    const r = await fetch(src, { headers: { "User-Agent": UA, Accept: "image/jpeg" } });
    if (!r.ok) return res.status(r.status).send("upstream " + r.status);
    const buf = Buffer.from(await r.arrayBuffer());
    res.setHeader("Content-Type", r.headers.get("content-type") || "image/jpeg");
    res.setHeader("Cache-Control", "public, s-maxage=86400, max-age=86400");
    return res.status(200).send(buf);
  } catch (e) {
    return res.status(502).send("fetch failed");
  }
};
