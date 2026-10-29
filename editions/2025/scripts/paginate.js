// Paginator for the 2025 issue. Everything is in CSS px at 96/in, trim coordinates (816 x 1056).
// Grid: 12 columns of 46 px, 12 px gutters, 66 px margins. Rail = cols 1-3, text = cols 5-12.
const TW = 816, TH = 1056, M = 66, COL = 46, GUT = 12;
const cx = (c) => M + (c - 1) * (COL + GUT);           // left edge of column c
const RAIL_X = cx(1), RAIL_W = 3 * COL + 2 * GUT;      // 162
const TX = cx(5), TXW = 8 * COL + 7 * GUT;             // 298, 452
const FULL_X = M, FULL_W = TW - 2 * M;                 // 684
const TOP = 72, BOTTOM = 984, L = 20;
const PPI = 200;                                       // never print an image below this if avoidable
const MONTHS = "JFMAMJJASOND";
const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;");
const ms = document.getElementById("measure");

function el(cls, html, w, style) {
  const d = document.createElement("div"); d.className = "it " + cls; d.innerHTML = html;
  if (w) d.style.width = w + "px"; if (style) d.setAttribute("style", (d.getAttribute("style") || "") + style);
  return d;
}
function measureEl(d) { ms.appendChild(d); const r = d.getBoundingClientRect(); return r.height; }
function clearMeasure() { ms.innerHTML = ""; }

// ---------- text blocks ----------
function textBlock(b) {   // -> {cls, html, w, x, lh, style}
  if (b.t === "p") {
    const cls = b.cls === "quote" ? "quote" : b.cls === "pull" ? "pull" : b.cls === "attr" ? "attr" : "body";
    let h = b.html;
    if (cls === "pull" || cls === "quote") h = h.replace(/^((?:<[bi]>)*)([“"‘])/, '$1<span style="margin-left:-.42em">$2</span>');
    return { cls, html: h, x: TX, w: TXW, lh: { quote: 24, pull: 30, attr: 16, body: 20 }[cls], nosplit: cls === "pull" };
  }
  if (b.t === "li") {
    const ind = 18 + b.depth * 20, cls = "li" + (b.cls === "quote" ? " quote" : "");
    const mk = `<span class="mk${b.mk === "–" ? "" : " ol"}">${b.mk}</span>`;
    return { cls, html: b.html, mk, x: TX, w: TXW, lh: 20, style: `--ind:${ind}px` };
  }
  if (b.t === "pre") {
    if (b.cls === "attr") return { cls: "attr", html: b.html, x: TX, w: TXW, lh: 16, nosplit: true };
    return { cls: "verse", html: (b.lead ? `<span class="lead">${" ".repeat(b.lead)}</span>` : "") + b.html, x: TX, w: TXW, lh: 24, nosplit: true };
  }
  if (b.t === "h4") return { cls: "h4", html: b.html, x: TX, w: TXW, lh: 20, nosplit: true };
}
function makeText(tb, html, extra) {
  const d = el(tb.cls + (extra ? " " + extra : ""), (tb.mk && !(extra || "").includes("cont") ? tb.mk : "") + html, tb.w, tb.style);
  return d;
}
function lines(tb, html, extra) { clearMeasure(); const h = measureEl(makeText(tb, html, extra)); return Math.round(h / tb.lh); }

// split tb's html after n lines: returns [htmlA, htmlB] or null
function splitText(tb, n) {
  clearMeasure();
  const d = makeText(tb, tb.html, "split"); ms.appendChild(d);
  const top = d.getBoundingClientRect().top;
  const walker = document.createTreeWalker(d, NodeFilter.SHOW_TEXT);
  const nodes = []; let total = 0;
  while (walker.nextNode()) {
    const nd = walker.currentNode;
    if (nd.parentElement.classList.contains("mk")) continue;
    nodes.push([nd, total]); total += nd.length;
  }
  const at = (k) => { for (let i = nodes.length - 1; i >= 0; i--) if (k >= nodes[i][1]) return [nodes[i][0], k - nodes[i][1]]; };
  const lineOf = (k) => {   // line index of char k (skipping whitespace forward)
    let j = k; const s = (q) => { const [nd, o] = at(q); return nd.data[o]; };
    while (j < total - 1 && /\s/.test(s(j))) j++;
    const [nd, o] = at(j); const r = document.createRange(); r.setStart(nd, o); r.setEnd(nd, Math.min(o + 1, nd.length));
    const rc = r.getClientRects(); if (!rc.length) return -1;
    return Math.floor((rc[0].top - top + 2) / tb.lh);
  };
  let lo = 0, hi = total - 1;           // first char on line >= n
  if (lineOf(hi) < n) return null;
  while (lo < hi) { const mid = (lo + hi) >> 1; if (lineOf(mid) >= n) hi = mid; else lo = mid + 1; }
  let k = lo; const [nd0, o0] = at(k);
  // back up to the start of the word (the break is at whitespace or after a dash)
  const ra = document.createRange(); ra.setStart(d, tb.mk ? 1 : 0); const [na, oa] = at(k); ra.setEnd(na, oa);
  const rb = document.createRange(); rb.setStart(na, oa); rb.setEnd(d, d.childNodes.length);
  const box = document.createElement("div");
  box.appendChild(ra.cloneContents()); const A = box.innerHTML.replace(/\s+$/, "");
  box.innerHTML = ""; box.appendChild(rb.cloneContents()); const B = box.innerHTML.replace(/^\s+/, "");
  return [A, B];
}

// ---------- images ----------
function imgBox(b, opts, lead) {
  const ar = b.ph / b.pw, maxW = (b.pw / PPI) * 96;     // widest it may print at 200 ppi
  let x, w, full = false;
  if (b.pw / b.ph >= 1.15 && maxW >= FULL_W - 1 && !(opts.narrow || []).includes(b.key)) { x = FULL_X; w = FULL_W; full = true; }
  else { x = TX; w = Math.min(TXW, maxW) * (lead ? 1 : opts.scale); }
  const cap = lead ? 640 : opts.capH;                   // portraits: cap the height, keep the ratio
  if (w * ar > cap) { w = cap / ar; full = false; x = TX; }
  if (full && opts.scale < 1 && !lead) { full = false; x = TX; w = TXW; }
  return { x, w: Math.round(w), h: Math.round(w * ar), full };
}
function creditEl(html, w) { return el("cr", html, w); }

// ---------- flow one piece ----------
function flowPiece(P, opts) {
  const pages = [];
  let pg = null;
  const newPage = (kind) => { pg = { kind: kind || "text", piece: P, items: [], y: TOP, empty: true, railBottom: TOP, last: null }; pages.push(pg); };
  const put = (item) => { pg.items.push(item); };

  // opener: number, date and the year-locator in the rail; title and subtitle; the lead image at the foot
  newPage("opener");
  const d = new Date(P.date + "T12:00:00Z");
  const dateTxt = d.toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
  put({ kind: "html", cls: "on", x: RAIL_X, y: TOP, w: RAIL_W, html: String(P.no).padStart(2, "0") });
  put({ kind: "html", cls: "od", x: RAIL_X, y: TOP + 24, w: RAIL_W, html: dateTxt });
  put({ kind: "loc", x: RAIL_X, y: TOP + 50, w: RAIL_W, date: P.date });
  clearMeasure();
  const th = measureEl(el("ot", esc(P.title), TXW));
  put({ kind: "html", cls: "ot", x: TX - 3, y: TOP - 13, w: TXW, html: esc(P.title) });
  let ty = TOP - 13 + th + 5;
  if (P.subtitle) { clearMeasure(); const sh = measureEl(el("os", esc(P.subtitle), 360)); put({ kind: "html", cls: "os", x: TX, y: ty, w: 360, html: esc(P.subtitle) }); ty += sh; }
  let bi = 0;
  if (P.blocks[0] && P.blocks[0].t === "img") {
    const b = P.blocks[0], bx = imgBox(b, opts, true);
    let ch = 0, cel = null;
    if (b.credit) { clearMeasure(); cel = b.credit; ch = measureEl(creditEl(b.credit, bx.full ? FULL_W : RAIL_W)); }
    const bottom = bx.full ? BOTTOM - (ch ? ch + 8 : 0) : BOTTOM;
    let h = bx.h, w = bx.w;
    const room = bottom - (ty + 48);
    if (h > room) { h = room; w = Math.round(h * b.pw / b.ph); }
    const x = bx.full && w < FULL_W ? TX : bx.x;
    put({ kind: "img", x, y: bottom - h, w, h, src: b.src, key: b.key, pw: b.pw, ph: b.ph, white: b.white });
    if (cel) {
      if (bx.full && w >= FULL_W) put({ kind: "html", cls: "cr", x: FULL_X, y: bottom + 8, w: FULL_W, html: cel });
      else put({ kind: "html", cls: "cr", x: RAIL_X, y: bottom - ch, w: RAIL_W, html: cel });
    }
    bi = 1;
  }

  // body
  newPage();
  const blocks = P.blocks.slice(bi);
  let prev = null;
  const gapBefore = (b, prevB) => {
    if (pg.empty || !prevB) return 0;
    const g = opts.gap;
    if (b.t === "img" || prevB.t === "img") return Math.round(20 * g);
    if (b.t === "hr" || prevB.t === "hr") return 14;
    if (b.t === "h4") return Math.round(20 * g);
    if (prevB.t === "h4") return 4;
    if (b.t === "li" && prevB.t === "li") return b.depth > 0 ? 3 : 6;
    const q = (x) => x.t === "p" && (x.cls === "quote" || x.cls === "pull") || (x.t === "pre" && x.cls === "verse") || (x.t === "li" && x.cls === "quote");
    if (b.cls === "attr") return 8;
    if (q(b) !== q(prevB)) return Math.round(20 * g);
    if (b.t === "pre" && prevB.t === "pre") return 0;
    return Math.round(10 * g);
  };
  // minimum height a block needs to start on this page (2 lines, or all of it)
  const needMin = (b, j) => {
    if (!b) return 0;
    if (j !== undefined && keepWithNext(b, blocks[j + 1])) { const tb = textBlock(b); return lines(tb, tb.html) * tb.lh + 10 + needMin(blocks[j + 1]); }
    if (b.t === "img") { const bx = imgBox(b, opts); return bx.h + (bx.full && b.credit ? 22 : 0); }
    if (b.t === "hr") return 2;
    const tb = textBlock(b); const n = lines(tb, tb.html);
    if (tb.nosplit || n <= 3) return n * tb.lh;
    return 2 * tb.lh;
  };
  const keepWithNext = (b, nxt) => {
    if (!(b.t === "p" && b.cls === "body") || !nxt) return false;
    const n = lines(textBlock(b), b.html);
    return (/:\s*(<\/[bi]>)*\s*$/.test(b.html) && n <= 2) || (n === 1 && nxt.t === "li");
  };

  for (let i = 0; i < blocks.length; i++) {
    const b = blocks[i], nx = blocks[i + 1];
    if (b.t === "h2") {
      const cls = b.cls === "date" ? "date" : "sec";
      clearMeasure(); const hh = measureEl(el(cls, b.html, RAIL_W));
      const nextFull = nx && nx.t === "img" && imgBox(nx, opts).full;
      const tryPlace = () => {
        let ry = pg.empty ? TOP : Math.max(pg.y + Math.round(30 * opts.gap), pg.railBottom + 16);
        const cy = ry + 13;
        const contentY = nextFull ? cy + hh + 10 : cy;
        let need = Math.max(nextFull ? 0 : hh, needMin(nx, i + 1));
        if (nx && nx.t === "p" && nx.cls === "body" && lines(textBlock(nx), nx.html) === 1 && blocks[i + 2] && blocks[i + 2].t !== "h2") need = Math.max(need, 20 + 10 + needMin(blocks[i + 2], i + 2));
        if (contentY + need > BOTTOM) return false;
        put({ kind: "rule", x: FULL_X, y: ry, w: FULL_W });
        put({ kind: "html", cls, x: RAIL_X, y: cy, w: RAIL_W, html: b.html });
        pg.railBottom = cy + hh; pg.y = contentY; pg.empty = true; pg.afterHead = true;
        return true;
      };
      if (!tryPlace()) { newPage(); tryPlace(); }
      prev = null; continue;
    }
    if (b.t === "hr") {
      const g = pg.empty ? 0 : 14;
      if (pg.y + g + 2 + 14 > BOTTOM) { newPage(); }
      else { pg.y += g; put({ kind: "rule", x: TX, y: pg.y, w: 46 }); pg.y += 1; pg.empty = false; }
      prev = b; continue;
    }
    if (b.t === "img") {
      const bx = imgBox(b, opts);
      let g = gapBefore(b, prev);
      let ch = 0;
      if (b.credit) { clearMeasure(); ch = measureEl(creditEl(b.credit, bx.full ? FULL_W : RAIL_W)); }
      const below = bx.full ? (b.credit ? ch + 8 : 0) : 0;
      if (pg.y + g + bx.h + below > BOTTOM) {
        const room = BOTTOM - pg.y - g - below;              // shrink up to 28% rather than leave the page short
        const colH = Math.round(TXW * b.ph / b.pw);
        if (!bx.full && room >= 0.72 * bx.h && room >= 240) { const k = room / bx.h; bx.w = Math.floor(bx.w * k); bx.h = Math.floor(bx.h * k); }
        else if (bx.full && colH <= BOTTOM - pg.y - g && colH >= 240) { bx.full = false; bx.x = TX; bx.w = TXW; bx.h = colH; }
        else { newPage(); g = 0; }
      }
      const y = pg.y + g;
      if (b.credit && !bx.full) { clearMeasure(); ch = measureEl(creditEl(b.credit, RAIL_W)); }
      put({ kind: "img", x: bx.x, y, w: bx.w, h: bx.h, src: b.src, key: b.key, pw: b.pw, ph: b.ph, white: b.white });
      let yy = y + bx.h;
      if (b.credit) {
        if (bx.full) { put({ kind: "html", cls: "cr", x: FULL_X, y: yy + 8, w: FULL_W, html: b.credit }); yy += ch + 8; }
        else {
          let cy = yy - ch;
          const side = TX + TXW - (bx.x + bx.w) - 14;         // a narrow image: the credit sits beside it
          if (side >= 120) { clearMeasure(); const ch2 = measureEl(creditEl(b.credit, Math.min(side, 162))); put({ kind: "html", cls: "cr", x: bx.x + bx.w + 14, y: yy - ch2, w: Math.min(side, 162), html: b.credit }); }
          else if (cy < pg.railBottom + 10) {         // rail is taken (a heading sits beside a short image)
            if (yy + 8 + ch <= BOTTOM) { put({ kind: "html", cls: "cr", x: bx.x, y: yy + 8, w: bx.w, html: b.credit }); yy += 8 + ch; }
            else put({ kind: "html", cls: "cr", x: RAIL_X, y: cy, w: RAIL_W, html: b.credit });
          } else { put({ kind: "html", cls: "cr", x: RAIL_X, y: cy, w: RAIL_W, html: b.credit }); pg.railBottom = Math.max(pg.railBottom, yy); }
        }
      }
      if (bx.full) pg.railBottom = Math.max(pg.railBottom, yy);
      pg.y = yy; pg.empty = false; prev = b; continue;
    }
    // text
    const tb = textBlock(b);
    let g = gapBefore(b, prev);
    let html = tb.html, cont = false;
    for (let guard = 0; guard < 20; guard++) {
      const n = lines(tb, html, cont ? "cont split" : "");
      const h = n * tb.lh;
      let need = h;
      if (keepWithNext(b, nx)) need += 10 + needMin(nx, i + 1);
      if (pg.y + g + need <= BOTTOM) {
        put({ kind: "text", tb, html, cont, x: tb.x, y: pg.y + g, w: tb.w });
        pg.y += g + h; pg.empty = false; break;
      }
      const room = Math.floor((BOTTOM - pg.y - g) / tb.lh);
      if (tb.nosplit || keepWithNext(b, nx) || n < 4 || room < 2) { newPage(); g = 0; continue; }
      let k = Math.min(room, n - 2);
      const parts = splitText(Object.assign({}, tb, { html, mk: cont ? null : tb.mk }), k);
      if (!parts) { newPage(); g = 0; continue; }
      put({ kind: "text", tb, html: parts[0], cont, split: true, x: tb.x, y: pg.y + g, w: tb.w });
      newPage(); g = 0; html = parts[1]; cont = true;
    }
    prev = b;
  }
  return pages;
}
function pageBottom(pg) {
  let m = TOP;
  for (const it of pg.items) { if (it.kind === "text") { const n = lines(it.tb, it.html, (it.cont ? "cont " : "") + (it.split || it.cont ? "split" : "")); m = Math.max(m, it.y + n * it.tb.lh); } else if (it.h) m = Math.max(m, it.y + it.h); else if (it.kind === "html") { clearMeasure(); m = Math.max(m, it.y + measureEl(el(it.cls, it.html, it.w))); } }
  return m;
}
function fill(pg) { return (pageBottom(pg) - TOP) / (BOTTOM - TOP); }

// try layouts until the last page is at least a quarter full; fewest pages wins, then nearest to 1:1
function layoutPiece(P) {
  const variants = [];
  for (const scale of [1, 0.92, 0.84, 0.76]) for (const gap of [1, 1.4, 1.9]) for (const capH of [560, 470, 400]) variants.push({ scale, gap, capH });
  let best = null;
  for (const v of variants) {
    const pages = flowPiece(P, v);
    const f = fill(pages[pages.length - 1]);
    const runt = pages.length > 2 && f < 0.25 || (pages.length === 2 && f < 0.12);
    const score = (runt ? 1000 : 0) + pages.length * 10 + (1 - v.scale) * 5 + (v.gap - 1) * 2 + (v.capH < 560 ? 1 : 0);
    if (!best || score < best.score) best = { pages, score, v, f };
  }
  console.log("piece", P.no, P.slug, "pages", best.pages.length, "last fill", best.f.toFixed(2), JSON.stringify(best.v));
  return best;
}

// ---------- render ----------
function locator(x, y, w, date, big) {
  const d = new Date(date + "T12:00:00Z"), y0 = Date.UTC(d.getUTCFullYear(), 0, 1), y1 = Date.UTC(d.getUTCFullYear() + 1, 0, 1);
  const px = (t) => ((t - y0) / (y1 - y0)) * w;
  let s = `<svg class="it loc" style="left:${x}px;top:${y}px;overflow:visible" width="${w}" height="22" viewBox="0 0 ${w} 22">`;
  s += `<line x1="0" y1="4.5" x2="${w}" y2="4.5" stroke="#111" stroke-width=".75"/>`;
  for (let m = 0; m <= 12; m++) { const t = Date.UTC(d.getUTCFullYear(), m, 1), xx = px(t).toFixed(2); s += `<line x1="${xx}" y1="1.5" x2="${xx}" y2="7.5" stroke="#111" stroke-width=".75"/>`; if (m < 12) s += `<text x="${(px(t) + px(Date.UTC(d.getUTCFullYear(), m + 1, 1))) / 2}" y="19" text-anchor="middle">${MONTHS[m]}</text>`; }
  const xd = px(d.getTime()); s += `<rect x="${(xd - 3).toFixed(2)}" y="1.5" width="6" height="6" fill="#111"/>`;
  return s + `</svg>`;
}
function renderItems(trim, items) {
  for (const it of items) {
    if (it.kind === "html") { const d = el(it.cls, it.html, it.w); d.style.left = it.x + "px"; d.style.top = it.y + "px"; trim.appendChild(d); }
    else if (it.kind === "text") { const d = makeText(it.tb, it.html, (it.cont ? "cont " : "") + (it.split || it.cont ? "split" : "")); d.style.left = it.x + "px"; d.style.top = it.y + "px"; d.dataset.split = it.split ? "1" : ""; d.dataset.cont = it.cont ? "1" : ""; trim.appendChild(d); }
    else if (it.kind === "img") { const im = document.createElement("img"); im.className = "it"; im.src = it.src; Object.assign(im.style, { left: it.x + "px", top: it.y + "px", width: it.w + "px", height: it.h + "px" }); im.dataset.key = it.key; if (it.white) im.classList.add("edge"); im.dataset.pw = it.pw; im.dataset.ph = it.ph; trim.appendChild(im); }
    else if (it.kind === "rule") { const d = el("rule", "", it.w); d.style.left = it.x + "px"; d.style.top = it.y + "px"; trim.appendChild(d); }
    else if (it.kind === "loc") trim.insertAdjacentHTML("beforeend", locator(it.x, it.y, it.w, it.date));
  }
}
function sheet(kind) { const s = document.createElement("section"); s.className = "sheet" + (kind === "cover" || kind === "back" ? " ground" : ""); s.dataset.kind = kind; const t = document.createElement("div"); t.className = "trim"; s.appendChild(t); return [s, t]; }
function folio(trim, n, title) {
  const recto = n % 2 === 1;
  const num = el("fo", String(n), 60, recto ? "text-align:right" : ""); num.style.left = (recto ? TW - M - 60 : M) + "px"; num.style.top = "1004px"; trim.appendChild(num);
  if (title) { const t = el("fo", esc(title), TXW - 70); t.style.left = TX + "px"; t.style.top = "1004px"; trim.appendChild(t); }
}

function build() {
  const book = document.getElementById("book");
  const laid = PIECES.map((P) => ({ P, ...layoutPiece(P) }));
  // page numbers: 1 cover, 2 contents, then the pieces
  let n = 3; for (const L_ of laid) { L_.start = n; n += L_.pages.length; }
  let total = n - 1 + 1;                                   // + back cover
  const pad = (4 - (total % 4)) % 4; total += pad;

  // cover: the tool's default, set in this issue's faces on this issue's ground
  { const [s, t] = sheet("cover"); s.dataset.page = 1; book.appendChild(s);
    clearMeasure(); const probe = el("mast cov", "Aidan Jude"); probe.style.fontSize = "100px"; probe.style.display = "inline-block"; ms.appendChild(probe); const pw = probe.getBoundingClientRect().width;
    const mz = Math.min(146.7, (840 - 128) / (pw / 100));
    const base = 64 * 4 / 3 + mz * 0.92;                   // tool: cy = 64 + mz*0.92 (pt, bleed origin)
    const m = el("mast cov", "Aidan Jude", 840, `text-align:center;font-size:${mz}px;line-height:${mz}px`); m.style.left = "-12px"; m.style.top = (base - mz * 0.80 - 12) + "px"; t.appendChild(m);
    const sy = base + mz * 0.3 + 20 * 4 / 3;
    const sub = el("csub cov", "Selected writing&nbsp;&nbsp;·&nbsp;&nbsp;2025", 840, "text-align:center"); sub.style.left = "-12px"; sub.style.top = (sy - 12 - 11) + "px"; t.appendChild(sub);
    const nm = el("cname cov", "Aidan Jude", 840, "text-align:center"); nm.style.left = "-12px"; nm.style.top = (1080 - 74 * 4 / 3 - 12 - 13) + "px"; t.appendChild(nm);
    const ct = el("ccount cov", `${PIECES.length} pieces`, 840, "text-align:center"); ct.style.left = "-12px"; ct.style.top = (1080 - 56 * 4 / 3 - 12 - 9) + "px"; t.appendChild(ct);
  }
  // contents
  { const [s, t] = sheet("contents"); s.dataset.page = 2; book.appendChild(s);
    const items = [];
    items.push({ kind: "html", cls: "ot", x: TX - 3, y: TOP - 13, w: TXW, html: "Contents" });
    // the year, with each piece where it fell
    const y0 = 196, w = FULL_W, yr = 2025, t0 = Date.UTC(yr, 0, 1), t1 = Date.UTC(yr + 1, 0, 1);
    const px = (d) => ((Date.parse(d + "T12:00:00Z") - t0) / (t1 - t0)) * w;
    let svg = `<svg class="it loc" style="left:${FULL_X}px;top:${y0}px;overflow:visible" width="${w}" height="60" viewBox="0 0 ${w} 60">`;
    svg += `<line x1="0" y1="30" x2="${w}" y2="30" stroke="#111" stroke-width=".75"/>`;
    for (let m = 0; m <= 12; m++) { const xx = (((Date.UTC(yr, m, 1) - t0) / (t1 - t0)) * w).toFixed(2); svg += `<line x1="${xx}" y1="26" x2="${xx}" y2="34" stroke="#111" stroke-width=".75"/>`; if (m < 12) svg += `<text x="${(+xx + w / 24).toFixed(2)}" y="48" text-anchor="middle">${MONTHS[m]}</text>`; }
    let lastX = -99, lift = 0;
    laid.forEach(({ P }) => { const x = px(P.date); lift = x - lastX < 22 ? (lift ? 0 : 1) : 0; lastX = x;
      svg += `<rect x="${(x - 3).toFixed(2)}" y="27" width="6" height="6" fill="#111"/>`;
      svg += `<text x="${x.toFixed(2)}" y="${lift ? 6 : 18}" text-anchor="middle" style="font-size:9px">${String(P.no).padStart(2, "0")}</text>`;
      if (lift) svg += `<line x1="${x.toFixed(2)}" y1="9" x2="${x.toFixed(2)}" y2="24" stroke="#111" stroke-width=".5"/>`; });
    svg += `</svg>`;
    t.insertAdjacentHTML("beforeend", svg);
    let y = 300; const rowH = 56;
    items.push({ kind: "rule", x: FULL_X, y: y - 14, w: FULL_W });
    laid.forEach(({ P, start }) => {
      const dt = (+P.date.slice(8)) + " " + ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"][+P.date.slice(5, 7) - 1];
      items.push({ kind: "html", cls: "ct-n", x: RAIL_X, y, w: 40, html: String(P.no).padStart(2, "0") });
      items.push({ kind: "html", cls: "ct-d", x: RAIL_X + 40, y: y + 3, w: 110, html: dt });
      items.push({ kind: "html", cls: "ct-t", x: TX, y, w: TXW - 60, html: esc(P.title) });
      items.push({ kind: "html", cls: "ct-s", x: TX, y: y + 26, w: TXW - 60, html: esc(P.subtitle) });
      items.push({ kind: "html", cls: "ct-n", x: TW - M - 50, y, w: 50, html: `<div style="text-align:right">${start}</div>` });
      y += rowH;
    });
    renderItems(t, items); folio(t, 2, "");
  }
  // pieces
  for (const L_ of laid) L_.pages.forEach((pg, k) => {
    const [s, t] = sheet(pg.kind); const no = L_.start + k; s.dataset.page = no; s.dataset.piece = L_.P.slug; book.appendChild(s);
    renderItems(t, pg.items); folio(t, no, pg.kind === "opener" ? "" : L_.P.title);
  });
  for (let i = 0; i < pad; i++) { const [s] = sheet("blank"); s.dataset.page = n + i; book.appendChild(s); }
  { const [s] = sheet("back"); s.dataset.page = total; book.appendChild(s); }
  clearMeasure();
  window.__layout = laid.map((L_) => ({ slug: L_.P.slug, start: L_.start, pages: L_.pages.length, fill: L_.f, v: L_.v }));
  window.__pages = total; window.__done = true;
}
document.fonts.load("14px IS").then(() => Promise.all(["400 14px IS", "600 14px IS", "italic 14px IS", "italic 19px ISerif", "19px ISerif", "11px Mono", "500 11px Mono", "italic 11px Mono"].map((f) => document.fonts.load(f)))).then(() => document.fonts.ready).then(build);
