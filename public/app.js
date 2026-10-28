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
  bindPick: "auto", binding: "staple", paper: "8", coverPaper: "2", spineOverride: null,
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
function layoutIssue(issue, T, mx, binding = "staple") {
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

  const starts = [];
  // --- essays. Each one starts at the top of a new page and is flowed on its own (flowPost), so
  // it can be tightened or rebalanced without touching its neighbours. Rules, from Aidan's read
  // of the first issue (2026-10-28): no essay starts mid-page; one that overflows one page by a
  // few lines is set slightly tighter to fit; a long one never ends on a stub (last page >= 1/4);
  // no paragraph leaves a single line at the foot or head of a page; a heading keeps 3 lines
  // under it; an image that doesn't fit lets the text run on and goes to the top of the next page.
  const AREA = BOT - TOP, MIN_LAST = 0.25;
  const lineCache = new Map();
  function setLines(runs, width, size, base, key) {
    const k = key + "|" + size.toFixed(3);
    let r = lineCache.get(k); if (!r) { r = lines(words(runs, size, base), width, size, wid(T.body, " ", size)); lineCache.set(k, r); }
    return r;
  }
  function itemsOf(post, pi, k, lk) {
    const S = T.size * k, L = T.lead * k * lk, sp = wid(T.body, " ", S), items = [];
    post.blocks.forEach((b, bi) => {
      const key = pi + ":" + bi;
      if (b.t === "p" || b.t === "q" || b.t === "li") {
        const x = X0 + (b.t === "q" ? 22 : b.t === "li" ? 18 : 0), w = MW - (b.t === "q" ? 44 : b.t === "li" ? 18 : 0);
        const ls = setLines(b.runs, w, S, b.t === "q" ? T.it : T.body, key);
        items.push({ t: "lines", gap: b.t === "li" && items.length && items[items.length - 1].li ? L * 0.15 : L * 0.5, L, li: b.t === "li",
          lines: ls.map((ln, i) => (ops, base) => {
            if (i === 0 && b.t === "li") ops.push({ op: "t", x: X0 + 4, y: base, s: san(b.mark, T.body) || "-", f: T.body, z: S, c: INK });
            emit(ops, ln, x, base, w, S, sp, { justify: true });
          }) });
      } else if (b.t === "pre") {
        const out = [];
        for (const raw of b.lines) {
          const lead = (raw.match(/^\s*/) || [""])[0].length;
          const ls = raw.trim() ? setLines([{ text: raw }], MW - 18, S, T.body, key + ":" + out.length) : [{ words: [], w: 0, last: true }];
          ls.forEach((ln, i) => out.push((ops, base) => emit(ops, ln, X0 + Math.min(lead, 12) * sp + (i ? 18 : 0), base, MW, S, sp)));
        }
        items.push({ t: "lines", gap: L * 0.5, L, lines: out });
      } else if (b.t === "h") {
        const hz = b.lv <= 2 ? S * 1.5 : b.lv === 3 ? S * 1.25 : S * 1.05, hf = b.lv <= 3 ? T.head : T.bd;
        const ls = lines(words(b.runs, hz, hf), MW, hz, wid(hf, " ", hz));
        items.push({ t: "head", gap: L * 1.1, h: ls.length * hz * 1.25 + L * 0.2,
          draw: (ops, y) => { for (const ln of ls) { y += hz * 1.25; emit(ops, ln, X0, y - hz * 0.3, MW, hz, wid(hf, " ", hz)); } } });
      } else if (b.t === "hr") {
        items.push({ t: "hr", gap: 0, h: L * 2, draw: (ops, y) => ops.push({ op: "l", x1: X0 + MW / 2 - 20, y1: y + L * 1.2, x2: X0 + MW / 2 + 20, y2: y + L * 1.2, w: 0.6, c: RULE }) });
      } else if (b.t === "img") {
        const im = state.imgs.get(b.src); if (!im || !im.ok) return;
        let w = Math.min(MW, Math.max(MW * 0.55, (im.w / 150) * 72)), h = (w * im.h) / im.w;
        const maxH = AREA * 0.66; if (h > maxH) { h = maxH; w = (h * im.w) / im.h; }
        const cz = T.size * 0.82, cl = cz * 1.4;
        const cls = b.cap ? lines(words([{ text: b.cap, i: true }], cz, T.body), w, cz, wid(T.it, " ", cz)) : [];
        items.push({ t: "img", gap: L * 0.8, h: h + 4 + cls.length * cl + L * 0.3,
          draw: (ops, y) => {
            ops.push({ op: "i", x: X0 + (MW - w) / 2, y, w, h, ref: b.src }); y += h + 4;
            for (const ln of cls) { y += cl; emit(ops, ln, X0 + (MW - w) / 2, y - cl * 0.3, w, cz, wid(T.it, " ", cz), { color: GREY }); }
          } });
      }
    });
    return { items, S, L, sp };
  }
  function headOf(post, ops) {
    const kick = [fmtDate(post.date), post.pub].filter(Boolean).join("  ·  ").toUpperCase();
    const tz = T.title, tl = tz * 1.12, S = T.size, L = T.lead, sp = wid(T.body, " ", S);
    const tLines = lines(words([{ text: post.title || "Untitled" }], tz, T.head), MW, tz, wid(T.head, " ", tz));
    const subz = S * 1.18, subl = L * 1.12;
    const sLines = post.subtitle ? lines(words([{ text: post.subtitle, i: true }], subz, T.body), MW, subz, wid(T.it, " ", subz)) : [];
    let y = TOP + 8; emit(ops, { words: [{ segs: [{ s: san(kick, T.body), f: T.body }], w: 0 }], last: true }, X0, y, MW, 7.6, 0, { color: GREY });
    y += 12;
    for (const ln of tLines) { y += tl; emit(ops, ln, X0, y - tl * 0.22, MW, tz, wid(T.head, " ", tz)); }
    y += 6;
    for (const ln of sLines) { y += subl; emit(ops, ln, X0, y - subl * 0.25, MW, subz, wid(T.it, " ", subz), { color: GREY }); }
    y += 10; ops.push({ op: "l", x1: X0, y1: y, x2: X0 + 36, y2: y, w: 1.2, c: INK }); y += 18;
    if (post.paid) {
      const r = lines(words([{ text: "Paid post: Substack only shares the free preview, so this prints the opening only.", i: true }], S * 0.9, T.body), MW, S * 0.9, sp);
      for (const ln of r) { y += L; emit(ops, ln, X0, y - L * 0.25, MW, S * 0.9, sp, { color: GREY }); }
      y += L * 0.5;
    }
    return y;
  }
  // flow one essay. k scales body size and leading, lk leading alone, cut shortens every page but
  // the last (used to rebalance a stub). Returns its pages and how full the last one is.
  function flowPost(post, pi, k = 1, lk = 1, cut = 0) {
    const { items } = itemsOf(post, pi, k, lk);
    const out = [], defer = []; let ops = null, y = TOP, stats = { splits: 0, widows: 0 };
    const bot = () => BOT - cut;
    const placeImg = (it) => { it.draw(ops, y); y += it.h; };
    const newPage = () => {
      ops = []; out.push(ops); y = TOP;
      while (defer.length && y + defer[0].h <= bot()) { placeImg(defer.shift()); y += defer.length ? defer[0].gap : 0; }
      if (y > TOP) y += T.lead * 0.3;
    };
    newPage(); y = headOf(post, ops);
    items.forEach((it, ii) => {
      const atTop = () => y <= TOP + 0.5;
      if (it.t === "lines") {
        const L = it.L; let i = 0; const n = it.lines.length;
        while (i < n) {
          const gap = atTop() ? 0 : (i === 0 ? it.gap : 0);
          const room = Math.floor((bot() - y - gap) / L + 1e-6), rem = n - i;
          let take = rem <= room ? rem : Math.min(room, rem - 2);   // leave at least 2 for the next page
          if (rem > room && take < 2) take = 0;                       // and never 1 alone at the foot
          if (take === 0) { if (atTop()) take = Math.min(rem, Math.max(1, room)); else { newPage(); continue; } }
          y += gap;
          for (let j = 0; j < take; j++) { y += L; it.lines[i + j](ops, y - L * 0.26); ops.push({ op: "mk", p: ii, i: i + j, n }); }
          i += take;
          if (i < n) { stats.splits++; newPage(); }
        }
      } else if (it.t === "head") {
        // keep the heading with the next 3 lines of text, however many items they span; a paragraph
        // of 4 lines or fewer can't split 3+, so it comes whole. An image after it comes with it.
        let keep = 0, need = 3, withImg = false;
        for (let j = ii + 1; j < items.length && need > 0; j++) {
          const nx = items[j];
          if (nx.t === "lines") { const n = nx.lines.length, take = n <= 4 ? n : Math.max(need, 2); keep += nx.gap + take * nx.L; need -= take; }
          else if (nx.t === "head") keep += nx.gap + nx.h;
          else if (nx.t === "img") { keep += nx.gap + nx.h; need = 0; withImg = true; }
          else keep += nx.h;
        }
        // an image already waiting for the next page holds back every image after it, so a
        // heading that needs one goes over too (and re-checks under whatever images land first)
        while (!atTop() && (y + it.gap + it.h + keep > bot() || (withImg && defer.length))) newPage();
        if (!atTop()) y += it.gap;
        it.draw(ops, y); y += it.h; ops.push({ op: "mk", p: ii, head: true, y });
      } else if (it.t === "hr") {
        if (atTop() || y + it.h + 3 * T.lead > bot()) return;   // a rule at a page break is just a page break
        it.draw(ops, y); y += it.h;
      } else if (it.t === "img") {
        const gap = atTop() ? 0 : it.gap;
        if (!defer.length && y + gap + it.h <= bot()) { y += gap; placeImg(it); }
        else defer.push(it);                                     // text runs on into the gap
      }
    });
    while (defer.length) newPage();
    return { pages: out, fill: (y - TOP) / AREA, k, lk, cut, stats };
  }
  function bestFlow(post, pi) {
    const base = flowPost(post, pi);
    const n = base.pages.length;
    if (n === 1 || base.fill >= MIN_LAST) return base;
    // tighten: set this essay up to 6% smaller to lose the stub page
    for (const k of [0.985, 0.97, 0.955, 0.94]) { const r = flowPost(post, pi, k); if (r.pages.length === n - 1) return r; }
    // loosen the leading a touch so more of it reaches the last page
    for (const lk of [1.02, 1.04]) { const r = flowPost(post, pi, 1, lk); if (r.pages.length === n && r.fill >= MIN_LAST) return r; }
    // rebalance: end the earlier pages a little short so the last page carries a quarter
    const step = T.lead;
    for (let cut = step; cut <= AREA * 0.3; cut += step) { const r = flowPost(post, pi, 1, 1, cut); if (r.pages.length === n && r.fill >= MIN_LAST) return { ...r, cutLast: true }; if (r.pages.length > n) break; }
    return base;
  }

  const flows = issue.posts.map((p, i) => bestFlow(p, i));
  state.flowStats = flows.map((f, i) => ({ title: issue.posts[i].title, pages: f.pages.length, fill: f.fill, k: f.k, lk: f.lk, cut: f.cut, splits: f.stats.splits }));

  // --- page count. Staple (self-cover): the whole file is a multiple of 4, at least 8. Perfect
  // (PUR): the cover is a separate file, so only the interior counts, a multiple of 4 and at
  // least 32 (Mixam product JSON 2026-10-28: boundMetadata.pagesIncrement 4, PUR min 16 on text
  // stock but 32 on the satin cover stocks). Padding is plain blank pages.
  const perfect = binding === "perfect";
  const fixed = 1 + toc.length + flows.reduce((a, f) => a + f.pages.length, 0) + 1;
  let pad = 0;
  if (perfect) { while ((fixed - 2 + pad) % 4 || fixed - 2 + pad < 32) pad++; }
  else { while ((fixed + pad) % 4 || fixed + pad < 8) pad++; }
  // left-hand page: staple counts the cover as page 1, perfect numbers from the first inside page
  const folioOf = (idx) => (perfect ? idx : idx + 1);
  const isLeft = (idx) => folioOf(idx) % 2 === 0;
  const blank = () => ({ kind: "blank", ops: [] });
  // Padding goes just before the back cover. Spending it to open a long essay on a left-hand
  // page put blank pages mid-issue (tried 2026-10-28: 3 blanks for 9 more spreads), which reads
  // as a printing fault, so essays open wherever the previous one ends.
  flows.forEach((f, i) => {
    starts.push({ title: issue.posts[i].title || "Untitled", date: issue.posts[i].date, n: folioOf(pages.length) });
    for (const ops of f.pages) pages.push({ kind: "body", ops, post: i });
  });
  while (pad-- > 0) pages.push(blank());
  const back = { kind: "back", ops: [] }; pages.push(back);

  // --- folios on contents and body pages; blank pages carry nothing
  pages.forEach((p, i) => {
    if (p.kind !== "body" && p.kind !== "contents") return;
    const n = folioOf(i), left = isLeft(i), fz = 7.8;
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
function drawOps(ctx, ops, k) {
  ctx.save(); ctx.beginPath(); ctx.rect(0, 0, W * k, H * k); ctx.clip();
  ctx.textBaseline = "alphabetic";
  for (const o of ops) {
    if (o.op === "t") { ctx.font = `${o.z * k}px "mz-${o.f}"`; ctx.fillStyle = css(o.c); ctx.fillText(o.s, o.x * k, o.y * k); }
    else if (o.op === "l") { ctx.strokeStyle = css(o.c); ctx.lineWidth = o.w * k; ctx.beginPath(); ctx.moveTo(o.x1 * k, o.y1 * k); ctx.lineTo(o.x2 * k, o.y2 * k); ctx.stroke(); }
    else if (o.op === "i") { const im = state.imgs.get(o.ref); if (im && im.bmp) ctx.drawImage(im.bmp, o.x * k, o.y * k, o.w * k, o.h * k); }
    else if (o.op === "fill") { ctx.fillStyle = css(o.c); ctx.fillRect(0, 0, W * k, H * k); }
    else if (o.op === "cover") {
      const c = state.cover; const s = Math.max(W / c.w, H / c.h), dw = c.w * s, dh = c.h * s;
      ctx.drawImage(c.bmp, ((W - dw) / 2) * k, ((H - dh) / 2) * k, dw * k, dh * k);
    }
  }
  ctx.restore();
}
function drawCanvas(cv, pg, cssW) {
  const dpr = Math.min(window.devicePixelRatio || 1, 2.5), k = (cssW / W) * dpr;
  cv.width = Math.round(W * k); cv.height = Math.round(H * k);
  cv.style.width = cssW + "px"; cv.style.height = (cssW * H) / W + "px";
  const ctx = cv.getContext("2d");
  ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, cv.width, cv.height);
  drawOps(ctx, pg.ops, k);
}
// the PUR cover spread at trim size: back | spine | front, fold lines dashed
function drawSpread(cv, cssW) {
  const sp = spinePt(), SW = 2 * W + sp;
  const dpr = Math.min(window.devicePixelRatio || 1, 2.5), k = (cssW / SW) * dpr;
  cv.width = Math.round(SW * k); cv.height = Math.round(H * k);
  cv.style.width = cssW + "px"; cv.style.height = (cssW * H) / SW + "px";
  const ctx = cv.getContext("2d");
  ctx.fillStyle = css(INK); ctx.fillRect(0, 0, cv.width, cv.height);
  const pg = state.pages, back = pg[pg.length - 1], front = pg[0];
  drawOps(ctx, back.ops, k);
  ctx.save(); ctx.translate((W + sp) * k, 0); drawOps(ctx, front.ops, k); ctx.restore();
  const st = spineText();
  if (st) { ctx.save(); ctx.translate((W + sp / 2) * k, (H / 2) * k); ctx.rotate(Math.PI / 2); ctx.font = `${st.z * k}px "mz-${st.f}"`; ctx.fillStyle = css(PAPER); ctx.textAlign = "center"; ctx.fillText(st.s, 0, st.z * 0.35 * k); ctx.restore(); }
  ctx.setLineDash([4 * dpr, 4 * dpr]); ctx.strokeStyle = "rgba(255,103,25,.9)"; ctx.lineWidth = dpr;
  for (const x of [W, W + sp]) { ctx.beginPath(); ctx.moveTo(x * k, 0); ctx.lineTo(x * k, H * k); ctx.stroke(); }
}

/* ---------- PUR spine ---------- */
// Mixam's paper calipers (inches per leaf) and PUR limits come from its own calculator data,
// GET https://mixam.com/api/products/1/100007?santaType=QUOTE (Magazines, read 2026-10-28):
// Satin 70/80/100lb Text = 0.0035/0.004/0.005; Satin 80/100/110/130lb Cover = .008/.01/.012/.016.
// Mixam publishes no spine formula; it says the spine is "calculated and displayed in your
// Shopping Cart". So the formula was fitted to its live quotes, POST https://mixam.com/api/offer
// from the /magazines calculator, 14 specs (16-400 pages, 3 text weights, 4 cover weights), and
// checked against the cart: 112pp, 80lb Text, 100lb Cover -> cart "Spine Width: 0.23 inch".
// The standard US plants quote floor(pages / 2 x caliper, to 0.01") + 0.01", whatever the cover
// weight (14 of 14). One plant (Express, and Best Value on 130lb Cover) quotes 0.03-0.10" wider,
// which is why the user can type the cart's figure in to override it.
const TEXT_PAPER = { 7: { label: "70lb Text", cal: 0.0035 }, 8: { label: "80lb Text", cal: 0.004 }, 9: { label: "100lb Text", cal: 0.005 } };
const COVER_PAPER = { 1: { label: "80lb Cover" }, 2: { label: "100lb Cover" }, 3: { label: "110lb Cover" }, 5: { label: "130lb Cover" } };
const interiorCount = () => (state.binding === "perfect" ? state.pages.length - 2 : state.pages.length);
const spineCalc = (pages, cal) => Math.floor(pages / 2 * cal * 100 + 1e-6) / 100 + 0.01;
const spineIn = () => (state.spineOverride > 0 ? state.spineOverride : spineCalc(interiorCount(), TEXT_PAPER[state.paper].cal));
const spinePt = () => spineIn() * 72;
// title on the spine only when it can be read: Mixam advises against text on very narrow spines
// and wants 0.08" clear of the folds (spine shifts up to 0.08" left/right) and 0.2" from top/bottom
function spineText() {
  const sp = spinePt(); if (sp < 18) return null;
  const T = TYPES.find((t) => t.id === state.type), mx = measure.get(T.id); if (!mx) return null;
  const s = mx.san(state.issue.name || "", T.head); if (!s) return null;
  let z = Math.min(11, (sp - 2 * 5.76) * 0.72);
  const room = H - 2 * 14.4 - 36; if (mx.wid(T.head, s, z) > room) z = room / mx.wid(T.head, s, 1);
  return { s, z, f: T.head, w: mx.wid(T.head, s, z) };
}

/* ---------- render: PDF ---------- */
// part: "all" (staple or FedEx, one file), "interior" (PUR inside pages), "cover" (PUR spread)
async function buildPdf(printer, part = "all") {
  const T = TYPES.find((t) => t.id === state.type);
  const doc = await PDFDocument.create(); doc.registerFontkit(fontkit);
  doc.setTitle(state.issue.name + (part === "cover" ? " (cover)" : part === "interior" ? " (inside pages)" : "")); doc.setAuthor(state.issue.author || ""); doc.setCreator("Substack to Magazine");
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
  // draw one page's ops with its trim origin at (ox, oy); full-page art and fills cover `region`
  const paint = async (p, ops, ox, oy, region) => {
    for (const o of ops) {
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
  };
  if (part === "cover") {
    // one spread, back | spine | front, 0.125" bleed all round (Mixam: "the front cover is
    // positioned on the right, the back cover on the left, and the spine in the center")
    const sp = spinePt(), PW = 2 * W + sp + 2 * BLEED, PH = H + 2 * BLEED;
    const p = doc.addPage([PW, PH]);
    p.setBleedBox(0, 0, PW, PH); p.setTrimBox(BLEED, BLEED, 2 * W + sp, H);
    p.drawRectangle({ x: 0, y: 0, width: PW, height: PH, color: rgb(...INK) });
    const pg = state.pages;
    await paint(p, pg[pg.length - 1].ops, BLEED, BLEED, [0, 0, BLEED + W, PH]);
    const fx = BLEED + W + sp;
    await paint(p, pg[0].ops, fx, BLEED, [fx, 0, W + BLEED, PH]);
    const st = spineText();
    if (st) {
      const cx = BLEED + W + sp / 2;
      p.drawText(st.s, { x: cx - st.z * 0.35, y: BLEED + H / 2 + st.w / 2, size: st.z, font: F[st.f], color: rgb(...PAPER), rotate: PDFLib.degrees(-90) });
    }
    return doc.save();
  }
  const mix = printer === "mixam", ox = mix ? BLEED : 0, oy = mix ? BLEED : 0;
  const PW = mix ? W + 2 * BLEED : W, PH = mix ? H + 2 * BLEED : H;
  // full-page art: to the bleed edge on Mixam, inside a white border on FedEx
  const region = mix ? [0, 0, PW, PH] : [FEDEX_INSET, FEDEX_INSET, W - 2 * FEDEX_INSET, H - 2 * FEDEX_INSET];
  const list = part === "interior" ? state.pages.slice(1, -1) : state.pages;
  for (const pg of list) {
    const p = doc.addPage([PW, PH]);
    if (mix) { p.setBleedBox(0, 0, PW, PH); p.setTrimBox(BLEED, BLEED, W, H); }
    await paint(p, pg.ops, ox, oy, region);
  }
  return doc.save();
}

/* ---------- viewer ---------- */
const wide = () => window.matchMedia("(min-width: 1000px)").matches;
function spreads() {
  const n = state.pages.length;
  if (!wide()) return state.pages.map((_, i) => [i]);
  // staple: the cover is page 1, so pages 2-3 face each other. Perfect: the first inside page is
  // a right-hand page facing the (unprinted) inside cover, so it stands alone and 2-3 pair up.
  const first = state.binding === "perfect" ? 2 : 1;
  const out = first === 2 ? [[0], [1]] : [[0]];
  for (let i = first; i < n - 1; i += 2) out.push(i + 1 < n - 1 ? [i, i + 1] : [i]);
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
  // staple while it fits in Mixam's 96, perfect (PUR) past that or when picked
  let pages = state.bindPick === "perfect" ? null : layoutIssue(state.issue, T, mx, "staple");
  state.stapleCount = pages ? pages.length : state.stapleCount;
  if (!pages || pages.length > 96) { pages = layoutIssue(state.issue, T, mx, "perfect"); state.binding = "perfect"; }
  else state.binding = "staple";
  state.pages = pages;
  // keep roughly the same place when the type changes
  const sp = spreads(); state.view = Math.max(0, sp.findIndex((s) => s.includes(Math.min(firstPage, state.pages.length - 1))));
  render();
  bindingUi();
}
function bindingUi() {
  const n = state.pages.length, perfect = state.binding === "perfect", inner = interiorCount();
  $("#pagesum").textContent = perfect
    ? `${inner} inside pages plus a separate wraparound cover (front, spine and back).`
    : `${n} pages, including the cover and back cover.`;
  document.querySelectorAll(".np").forEach((e) => (e.textContent = `${perfect ? inner : n} Pages`));
  document.querySelectorAll(".bd").forEach((b) => b.classList.toggle("on", b.dataset.bind === state.binding));
  const over = (state.stapleCount || 0) > 96;
  $("#bd-staple").disabled = over;
  $("#mixwarn").textContent = over && perfect ? `This issue is past the 96 pages Mixam can staple, so it is set up for Perfect (PUR) binding: a glued, square spine like a paperback.` : "";
  $("#m-staple").hidden = perfect; $("#m-perfect").hidden = !perfect;
  if (perfect) {
    const sIn = spineIn(), sp = spinePt();
    $("#spinev").textContent = sIn.toFixed(2) + "\u2033";
    $("#spinecalc").textContent = `${inner} pages \u00f7 2 \u00d7 ${TEXT_PAPER[state.paper].cal}\u2033 per sheet of ${TEXT_PAPER[state.paper].label}`;
    $("#spreaddim").textContent = `Cover file: ${((2 * W + sp + 2 * BLEED) / 72).toFixed(3)} \u00d7 ${((H + 2 * BLEED) / 72).toFixed(3)} in with bleed (trim ${((2 * W + sp) / 72).toFixed(3)} \u00d7 11 in).`;
    document.querySelectorAll(".pw").forEach((e) => (e.textContent = TEXT_PAPER[state.paper].label));
    document.querySelectorAll(".cw").forEach((e) => (e.textContent = COVER_PAPER[state.coverPaper].label));
    document.querySelectorAll(".sv").forEach((e) => (e.textContent = sIn.toFixed(2)));
    const cv = $("#spreadcv"); if (cv && state.pages.length) drawSpread(cv, Math.min((cv.parentElement.clientWidth || 364) - 24, 680));
  }
}

/* ---------- steps ---------- */
// One screen, top to bottom (Aidan, 2026-10-28: "all on one screen, so its clear to them what is
// next"). Steps 1-4 open in order as each is satisfied; 5-7 open together once the magazine
// exists. Done steps stay open and editable; upcoming ones show a title and one line.
const LABELS = ["Enter your username", "Select your posts", "Name it", "Generate the magazine", "Design your cover", "Choose a typography", "Download the PDF"];
const selKey = () => [...state.sel].sort().join("|");
function progress() {
  const made = state.pages.length > 0, stale = made && state.genKey !== selKey();
  const done = [state.posts.length > 0, state.sel.size > 0, !!$("#magname").value.trim(), made && !stale, !!state.cover, made && state.typePicked, false];
  let cur = done.findIndex((d, i) => !d && (i < 4 || made));
  if (cur > 3 && !made) cur = 3;
  if (cur < 0) cur = 6;
  for (let i = 0; i < 7; i++) {
    const el = $("#s" + (i + 1)), open = i <= Math.min(cur, 3) || (made && i >= 4);
    el.classList.toggle("up", !open); el.classList.toggle("cur", i === cur); el.classList.toggle("done", !!(open && done[i] && i !== cur));
  }
  const gen = $("#gen");
  gen.hidden = made && !stale; gen.textContent = stale ? "Update the magazine →" : "Generate the magazine →";
  $("#stale").hidden = !stale;
  document.querySelectorAll(".dl").forEach((b) => (b.disabled = stale));
  $("#prog").textContent = `Next: ${LABELS[cur]}`;
}
// the preview sits under step 4 on a phone, and stays beside the steps on a wide screen
function placeViewer() { $("#viewer").classList.toggle("none", !state.pages.length); $("#blank").hidden = state.pages.length > 0; $("#blankname").textContent = $("#magname").value.trim() || state.name || ""; const v = $("#viewer"), dst = wide() ? $("#slot-wide") : $("#slot-phone"); if (state.pages.length && v.parentElement !== dst) dst.appendChild(v); if (!state.pages.length) $("#slot-phone").appendChild(v); }
const reveal = (id) => { const el = $("#" + id); if (el && el.getBoundingClientRect().top > window.innerHeight * 0.7) el.scrollIntoView({ behavior: "smooth", block: "start" }); };

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
  Object.assign(state, { user: u, name: d.name, pubs: d.pubs, posts: [], sel: new Set(), loading: true, bodies: new Map(), budget: 0, pages: [], issue: null, genKey: null });
  placeViewer(); progress();
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
  if (state.user === u && state.posts.length) { progress(); return; }
  btn.disabled = true; btn.textContent = "Finding…";
  try {
    await loadArchive(u, () => { progress(); btn.disabled = false; btn.textContent = "Find posts"; });
  } catch (x) {
    if (!state.posts.length) { err.textContent = x.message; err.hidden = false; }
    else $("#est").textContent = x.message;
    progress();
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
  $("#gen").disabled = !sel.length;
  progress();
}
$("#filter").addEventListener("input", drawList);
$("#all").addEventListener("click", () => { state.posts.filter((p) => p.audience === "everyone").forEach((p) => state.sel.add(keyOf(p))); drawList(); });
$("#none").addEventListener("click", () => { state.sel.clear(); drawList(); });

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
    state.view = 0; state.genKey = selKey();
    await relayout();
    placeViewer(); render(); progress();
    (wide() ? $("#s5") : $("#viewer")).scrollIntoView({ behavior: "smooth", block: "start" });
    track("generated", { posts: sel.length, pages: state.pages.length });
    msg.textContent = "";
  } catch (e) { msg.textContent = "Something went wrong: " + e.message; }
  btn.disabled = false;
});
$("#magname").addEventListener("change", () => { if (state.issue) { state.issue.name = $("#magname").value.trim() || state.name; relayout(); } });
$("#magname").addEventListener("input", () => { progress(); placeViewer(); });

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
    state.view = 0; await relayout(); progress();
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
      state.typePicked = true; await relayout(); progress(); track("type", { type: T.id });
    });
    box.appendChild(b);
  }
}
TYPES.forEach((T) => { if (!faceLoaded.has(T.head)) new FontFace("mz-" + T.head, `url(fonts/${T.head}.ttf)`).load().then((f) => document.fonts.add(f)).catch(() => {}); });
drawTypes();
$("#prev").addEventListener("click", () => go(-1));
$("#next").addEventListener("click", () => go(1));
document.addEventListener("keydown", (e) => { if (!state.pages.length || /INPUT|SELECT|TEXTAREA/.test(document.activeElement.tagName)) return; if (e.key === "ArrowRight") go(1); if (e.key === "ArrowLeft") go(-1); });
let tx = null;
$("#spread").addEventListener("touchstart", (e) => (tx = e.touches[0].clientX), { passive: true });
$("#spread").addEventListener("touchend", (e) => { if (tx === null) return; const dx = e.changedTouches[0].clientX - tx; if (Math.abs(dx) > 40) go(dx < 0 ? 1 : -1); tx = null; });
let rz; window.addEventListener("resize", () => { clearTimeout(rz); rz = setTimeout(() => { if (state.pages.length) { placeViewer(); render(); bindingUi(); } }, 120); });

// 7. download
document.querySelectorAll(".tab").forEach((t) => t.addEventListener("click", () => {
  document.querySelectorAll(".tab").forEach((x) => x.classList.toggle("on", x === t));
  document.querySelectorAll(".panel").forEach((p) => p.classList.toggle("on", p.id === "p-" + t.dataset.tab));
}));
document.querySelectorAll(".dl").forEach((b) => b.addEventListener("click", async () => {
  const printer = b.dataset.printer, part = b.dataset.part || "all", label = b.textContent;
  b.disabled = true; b.textContent = "Building the PDF…";
  try {
    const bytes = await buildPdf(printer, part);
    const slug = (state.issue.name || "magazine").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "magazine";
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([bytes], { type: "application/pdf" }));
    a.download = `${slug}-${printer}${part === "all" ? "" : "-" + part}.pdf`; document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 60000);
    track("download", { printer, part, binding: state.binding, pages: state.pages.length });
  } catch (e) { alert("Couldn't build the PDF: " + e.message); }
  b.disabled = false; b.textContent = label;
}));

// binding + PUR paper choices
document.querySelectorAll(".bd").forEach((b) => b.addEventListener("click", async () => {
  if (b.disabled) return;
  state.bindPick = b.dataset.bind === "perfect" ? "perfect" : "auto"; state.spineOverride = null; $("#spineover").value = "";
  await relayout(); track("binding", { binding: state.binding });
}));
$("#paper").addEventListener("change", (e) => { state.paper = e.target.value; state.spineOverride = null; $("#spineover").value = ""; bindingUi(); });
$("#coverpaper").addEventListener("change", (e) => { state.coverPaper = e.target.value; bindingUi(); });
$("#spineover").addEventListener("input", (e) => { const v = parseFloat(e.target.value); state.spineOverride = v > 0 && v < 3 ? v : null; bindingUi(); });

// Open pre-loaded with an example: the default username is looked up straight away, so the picker
// is ready to click through. (A visitor can go back and type their own.)
progress(); placeViewer();
loadArchive($("#user").value.trim()).then(placeViewer).catch(() => {});
window.__mz = state; // for testing
