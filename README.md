# Substack to Magazine

**Live:** https://substack-magazine.vercel.app

Turn your Substack into a physical magazine. Enter your Substack username, pick the posts you want,
name the magazine, and it lays them out as a printed issue you can page through. Upload your own
cover art, try five typefaces, then download a print-ready PDF with step-by-step ordering
instructions for Mixam (a stapled magazine) or FedEx Office (letter pages, same-day pickup).

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

| | Mixam | FedEx Office |
|---|---|---|
| Page | 8.5 × 11 in trim + 0.125 in bleed (630 × 810 pt), TrimBox and BleedBox set | 8.5 × 11 in, no bleed |
| Cover | Art runs to the bleed edge | Art inside a 0.25 in border, since FedEx prints with a margin |
| Pages | Multiple of 4 (saddle stitch), minimum 8, padded with ruled Notes pages | Same pages |

Nothing is stored. Posts are fetched from Substack's public API and the PDF is built in the browser.

## Run locally

    node scripts/dev.js     # http://localhost:4321, serves public/ and runs api/*.js

## Licence

MIT. Fonts are SIL Open Font License (Google Fonts). See `LICENSE`.
