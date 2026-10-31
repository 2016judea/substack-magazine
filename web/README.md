# Periodicals, on the web

**Live:** https://aidanjude-periodicals.vercel.app

All 51 posts from aidanjude.substack.com (January 2023 to October 2026) as a magazine you page through:
spreads on a desktop, one page at a time on a phone, a Contents menu, arrows, swipe, pinch to read.

- `build.py` writes `public/index.html` and `public/img/`. The words, pictures and credits come from
  `editions/complete/scripts/content.py`, the same parse the print edition uses, so web and print hold
  the same magazine. Face and colours are read from `editions/complete/scripts/build.py`.
- `reader.html` is the Credo reader (`~/Desktop/credo/scripts/reader.html`), copied verbatim. Every change
  to it is a checked string replacement in `build.py`.
- `qa.py` drives the built reader in Chromium at 390x844 and 1440x900: console errors, pages that overflow,
  pictures that fail, contents links, arrow and swipe turns. `python3 web/qa.py [url]`.

Deploy: `cd web && npx vercel@latest deploy --prod` (Vercel project `periodicals`, analytics on, noindex).
