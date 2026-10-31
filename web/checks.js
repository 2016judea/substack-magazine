// Credo's typesetting rules (aetas-nova-issue rules 9-10), checked over every page of the built reader.
// Returns {name: [[page, detail], ...]}; an empty list everywhere is a pass.
() => {
  const LINE = 22.11 * 1.5, pages = [...document.querySelectorAll('.page')];
  const R = {heading_split: [], runt: [], widow_orphan: [], overflow: [], repeat_img: [], blank: [], hole: [], ctrl: [], list_orphan: [], img_after_colon_moved: []};
  const pieceOf = p => (p.dataset.piece || '').split(' ').filter(Boolean);
  const lastPageOf = {}; pages.forEach((p, i) => pieceOf(p).forEach(s => lastPageOf[s] = i));
  const seen = {};
  pages.forEach((p, i) => {
    const n = i + 1, tx = p.querySelector('.tx'), ps = pieceOf(p);
    p.querySelectorAll('img').forEach(im => { const s = im.getAttribute('src'); if (seen[s]) R.repeat_img.push([n, s + ' also p.' + seen[s]]); else seen[s] = n });
    if (p.classList.contains('blank') || (!tx && !p.classList.contains('ink')) || (tx && !tx.children.length)) R.blank.push([n, p.className]);
    if (/[\u0001-\u0005]/.test(p.textContent)) R.ctrl.push([n, (p.textContent.match(/.{0,20}[\u0001-\u0005].{0,20}/)||[''])[0]]);
    if (!tx) return;
    if (tx.scrollHeight > tx.clientHeight + 1) R.overflow.push([n, tx.scrollHeight - tx.clientHeight]);
    if (p.classList.contains('contents')) return;
    const kids = [...tx.children], bottom = tx.clientHeight;
    const last = kids[kids.length - 1], used = last ? last.offsetTop + last.offsetHeight : 0;
    const slug = ps[ps.length - 1], continues = slug && lastPageOf[slug] > i;
    // (a) a heading with under ~2 lines of its body below it on the page, its piece going on overleaf
    kids.forEach((k, j) => {
      const isHead = k.matches('h3,h4,h5.dept') || k.matches('h2') || k.classList.contains('start') || k.classList.contains('eyebrow');
      if (!isHead) return;
      const rest = kids.slice(j + 1).filter(x => !x.matches('h2,h3,h4,h5.dept'));
      const after = rest.reduce((a, x) => a + x.offsetHeight, 0);
      if (after < 1.8 * LINE && continues && j >= kids.length - 3) R.heading_split.push([n, (k.textContent || '').slice(0, 40) + ' · ' + Math.round(after) + 'px under']);
    });
    // (b) a runt: a piece's tail under 4 lines alone at the top of a page that is not its first
    ps.forEach(s => {
      if (lastPageOf[s] !== i) return;
      const first = pages.findIndex(q => pieceOf(q).includes(s));
      if (first === i) return;
      const own = kids.filter(k => !k.classList.contains('start') && k.offsetTop < (kids.find(x => x.classList.contains('start'))?.offsetTop ?? 1e9));
      const h = own.length ? own[own.length - 1].offsetTop + own[own.length - 1].offsetHeight : 0;
      if (pieceOf(p)[0] === s && h < 4 * LINE + 2 && !own.some(k => k.querySelector('img'))) R.runt.push([n, s + ' ' + Math.round(h / LINE) + ' lines']);
    });
    // (c) a split paragraph leaving one line on either side
    kids.forEach(k => { if (k.tagName === 'P' && k.dataset.split && Math.round(k.offsetHeight / LINE) < 2) R.widow_orphan.push([n, k.dataset.split + ' ' + k.textContent.slice(0, 30)]) });
    // a list leaving one single-line item alone at the foot of the page, the list going on overleaf
    if (last && /^(UL|OL)$/.test(last.tagName) && last.children.length === 1 && last.offsetHeight < 1.5 * LINE && continues && !(last.previousElementSibling && /^(UL|OL)$/.test(last.previousElementSibling.tagName))) {
      const nx = pages[i + 1] && pages[i + 1].querySelector('.tx'); const f0 = nx && nx.firstElementChild;
      if (f0 && /^(UL|OL)$/.test(f0.tagName)) R.list_orphan.push([n, last.textContent.slice(0, 30)]);
    }
    // loose white space: a page left over a third empty while its piece goes on overleaf
    if (continues && bottom - used > bottom / 3) R.hole.push([n, Math.round((bottom - used) / bottom * 100) + '% empty']);
  });
  // a picture his line introduces (the line ends in a colon) must follow that line directly
  const flow = []; pages.forEach((p, i) => p.querySelectorAll('.tx > p, .tx > figure img').forEach(e => flow.push([i + 1, e])));
  const plain = v => (v || '').replace(/[\u0001-\u0004]/g, '').replace(/\u0005/g, ' ').replace(/\s+/g, ' ').trim();
  (window.ISSUE || []).forEach(f => f.blocks.forEach((b, k) => {
    if (b.t !== 'img') return; const prev = f.blocks[k - 1]; if (!prev || !/[:：]\s*$/.test(prev.v || '')) return;
    const at = flow.findIndex(([, e]) => e.tagName === 'IMG' && e.getAttribute('src') === b.src); if (at < 1) return;
    const before = flow[at - 1][1]; const tail = plain(prev.v).slice(-25);
    if (before.tagName !== 'P' || !plain(before.textContent).endsWith(tail) || flow[at - 1][0] !== flow[at][0]) R.img_after_colon_moved.push([flow[at][0], b.src]);
  }));
  return R;
}
