/* Substack -> Magazine. One layout engine feeds both the on-screen preview (canvas) and the two
   print PDFs (pdf-lib), so what you page through is what prints. Units are PDF points, origin
   top-left of the trim, y = text baseline. */
"use strict";
const { PDFDocument, rgb, pushGraphicsState, popGraphicsState, rectangle, clip, endPath } = PDFLib;

const W = 612, H = 792;            // US Letter trim, 8.5 x 11 in
const BLEED = 9;                   // 0.125 in, Mixam's spec
const FEDEX_INSET = 18;            // FedEx prints with a margin, never full bleed
const M = { top: 78, bottom: 86, side: 100 };
const X0 = M.side, MW = W - 2 * M.side, TOP = M.top, BOT = H - M.bottom;
const INK = [0.114, 0.106, 0.094], PAPER = [0.957, 0.941, 0.906], GREY = [0.45, 0.43, 0.40], RULE = [0.82, 0.80, 0.76];

const TYPES = [
  { id: "garamond", label: "Garamond", note: "Old-style book face", head: "garamond-400", body: "garamond-400", it: "garamond-400i", bd: "garamond-700", size: 12, lead: 16.6, title: 30 },
  { id: "baskerville", label: "Baskerville", note: "Classic, upright", head: "baskerville-400", body: "baskerville-400", it: "baskerville-400i", bd: "baskerville-700", size: 10.4, lead: 15.6, title: 26 },
  { id: "editorial", label: "Editorial", note: "Playfair heads, Source Serif text", head: "playfair-700", body: "sourceserif-400", it: "sourceserif-400i", bd: "sourceserif-700", size: 10.6, lead: 15.6, title: 28 },
  { id: "typewriter", label: "Typewriter", note: "Courier Prime", head: "courier-700", body: "courier-400", it: "courier-400i", bd: "courier-700", size: 10.4, lead: 15.2, title: 24 },
  { id: "grotesk", label: "Grotesk", note: "Inter, modern sans", head: "inter-700", body: "inter-400", it: "inter-400i", bd: "inter-700", size: 9.8, lead: 15, title: 25 },
];

// Ligatures off: with them on, pdf-lib drew "ff"/"fi" glyphs ~6 pt wider than it measured, pushing
// justified lines past the column (found 2026-10-28 in a 1,367-post test issue), and the PDF text
// extracted as (cid:923). Plain glyphs measure and draw the same.
const FONT_OPTS = { subset: false, features: { liga: false, clig: false, dlig: false, rlig: false, calt: false } };
const $ = (s) => document.querySelector(s);
const state = {
  user: "", name: "", pubs: [], posts: [], sel: new Set(), type: "garamond",
  cover: null, bodies: new Map(), imgs: new Map(), pages: [], view: 0, issue: null,
};
const track = (name, data) => { try { window.va && window.va("event", { name, data }); } catch (e) {} };
const keyOf = (p) => p.host + "/" + p.slug;

/* ---------- fonts ---------- */
const fontBytes = new Map(), faceLoaded = new Set(), measure = new Map();
async function bytesOf(k) {
  if (!fontBytes.has(k)) fontBytes.set(k, fetch(`fonts/${k}.ttf`).then((r) => r.arrayBuffer()));
  return fontBytes.get(k);
}
const keysOf = (T) => [...new Set([T.head, T.body, T.it, T.bd])];
async function loadFaces(T) {
  await Promise.all(keysOf(T).map(async (k) => {
    if (faceLoaded.has(k)) return;
    const f = new FontFace("mz-" + k, await bytesOf(k));
    await f.load(); document.fonts.add(f); faceLoaded.add(k);
  }));
}
// A metrics provider: real pdf-lib fonts, so line breaks are computed from the same widths the
// PDF will use.
async function metrics(T) {
  if (measure.has(T.id)) return measure.get(T.id);
  const doc = await PDFDocument.create(); doc.registerFontkit(fontkit);
  const F = {}, CS = {};
  for (const k of keysOf(T)) {
    F[k] = await doc.embedFont(await bytesOf(k), FONT_OPTS);
    CS[k] = new Set(F[k].getCharacterSet());
  }
  const cache = new Map();
  const wid = (k, s, z) => {
    const c = k + "\u0001" + s; let w = cache.get(c);
    if (w === undefined) { w = F[k].widthOfTextAtSize(s, 1); cache.set(c, w); }
    return w * z;
  };
  const SUB = { "‘": "'", "’": "'", "“": '"', "”": '"', "—": "-", "–": "-", "…": "...", " ": " ", "→": "->", "•": "*" };
  const san = (s, k) => {
    let o = "";
    for (const ch of s) {
      const cp = ch.codePointAt(0);
      if (CS[k].has(cp)) o += ch;
      else if (SUB[ch]) o += [...SUB[ch]].every((c) => CS[k].has(c.codePointAt(0))) ? SUB[ch] : "";
    }
    return o;
  };
  const m = { F, wid, san };
  measure.set(T.id, m);
  return m;
}

/* ---------- Substack HTML -> blocks ---------- */
const SKIP = "svg,button,script,style,iframe,label.hide-text,.subscription-widget-wrap,.subscription-widget-wrap-editor,.subscribe-widget,.button-wrapper,.captioned-button-wrap,.image-link-expand,.embedded-post-wrap,.youtube-wrap,.tweet,.poll-embed,.digest-post-embed,.native-video-embed,.install-substack-app-embed,.comment-embed,.paywall-jump,.restack-image,.footnote-anchor";
function runsOf(node, st = { i: false, b: false }, out = []) {
  for (const c of node.childNodes) {
    if (c.nodeType === 3) { if (c.nodeValue) out.push({ text: c.nodeValue, i: st.i, b: st.b }); continue; }
    if (c.nodeType !== 1 || c.matches(SKIP)) continue;
    const tag = c.tagName.toLowerCase();
    if (tag === "br") { out.push({ br: true }); continue; }
    const ns = { i: st.i || tag === "em" || tag === "i", b: st.b || tag === "strong" || tag === "b" };
    runsOf(c, ns, out);
  }
  return out;
}
const hasText = (runs) => runs.some((r) => r.text && r.text.trim());
function imgOf(el) {
  const img = el.tagName === "IMG" ? el : el.querySelector("img");
  if (!img) return null;
  let src = img.getAttribute("src") || "", w = +img.getAttribute("width") || 0, h = +img.getAttribute("height") || 0;
  try { const a = JSON.parse(img.getAttribute("data-attrs") || "{}"); if (a.src) src = a.src; w = a.width || w; h = a.height || h; } catch (e) {}
  if (!/^https:\/\/(substack-post-media\.s3\.amazonaws\.com|substackcdn\.com|bucketeer-)/.test(src)) return null;
  const capEl = el.querySelector && el.querySelector("figcaption");
  return { t: "img", src, w, h, cap: capEl ? capEl.textContent.trim() : "" };
}
function blocksOf(html) {
  const doc = new DOMParser().parseFromString(`<div id="r">${html}</div>`, "text/html");
  const out = [];
  const walk = (el) => {
    for (const c of el.children) {
      if (c.matches(SKIP)) continue;
      const tag = c.tagName.toLowerCase();
      if (/^h[1-6]$/.test(tag)) { const r = runsOf(c); if (hasText(r)) out.push({ t: "h", lv: +tag[1], runs: r }); }
      else if (tag === "p") { const r = runsOf(c); if (hasText(r)) out.push({ t: "p", runs: r }); else { const im = imgOf(c); if (im) out.push(im); } }
      else if (tag === "blockquote") {
        const ps = c.querySelectorAll("p");
        if (ps.length) ps.forEach((p) => { const r = runsOf(p); if (hasText(r)) out.push({ t: "q", runs: r }); });
        else { const r = runsOf(c); if (hasText(r)) out.push({ t: "q", runs: r }); }
      }
      else if (tag === "pre") out.push({ t: "pre", lines: c.textContent.replace(/\n+$/, "").split("\n") });
      else if (tag === "ul" || tag === "ol") {
        let n = 0;
        for (const li of c.children) { if (li.tagName !== "LI") continue; n++; const r = runsOf(li); if (hasText(r)) out.push({ t: "li", runs: r, mark: tag === "ol" ? n + "." : "•" }); }
      }
      else if (tag === "hr") out.push({ t: "hr" });
      else if (tag === "figure" || tag === "picture" || tag === "img" || c.classList.contains("captioned-image-container")) { const im = imgOf(c); if (im) out.push(im); }
      else walk(c);
    }
  };
  walk(doc.getElementById("r"));
  return out;
}

/* ---------- layout ---------- */
function layoutIssue(issue, T, mx) {
  const { wid, san } = mx;
  const S = T.size, L = T.lead, pages = [];
  const sp = wid(T.body, " ", S);
  const fontOf = (r, base) => (r.b ? T.bd : r.i ? (base === T.it ? T.body : T.it) : base);

  function words(runs, size, base) {
    const out = []; let cur = null;
    for (const r of runs) {
      if (r.br) { if (cur) { out.push(cur); cur = null; } out.push({ br: true }); continue; }
      const f = fontOf(r, base);
      for (const part of r.text.replace(/ /g, " ").split(/(\s+)/)) {
        if (!part) continue;
        if (/^\s+$/.test(part)) { if (cur) { out.push(cur); cur = null; } continue; }
        const s = san(part, f); if (!s) continue;
        const w = wid(f, s, size);
        if (cur) { cur.segs.push({ s, f }); cur.w += w; } else cur = { segs: [{ s, f }], w };
      }
    }
    if (cur) out.push(cur);
    return out;
  }
  // a word wider than the measure (a URL) is cut into pieces that fit
  function splitLong(w, width, size) {
    if (w.w <= width) return [w];
    const parts = []; let cur = { segs: [], w: 0 };
    for (const sg of w.segs) for (const ch of sg.s) {
      const cw = wid(sg.f, ch, size);
      if (cur.w + cw > width && cur.w > 0) { parts.push(cur); cur = { segs: [], w: 0 }; }
      const last = cur.segs[cur.segs.length - 1];
      if (last && last.f === sg.f) last.s += ch; else cur.segs.push({ s: ch, f: sg.f });
      cur.w += cw;
    }
    if (cur.w) parts.push(cur);
    return parts;
  }
  function lines(ws, width, size, spc) {
    const out = []; let line = [], lw = 0;
    for (const w0 of ws) {
      if (w0.br) { out.push({ words: line, w: lw, last: true }); line = []; lw = 0; continue; }
      for (const w of splitLong(w0, width, size)) {
        const add = (line.length ? spc : 0) + w.w;
        if (line.length && lw + add > width) { out.push({ words: line, w: lw }); line = [w]; lw = w.w; }
        else { line.push(w); lw += add; }
      }
    }
    if (line.length) out.push({ words: line, w: lw, last: true });
    return out;
  }
  function emit(ops, ln, x, y, width, size, spc, opt = {}) {
    let g = spc, cx = x;
    const gaps = ln.words.length - 1, extra = width - ln.w;
    if (opt.justify && !ln.last && gaps > 0 && extra / gaps < spc * 2.4) g = spc + extra / gaps;
    if (opt.align === "center") cx = x + (width - ln.w) / 2;
    if (opt.align === "right") cx = x + (width - ln.w);
    for (const w of ln.words) {
      for (const sg of w.segs) { ops.push({ op: "t", x: cx, y, s: sg.s, f: sg.f, z: size, c: opt.color || INK }); cx += wid(sg.f, sg.s, size); }
      cx += g;
    }
  }

  // --- front cover
  const cover = { kind: "cover", ops: [] };
  pages.push(cover);
  // --- contents pages (count fixed up front so page numbers are known)
  const TOCL = 21, tocFirst = Math.floor((BOT - TOP - 64) / TOCL), tocNext = Math.floor((BOT - TOP) / TOCL);
  let nToc = 1; for (let left = issue.posts.length - tocFirst; left > 0; left -= tocNext) nToc++;
  const toc = []; for (let i = 0; i < nToc; i++) { const p = { kind: "contents", ops: [] }; pages.push(p); toc.push(p); }

  let page = null, y = 0;
  const newPage = () => { page = { kind: "body", ops: [] }; pages.push(page); y = TOP; };
  const fits = (h) => page && y + h <= BOT;
  const starts = [];

  for (const post of issue.posts) {
    // --- post head
    const kick = [fmtDate(post.date), post.pub].filter(Boolean).join("  ·  ").toUpperCase();
    const tz = T.title, tl = tz * 1.12;
    const tLines = lines(words([{ text: post.title || "Untitled" }], tz, T.head), MW, tz, wid(T.head, " ", tz));
    const subz = S * 1.18, subl = L * 1.12;
    const sLines = post.subtitle ? lines(words([{ text: post.subtitle, i: true }], subz, T.body), MW, subz, wid(T.it, " ", subz)) : [];
    const headH = 22 + tLines.length * tl + sLines.length * subl + 26;
    if (!page || y > TOP && (BOT - y < (BOT - TOP) * 0.38 || !fits(headH + 26 + 4 * L))) newPage();
    else if (y > TOP) { y += L * 1.6; page.ops.push({ op: "l", x1: X0 + MW / 2 - 30, y1: y, x2: X0 + MW / 2 + 30, y2: y, w: 0.6, c: RULE }); y += L * 1.8; }
    starts.push({ title: post.title || "Untitled", date: post.date, n: pages.length });
    y += 8; emit(page.ops, { words: [{ segs: [{ s: san(kick, T.body), f: T.body }], w: 0 }], last: true }, X0, y, MW, 7.6, 0, { color: GREY });
    y += 12;
    for (const ln of tLines) { y += tl; emit(page.ops, ln, X0, y - tl * 0.22, MW, tz, wid(T.head, " ", tz)); }
    y += 6;
    for (const ln of sLines) { y += subl; emit(page.ops, ln, X0, y - subl * 0.25, MW, subz, wid(T.it, " ", subz), { color: GREY }); }
    y += 10; page.ops.push({ op: "l", x1: X0, y1: y, x2: X0 + 36, y2: y, w: 1.2, c: INK }); y += 18;
    if (post.paid) {
      const r = lines(words([{ text: "Paid post: Substack only shares the free preview, so this prints the opening only.", i: true }], S * 0.9, T.body), MW, S * 0.9, sp);
      for (const ln of r) { if (!fits(L)) newPage(); y += L; emit(page.ops, ln, X0, y - L * 0.25, MW, S * 0.9, sp, { color: GREY }); }
      y += L * 0.5;
    }

    // --- body
    let prev = null;
    for (const b of post.blocks) {
      if (b.t === "p" || b.t === "q" || b.t === "li") {
        const x = X0 + (b.t === "q" ? 22 : b.t === "li" ? 18 : 0), w = MW - (b.t === "q" ? 44 : b.t === "li" ? 18 : 0);
        const base = b.t === "q" ? T.it : T.body;
        const ls = lines(words(b.runs, S, base), w, S, sp);
        if (prev) y += b.t === "li" && prev === "li" ? L * 0.15 : L * 0.5;
        ls.forEach((ln, i) => {
          if (!fits(L)) newPage();
          y += L;
          const by = y - L * 0.26;
          if (i === 0 && b.t === "li") page.ops.push({ op: "t", x: X0 + 4, y: by, s: san(b.mark, T.body) || "-", f: T.body, z: S, c: INK });
          emit(page.ops, ln, x, by, w, S, sp, { justify: true });
        });
      } else if (b.t === "h") {
        const hz = b.lv <= 2 ? S * 1.5 : b.lv === 3 ? S * 1.25 : S * 1.05, hf = b.lv <= 3 ? T.head : T.bd;
        const ls = lines(words(b.runs, hz, hf), MW, hz, wid(hf, " ", hz));
        if (!fits(L * 1.2 + ls.length * hz * 1.25 + L * 3)) newPage(); else y += L * 1.1;
        for (const ln of ls) { y += hz * 1.25; emit(page.ops, ln, X0, y - hz * 0.3, MW, hz, wid(hf, " ", hz)); }
        y += L * 0.2;
      } else if (b.t === "pre") {
        if (prev) y += L * 0.5;
        for (const raw of b.lines) {
          const lead = (raw.match(/^\s*/) || [""])[0].length;
          const ls = raw.trim() ? lines(words([{ text: raw }], S, T.body), MW - 18, S, sp) : [{ words: [], w: 0, last: true }];
          ls.forEach((ln, i) => { if (!fits(L)) newPage(); y += L; emit(page.ops, ln, X0 + Math.min(lead, 12) * sp + (i ? 18 : 0), y - L * 0.26, MW, S, sp); });
        }
      } else if (b.t === "hr") {
        if (!fits(L * 3)) { newPage(); continue; }
        y += L * 1.2; page.ops.push({ op: "l", x1: X0 + MW / 2 - 20, y1: y, x2: X0 + MW / 2 + 20, y2: y, w: 0.6, c: RULE }); y += L * 0.8;
      } else if (b.t === "img") {
        const im = state.imgs.get(b.src); if (!im || !im.ok) continue;
        const iw = im.w, ih = im.h;
        let w = Math.min(MW, Math.max(MW * 0.55, (iw / 150) * 72)), h = (w * ih) / iw;
        const maxH = (BOT - TOP) * 0.66; if (h > maxH) { h = maxH; w = (h * iw) / ih; }
        const cz = S * 0.82, cl = cz * 1.4;
        const cls = b.cap ? lines(words([{ text: b.cap, i: true }], cz, T.body), w, cz, wid(T.it, " ", cz)) : [];
        const need = (prev ? L * 0.8 : 0) + h + cls.length * cl + 6;
        if (!fits(need)) newPage(); else if (prev) y += L * 0.8;
        page.ops.push({ op: "i", x: X0 + (MW - w) / 2, y, w, h, ref: b.src });
        y += h + 4;
        for (const ln of cls) { y += cl; emit(page.ops, ln, X0 + (MW - w) / 2, y - cl * 0.3, w, cz, wid(T.it, " ", cz), { color: GREY }); }
        y += L * 0.3;
      }
      prev = b.t;
    }
  }
  if (!page) newPage();

  // --- pad to a multiple of 4 (saddle stitch) with ruled notes pages, minimum 8 (Mixam's floor)
  while ((pages.length + 1) % 4 !== 0 || pages.length + 1 < 8) {
    const p = { kind: "notes", ops: [] };
    p.ops.push({ op: "t", x: X0, y: TOP + 10, s: san("Notes", T.head), f: T.head, z: 16, c: GREY });
    for (let ly = TOP + 52; ly < BOT; ly += 26) p.ops.push({ op: "l", x1: X0, y1: ly, x2: X0 + MW, y2: ly, w: 0.4, c: RULE });
    pages.push(p);
  }
  const back = { kind: "back", ops: [] }; pages.push(back);

  // --- folios on inner pages: page 1 is the cover (a right-hand page), so even pages are left-hand
  pages.forEach((p, i) => {
    if (p.kind === "cover" || p.kind === "back") return;
    const n = i + 1, left = n % 2 === 0, fz = 7.8;
    const num = String(n), nm = san(issue.name, T.body).toUpperCase();
    const nw = wid(T.body, num, fz), mw = wid(T.body, nm, fz * 0.92);
    const fy = H - 46;
    if (left) { p.ops.push({ op: "t", x: X0, y: fy, s: num, f: T.body, z: fz, c: GREY }); p.ops.push({ op: "t", x: X0 + MW - mw, y: fy, s: nm, f: T.body, z: fz * 0.92, c: GREY }); }
    else { p.ops.push({ op: "t", x: X0, y: fy, s: nm, f: T.body, z: fz * 0.92, c: GREY }); p.ops.push({ op: "t", x: X0 + MW - nw, y: fy, s: num, f: T.body, z: fz, c: GREY }); }
  });

  // --- contents
  let ti = 0;
  toc.forEach((p, k) => {
    let cy = TOP;
    if (k === 0) { cy += 30; p.ops.push({ op: "t", x: X0, y: cy, s: san("Contents", T.head), f: T.head, z: 26, c: INK }); cy += 34; }
    const per = k === 0 ? tocFirst : tocNext;
    for (let j = 0; j < per && ti < starts.length; j++, ti++) {
      const st = starts[ti]; cy += TOCL;
      const num = String(st.n), z = S * 0.98, nwid = wid(T.body, num, z);
      let t = san(st.title, T.body); const room = MW - nwid - 70;
      while (t.length > 3 && wid(T.body, t, z) > room) t = t.slice(0, -2);
      if (t !== san(st.title, T.body)) t = t.replace(/\s*\S?$/, "") + "...";
      p.ops.push({ op: "t", x: X0, y: cy, s: t, f: T.body, z, c: INK });
      const d = san(fmtDate(st.date), T.body);
      p.ops.push({ op: "t", x: X0 + MW - nwid - 14 - wid(T.body, d, 7.4), y: cy, s: d, f: T.body, z: 7.4, c: GREY });
      p.ops.push({ op: "t", x: X0 + MW - nwid, y: cy, s: num, f: T.body, z, c: INK });
    }
  });

  // --- covers
  const cText = state.cover ? (state.cover.dark ? [1, 1, 1] : INK) : PAPER;
  cover.ops.push(state.cover ? { op: "cover", ref: "__cover" } : { op: "fill", c: INK });
  const nm = san(issue.name, T.head) || "Magazine";
  let mz = Math.min(110, (W - 96) / wid(T.head, nm, 1));
  let mLines = [{ words: [{ segs: [{ s: nm, f: T.head }], w: wid(T.head, nm, mz) }], w: wid(T.head, nm, mz), last: true }];
  if (mz < 54) { mz = 54; mLines = lines(words([{ text: nm }], mz, T.head), W - 96, mz, wid(T.head, " ", mz)).slice(0, 3); }
  let cy = 64;
  for (const ln of mLines) { cy += mz * 0.92; emit(cover.ops, ln, 48, cy, W - 96, mz, wid(T.head, " ", mz), { align: "center", color: cText }); }
  const yrs = issue.posts.map((p) => (p.date || "").slice(0, 4)).filter(Boolean).sort();
  const span = yrs.length ? (yrs[0] === yrs[yrs.length - 1] ? yrs[0] : yrs[0] + " – " + yrs[yrs.length - 1]) : "";
  const sub = san(`Selected writing  ·  ${span}`, T.body);
  cy += mz * 0.3 + 20; cover.ops.push({ op: "t", x: (W - wid(T.body, sub, 11)) / 2, y: cy, s: sub, f: T.body, z: 11, c: cText });
  const by = san(issue.author || "", T.body), cnt = san(`${issue.posts.length} ${issue.posts.length === 1 ? "piece" : "pieces"}`, T.body);
  if (by) cover.ops.push({ op: "t", x: (W - wid(T.body, by, 13)) / 2, y: H - 74, s: by, f: T.body, z: 13, c: cText });
  cover.ops.push({ op: "t", x: (W - wid(T.body, cnt, 9)) / 2, y: H - 56, s: cnt, f: T.body, z: 9, c: cText });

  back.ops.push({ op: "fill", c: INK });
  const bn = san(issue.name, T.head), bz = 20;
  back.ops.push({ op: "t", x: (W - wid(T.head, bn, bz)) / 2, y: H / 2 - 4, s: bn, f: T.head, z: bz, c: PAPER });
  const from = san("From " + issue.hosts.join(", "), T.body);
  back.ops.push({ op: "t", x: (W - wid(T.body, from, 8.5)) / 2, y: H / 2 + 18, s: from, f: T.body, z: 8.5, c: [0.75, 0.72, 0.67] });
  return pages;
}
function fmtDate(d) {
  if (!d) return "";
  const [y, m, day] = d.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, day)).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" });
}

/* ---------- render: canvas ---------- */
const css = (c) => `rgb(${c.map((v) => Math.round(v * 255)).join(",")})`;
function drawCanvas(cv, pg, cssW) {
  const dpr = Math.min(window.devicePixelRatio || 1, 2.5), k = (cssW / W) * dpr;
  cv.width = Math.round(W * k); cv.height = Math.round(H * k);
  cv.style.width = cssW + "px"; cv.style.height = (cssW * H) / W + "px";
  const ctx = cv.getContext("2d");
  ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, cv.width, cv.height);
  ctx.textBaseline = "alphabetic";
  for (const o of pg.ops) {
    if (o.op === "t") { ctx.font = `${o.z * k}px "mz-${o.f}"`; ctx.fillStyle = css(o.c); ctx.fillText(o.s, o.x * k, o.y * k); }
    else if (o.op === "l") { ctx.strokeStyle = css(o.c); ctx.lineWidth = o.w * k; ctx.beginPath(); ctx.moveTo(o.x1 * k, o.y1 * k); ctx.lineTo(o.x2 * k, o.y2 * k); ctx.stroke(); }
    else if (o.op === "i") { const im = state.imgs.get(o.ref); if (im && im.bmp) ctx.drawImage(im.bmp, o.x * k, o.y * k, o.w * k, o.h * k); }
    else if (o.op === "fill") { ctx.fillStyle = css(o.c); ctx.fillRect(0, 0, cv.width, cv.height); }
    else if (o.op === "cover") {
      const c = state.cover; const s = Math.max(W / c.w, H / c.h), dw = c.w * s, dh = c.h * s;
      ctx.drawImage(c.bmp, ((W - dw) / 2) * k, ((H - dh) / 2) * k, dw * k, dh * k);
    }
  }
}

/* ---------- render: PDF ---------- */
async function buildPdf(printer) {
  const T = TYPES.find((t) => t.id === state.type);
  const doc = await PDFDocument.create(); doc.registerFontkit(fontkit);
  doc.setTitle(state.issue.name); doc.setAuthor(state.issue.author || ""); doc.setCreator("Substack to Magazine");
  const F = {};
  for (const k of keysOf(T)) F[k] = await doc.embedFont(await bytesOf(k), FONT_OPTS);
  const E = new Map();
  const emb = async (ref) => {
    if (E.has(ref)) return E.get(ref);
    const im = ref === "__cover" ? state.cover : state.imgs.get(ref);
    let e = null;
    try { e = im.png ? await doc.embedPng(im.bytes) : await doc.embedJpg(im.bytes); } catch (err) { e = null; }
    E.set(ref, e); return e;
  };
  const mix = printer === "mixam", ox = mix ? BLEED : 0, oy = mix ? BLEED : 0;
  const PW = mix ? W + 2 * BLEED : W, PH = mix ? H + 2 * BLEED : H;
  // full-page art: to the bleed edge on Mixam, inside a white border on FedEx
  const region = mix ? [0, 0, PW, PH] : [FEDEX_INSET, FEDEX_INSET, W - 2 * FEDEX_INSET, H - 2 * FEDEX_INSET];
  for (const pg of state.pages) {
    const p = doc.addPage([PW, PH]);
    if (mix) { p.setBleedBox(0, 0, PW, PH); p.setTrimBox(BLEED, BLEED, W, H); }
    for (const o of pg.ops) {
      if (o.op === "t") p.drawText(o.s, { x: ox + o.x, y: oy + H - o.y, size: o.z, font: F[o.f], color: rgb(...o.c) });
      else if (o.op === "l") p.drawLine({ start: { x: ox + o.x1, y: oy + H - o.y1 }, end: { x: ox + o.x2, y: oy + H - o.y2 }, thickness: o.w, color: rgb(...o.c) });
      else if (o.op === "i") { const e = await emb(o.ref); if (e) p.drawImage(e, { x: ox + o.x, y: oy + H - o.y - o.h, width: o.w, height: o.h }); }
      else if (o.op === "fill") { const [rx, ry, rw, rh] = region; p.drawRectangle({ x: rx, y: ry, width: rw, height: rh, color: rgb(...o.c) }); }
      else if (o.op === "cover") {
        const e = await emb("__cover"); if (!e) continue;
        const [rx, ry, rw, rh] = region, c = state.cover, s = Math.max(rw / c.w, rh / c.h), dw = c.w * s, dh = c.h * s;
        p.pushOperators(pushGraphicsState(), rectangle(rx, ry, rw, rh), clip(), endPath());
        p.drawImage(e, { x: rx + (rw - dw) / 2, y: ry + (rh - dh) / 2, width: dw, height: dh });
        p.pushOperators(popGraphicsState());
      }
    }
  }
  return doc.save();
}

/* ---------- viewer ---------- */
const wide = () => window.matchMedia("(min-width: 900px)").matches;
function spreads() {
  const n = state.pages.length;
  if (!wide()) return state.pages.map((_, i) => [i]);
  const out = [[0]];
  for (let i = 1; i < n - 1; i += 2) out.push(i + 1 < n - 1 ? [i, i + 1] : [i]);
  out.push([n - 1]);
  return out;
}
function render() {
  if (!state.pages.length) return;
  const sp = spreads(); state.view = Math.max(0, Math.min(state.view, sp.length - 1));
  const cur = sp[state.view], box = $("#spread");
  box.innerHTML = "";
  const avail = box.clientWidth || 340, availH = window.innerHeight * (wide() ? 0.8 : 0.56);
  let pw = Math.min(wide() ? avail / 2 : avail, (availH * W) / H);
  pw = Math.floor(pw);
  for (const i of cur) { const cv = document.createElement("canvas"); cv.dataset.page = i + 1; drawCanvas(cv, state.pages[i], pw); box.appendChild(cv); }
  const label = cur.length === 2 ? `${cur[0] + 1}–${cur[1] + 1}` : `${cur[0] + 1}`;
  $("#pgno").textContent = `${label} / ${state.pages.length}`;
  $("#prev").disabled = state.view === 0; $("#next").disabled = state.view === sp.length - 1;
}
function go(d) { state.view += d; render(); }

async function relayout() {
  const T = TYPES.find((t) => t.id === state.type);
  await loadFaces(T);
  const mx = await metrics(T);
  const firstPage = (spreads()[state.view] || [0])[0];
  state.pages = layoutIssue(state.issue, T, mx);
  // keep roughly the same place when the type changes
  const sp = spreads(); state.view = Math.max(0, sp.findIndex((s) => s.includes(Math.min(firstPage, state.pages.length - 1))));
  render();
  const n = state.pages.length;
  $("#pagesum").textContent = `${n} pages, including the cover and back cover.`;
  document.querySelectorAll(".np").forEach((e) => (e.textContent = `${n} Pages`));
  $("#mixwarn").textContent = n > 96 ? `Mixam's staple binding takes up to 96 pages and this issue is ${n}. Go back and select fewer posts, or choose Perfect (PUR) binding on Mixam (that needs a separate cover file, which this tool doesn't make yet).` : "";
}

/* ---------- steps ---------- */
const STEPS = ["s1", "s2", "s3", "s4", "s5"];
function show(id) {
  STEPS.forEach((s) => $("#" + s).classList.toggle("on", s === id));
  // his flow numbers its steps 1-7; generating is step 4, design is 5 and 6 on one screen
  $("#prog").textContent = `Step ${["1", "2", "3", "5–6", "7"][STEPS.indexOf(id)]} of 7`;
  window.scrollTo(0, 0);
  if (id === "s4") requestAnimationFrame(render);
}
document.querySelectorAll(".back").forEach((b) => b.addEventListener("click", () => show(b.dataset.to)));

async function api(path) {
  const r = await fetch(path);
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || `Error ${r.status}`);
  return j;
}

// 1. find posts
// Resolve the writer, then page every publication's archive from the browser, one page per call,
// advancing by rows returned and stopping only on an empty page (see api/archive.js).
let run = 0;
async function loadArchive(u, onFirst) {
  const me = ++run;
  const d = await api("/api/archive?u=" + encodeURIComponent(u));
  if (me !== run) return;
  Object.assign(state, { user: u, name: d.name, pubs: d.pubs, posts: [], sel: new Set(), loading: true, bodies: new Map(), budget: 0 });
  $("#magname").value = d.name || ""; $("#filter").value = "";
  const seen = new Set(); let first = true;
  for (const pub of d.pubs) {
    let off = 0;
    for (let guard = 0; guard < 2000; guard++) {
      let pg = null;
      for (let a = 0; a < 7 && !pg; a++) {
        try { pg = await api(`/api/archive?host=${encodeURIComponent(pub.host)}&offset=${off}&pub=${encodeURIComponent(pub.name)}`); }
        catch (e) {
          if (a === 6) { state.loading = false; summary(); throw new Error(`Substack stopped answering after ${state.posts.length} posts. Try again in a minute to get the rest.`); }
          await new Promise((r) => setTimeout(r, 2000 * (a + 1)));
        }
      }
      if (me !== run) return;
      if (!pg.n) break;
      const fresh = pg.posts.filter((p) => !seen.has(keyOf(p)));
      if (!fresh.length) break;
      fresh.forEach((p) => seen.add(keyOf(p)));
      state.posts.push(...fresh.filter((p) => p.type === "newsletter"));
      off += pg.n;
      // default pick: every free post. It is their whole Substack; trimming to the newest few hid
      // the older work (2026-10-28). Past 96 pages the download step says so.
      for (const p of fresh) if (p.audience === "everyone" && p.type === "newsletter") state.sel.add(keyOf(p));
      if (first) { first = false; onFirst && onFirst(); }
      $("#selsum") && drawListSoon();
    }
  }
  state.loading = false;
  if (first) throw new Error(`No posts found for "${u}".`);
  drawList();
  track("found", { posts: state.posts.length });
}
let dls = 0;
function drawListSoon() { if (dls) return; dls = setTimeout(() => { dls = 0; drawList(); }, 250); }
$("#f1").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = $("#find"), err = $("#e1"), u = $("#user").value.trim(); err.hidden = true;
  if (!u) { err.textContent = "Enter a Substack username."; err.hidden = false; return; }
  if (state.user === u && state.posts.length) { show("s2"); $("#drop").open = true; return; }
  btn.disabled = true; btn.textContent = "Finding…";
  try {
    await loadArchive(u, () => { show("s2"); $("#drop").open = true; btn.disabled = false; btn.textContent = "Find posts"; });
  } catch (x) {
    if ($("#s1").classList.contains("on")) { err.textContent = x.message; err.hidden = false; }
    else $("#est").textContent = x.message;
  }
  btn.disabled = false; btn.textContent = "Find posts";
});

// 2. pick posts
function drawList() {
  const q = $("#filter").value.trim().toLowerCase(), list = $("#list");
  list.innerHTML = "";
  for (const pub of state.pubs) {
    const ps = state.posts.filter((p) => p.host === pub.host && (!q || p.title.toLowerCase().includes(q)));
    if (!ps.length) continue;
    const h = document.createElement("div"); h.className = "pub"; h.textContent = `${pub.name} · ${ps.length}`; list.appendChild(h);
    for (const p of ps) {
      const row = document.createElement("label"); row.className = "row";
      const paid = p.audience !== "everyone";
      row.innerHTML = `<input type="checkbox"><div><div class="t"></div><div class="m"></div></div>`;
      row.querySelector(".t").textContent = p.title || "Untitled";
      if (paid) row.querySelector(".t").insertAdjacentHTML("beforeend", ` <span class="tag" title="Substack only shares the free preview of paid posts">Paid · preview only</span>`);
      row.querySelector(".m").textContent = `${fmtDate(p.date)} · ${p.words ? p.words.toLocaleString() + " words" : "short"}`;
      const cb = row.querySelector("input"); cb.checked = state.sel.has(keyOf(p));
      cb.addEventListener("change", () => { cb.checked ? state.sel.add(keyOf(p)) : state.sel.delete(keyOf(p)); summary(); });
      list.appendChild(row);
    }
  }
  summary();
}
const estPages = (p) => 0.6 + (p.words || 0) / 420;
function summary() {
  const sel = state.posts.filter((p) => state.sel.has(keyOf(p)));
  const words = sel.reduce((a, p) => a + (p.words || 0), 0);
  $("#selsum").textContent = `${sel.length} of ${state.posts.length}${state.loading ? "+" : ""} posts selected`;
  const est = Math.max(8, Math.ceil((3 + sel.reduce((a, p) => a + estPages(p), 0)) / 4) * 4);
  $("#est").textContent = (state.loading ? `Still reading the archive: ${state.posts.length} posts so far. ` : "") + (sel.length ? `${words.toLocaleString()} words. You'll see the exact page count when it's laid out.` + (est > 96 ? " This many words is likely past the 96 pages Mixam can staple." : "") : "Pick at least one post.");
  $("#to3").disabled = !sel.length; $("#gen").disabled = !sel.length;
}
$("#filter").addEventListener("input", drawList);
$("#all").addEventListener("click", () => { state.posts.filter((p) => p.audience === "everyone").forEach((p) => state.sel.add(keyOf(p))); drawList(); });
$("#none").addEventListener("click", () => { state.sel.clear(); drawList(); });
$("#to3").addEventListener("click", () => { if (!$("#magname").value.trim()) $("#magname").value = state.name || ""; show("s3"); });

// 3. generate
async function pool(items, n, fn) {
  let i = 0; const run = async () => { while (i < items.length) { const k = i++; await fn(items[k], k); } };
  await Promise.all(Array.from({ length: Math.min(n, items.length) }, run));
}
async function loadImage(src) {
  if (state.imgs.has(src)) return;
  const rec = { ok: false }; state.imgs.set(src, rec);
  try {
    const r = await fetch("/api/img?u=" + encodeURIComponent(src)); if (!r.ok) return;
    const buf = await r.arrayBuffer(), ct = r.headers.get("content-type") || "";
    const u8 = new Uint8Array(buf);
    const isPng = u8[0] === 0x89 && u8[1] === 0x50, isJpg = u8[0] === 0xff && u8[1] === 0xd8;
    if (!isPng && !isJpg) return; void ct;
    rec.bmp = await createImageBitmap(new Blob([buf])); rec.w = rec.bmp.width; rec.h = rec.bmp.height;
    rec.bytes = buf; rec.png = isPng; rec.ok = true;
  } catch (e) {}
}
$("#gen").addEventListener("click", async () => {
  const btn = $("#gen"), msg = $("#genmsg");
  const sel = state.posts.filter((p) => state.sel.has(keyOf(p))).sort((a, b) => (a.date < b.date ? -1 : 1));
  if (!sel.length) return;
  btn.disabled = true; let done = 0;
  msg.textContent = `Fetching ${sel.length} posts…`;
  try {
    await pool(sel, 3, async (p) => {
      const k = keyOf(p);
      if (!state.bodies.has(k)) {
        try {
          let d = null;
          for (let a = 0; a < 4 && !d; a++) {
            try { d = await api(`/api/post?host=${encodeURIComponent(p.host)}&slug=${encodeURIComponent(p.slug)}`); }
            catch (e) { if (a === 3) throw e; await new Promise((r) => setTimeout(r, 1500 * (a + 1))); }
          }
          state.bodies.set(k, { ...d, blocks: blocksOf(d.html) });
        }
        catch (e) { state.bodies.set(k, { title: p.title, subtitle: p.subtitle, date: p.date, audience: p.audience, blocks: [{ t: "p", runs: [{ text: "(This post couldn't be loaded from Substack.)", i: true }] }] }); }
      }
      msg.textContent = `Fetched ${++done} of ${sel.length} posts…`;
    });
    const srcs = [...new Set(sel.flatMap((p) => state.bodies.get(keyOf(p)).blocks.filter((b) => b.t === "img").map((b) => b.src)))];
    let di = 0;
    if (srcs.length) msg.textContent = `Fetching ${srcs.length} images…`;
    await pool(srcs, 6, async (s) => { await loadImage(s); msg.textContent = `Fetched ${++di} of ${srcs.length} images…`; });
    msg.textContent = "Laying out pages…";
    state.issue = {
      name: $("#magname").value.trim() || state.name || "My Magazine", author: state.name || "",
      hosts: [...new Set(sel.map((p) => p.host))],
      posts: sel.map((p) => { const b = state.bodies.get(keyOf(p)); return { title: b.title || p.title, subtitle: b.subtitle || p.subtitle, date: p.date, pub: p.pub, paid: p.audience !== "everyone", blocks: b.blocks }; }),
    };
    state.view = 0;
    show("s4");
    await relayout();
    track("generated", { posts: sel.length, pages: state.pages.length });
    msg.textContent = "";
  } catch (e) { msg.textContent = "Something went wrong: " + e.message; }
  btn.disabled = false;
});
$("#magname").addEventListener("change", () => { if (state.issue) { state.issue.name = $("#magname").value.trim() || state.name; relayout(); } });

// 5. cover upload
$("#cover").addEventListener("change", async (e) => {
  const f = e.target.files && e.target.files[0]; if (!f) return;
  $("#covlab").textContent = "Reading image…";
  try {
    const bmp0 = await createImageBitmap(f);
    const max = 3400, s = Math.min(1, max / Math.max(bmp0.width, bmp0.height));
    const cv = document.createElement("canvas"); cv.width = Math.round(bmp0.width * s); cv.height = Math.round(bmp0.height * s);
    const ctx = cv.getContext("2d"); ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, cv.width, cv.height); ctx.drawImage(bmp0, 0, 0, cv.width, cv.height);
    // is the top of the art dark? decides the masthead colour
    const sm = document.createElement("canvas"); sm.width = 40; sm.height = 16;
    sm.getContext("2d").drawImage(cv, 0, 0, cv.width, cv.height * 0.32, 0, 0, 40, 16);
    const px = sm.getContext("2d").getImageData(0, 0, 40, 16).data; let lum = 0;
    for (let i = 0; i < px.length; i += 4) lum += 0.2126 * px[i] + 0.7152 * px[i + 1] + 0.0722 * px[i + 2];
    lum /= px.length / 4;
    const blob = await new Promise((r) => cv.toBlob(r, "image/jpeg", 0.92));
    const bytes = await blob.arrayBuffer();
    state.cover = { bytes, png: false, bmp: await createImageBitmap(blob), w: cv.width, h: cv.height, dark: lum < 150 };
    const ppi = Math.round(Math.min(cv.width / ((W + 2 * BLEED) / 72), cv.height / ((H + 2 * BLEED) / 72)));
    $("#covlab").textContent = `${f.name} ✓  (${ppi} ppi at print size${ppi < 200 ? ", may print soft" : ""}). Tap to change.`;
    state.view = 0; await relayout();
    track("cover", { ppi });
  } catch (x) { $("#covlab").textContent = "Couldn't read that image. Try a JPEG or PNG."; }
});

// 6. typography
function drawTypes() {
  const box = $("#types"); box.innerHTML = "";
  for (const T of TYPES) {
    const b = document.createElement("button"); b.type = "button"; b.className = "ty" + (T.id === state.type ? " on" : ""); b.dataset.type = T.id;
    b.innerHTML = `<b style="font-family:'mz-${T.head}',serif">${T.label}</b><small>${T.note}</small>`;
    b.addEventListener("click", async () => {
      state.type = T.id; document.querySelectorAll(".ty").forEach((x) => x.classList.toggle("on", x === b));
      await relayout(); track("type", { type: T.id });
    });
    box.appendChild(b);
  }
}
TYPES.forEach((T) => { if (!faceLoaded.has(T.head)) new FontFace("mz-" + T.head, `url(fonts/${T.head}.ttf)`).load().then((f) => document.fonts.add(f)).catch(() => {}); });
drawTypes();
$("#prev").addEventListener("click", () => go(-1));
$("#next").addEventListener("click", () => go(1));
document.addEventListener("keydown", (e) => { if (!$("#s4").classList.contains("on")) return; if (e.key === "ArrowRight") go(1); if (e.key === "ArrowLeft") go(-1); });
let tx = null;
$("#spread").addEventListener("touchstart", (e) => (tx = e.touches[0].clientX), { passive: true });
$("#spread").addEventListener("touchend", (e) => { if (tx === null) return; const dx = e.changedTouches[0].clientX - tx; if (Math.abs(dx) > 40) go(dx < 0 ? 1 : -1); tx = null; });
let rz; window.addEventListener("resize", () => { clearTimeout(rz); rz = setTimeout(() => { if (state.pages.length && $("#s4").classList.contains("on")) render(); }, 120); });
$("#to5").addEventListener("click", () => show("s5"));

// 7. download
document.querySelectorAll(".tab").forEach((t) => t.addEventListener("click", () => {
  document.querySelectorAll(".tab").forEach((x) => x.classList.toggle("on", x === t));
  document.querySelectorAll(".panel").forEach((p) => p.classList.toggle("on", p.id === "p-" + t.dataset.tab));
}));
document.querySelectorAll(".dl").forEach((b) => b.addEventListener("click", async () => {
  const printer = b.dataset.printer, label = b.textContent;
  b.disabled = true; b.textContent = "Building the PDF…";
  try {
    const bytes = await buildPdf(printer);
    const slug = (state.issue.name || "magazine").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "magazine";
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([bytes], { type: "application/pdf" }));
    a.download = `${slug}-${printer}.pdf`; document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 60000);
    track("download", { printer, pages: state.pages.length });
  } catch (e) { alert("Couldn't build the PDF: " + e.message); }
  b.disabled = false; b.textContent = label;
}));

// Open pre-loaded with an example: the default username is looked up straight away, so the picker
// is ready to click through. (A visitor can go back and type their own.)
loadArchive($("#user").value.trim()).catch(() => {});
window.__mz = state; // for testing
