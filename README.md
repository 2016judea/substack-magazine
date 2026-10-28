# Substack to Magazine

**Live:** https://substack-magazine.vercel.app

Turn your Substack into a physical magazine. Enter your Substack username, pick the posts you want,
name the magazine, and it lays them out as a printed issue you can page through. Upload your own
cover art, try five typefaces, then download print-ready PDFs with step-by-step ordering
instructions for Mixam (stapled up to 96 pages, perfect bound past that) or FedEx Office (letter
pages, same-day pickup).

## How it works

- `api/archive.js` resolves a Substack handle to its publications (`substack.com/api/v1/user/<handle>/public_profile`)
  and returns one page of a publication's archive per call. The browser pages through it, advancing by
  rows returned and stopping only on an empty page: Substack caps a page at about 24 rows whatever
  `limit` asks for, so a short page is not the last one. Custom domains (`www.example.com`) work too.
- `api/post.js` returns a post's `body_html`. Paid posts come back truncated, so they are marked in the
  picker and print with a note.
- `api/img.js` fetches post images through Substack's CDN as JPEG (pdf-lib only embeds JPEG and PNG).
- `public/app.js` is the whole layout engine. One set of page operations drives both the on-screen
  preview (canvas) and the PDFs (pdf-lib, fonts embedded), so the preview is what prints.

## The print files

| | Mixam, staple | Mixam, Perfect (PUR) | FedEx Office |
|---|---|---|---|
| Files | One PDF, cover is page 1 | Inside pages PDF + one cover spread PDF (back, spine, front) | One PDF |
| Page | 8.5 × 11 in trim + 0.125 in bleed (630 × 810 pt), TrimBox and BleedBox set | Same, inside pages | 8.5 × 11 in, no bleed |
| Pages | Multiple of 4, 8 to 96 | Inside pages a multiple of 4, at least 32 | Same pages as staple |
| Cover | Art runs to the bleed edge | Spread is 17 in + spine + 0.25 in bleed wide; art fills the front panel to the bleed | Art inside a 0.25 in border |

The spine is computed from Mixam's own paper calipers (read from its calculator's product data)
with the rule its standard US plants quote: `floor(pages / 2 × caliper, to 0.01 in) + 0.01 in`.
Checked against 14 live quotes and the cart on 2026-10-28; the source and the exceptions are in
the comment above `spineCalc` in `public/app.js`. If Mixam's cart shows a different spine width,
the user types it in and downloads the cover again.

## Layout rules

Every essay starts at the top of a page. One that overflows by a few lines is set up to 6%
tighter to fit; a long one never ends on a page under a quarter full (tighten, loosen the
leading, or end earlier pages a little short). No paragraph leaves one line alone at the foot or
head of a page, a heading keeps three lines under it, and an image that doesn't fit lets the
text run on and goes to the top of the next page. Padding Mixam needs is blank pages before the
back cover.

Nothing is stored. Posts are fetched from Substack's public API and the PDF is built in the browser.

## Run locally

    node scripts/dev.js     # http://localhost:4321, serves public/ and runs api/*.js

## Licence

MIT. Fonts are SIL Open Font License (Google Fonts). See `LICENSE`.
