# Periodicals, on the web

**Live:** https://aidanjude-periodicals.vercel.app

All 51 posts from aidanjude.substack.com (January 2023 to October 2026), plus three pieces he chose from randomaidan.substack.com, as a magazine you page through:
spreads on a desktop, one page at a time on a phone, a Contents menu, arrows, swipe, pinch to read.

- `build.py` writes `public/index.html` and `public/img/`. The words, pictures and credits come from
  `editions/complete/scripts/content.py`, the same parse the print edition uses, so web and print hold
  the same magazine. Face and colours are read from `editions/complete/scripts/build.py`.
- `reader.html` is the Credo reader (`~/Desktop/credo/scripts/reader.html`), copied verbatim. Every change
  to it is a checked string replacement in `build.py`.
- `qa.py` drives the built reader in Chromium at 390x844 and 1440x900: console errors, pages that overflow,
  pictures that fail, contents links, arrow and swipe turns. `python3 web/qa.py [url]`.

- `check.py` + `checks.js`: the typesetting rules over every page (heads kept with their text, no runts, no
  one-line widows/orphans, no overflow, no repeated picture, no blank page, no hole over a third of a page while a
  piece goes on, no list item stranded). `build.py` runs it and fails on any hit.
- `render_pages.py` + `pairs.py`: every page to PNG at 820 px for the page-by-page look.

Deploy: `cd web && npx vercel@latest deploy --prod` (CLI only: the project is not linked to git, because a git
deploy builds the repo root) (Vercel project `periodicals`, analytics on, noindex).
