# Data model

Written from the need before touching any data (BUSINESS.md rule 5). The need: a writer
turns their Substack into a printed magazine they can hold.

## Writer
| field | question it answers |
|---|---|
| handle | who is this? (`substack.com/@handle`) |
| name | what does the masthead default to? |
| publications[] | which newsletters are theirs? (one person can run several) |

## Publication
| field | question |
|---|---|
| base | where do posts come from? (`<sub>.substack.com` or a custom domain) |
| name | which newsletter is this post from? |

## Post
| field | question |
|---|---|
| slug, title, subtitle, date | what goes in the contents and the article head? |
| audience | will the printed text be complete, or is it paywalled and cut short? |
| wordcount | how much paper will it take? |
| body (blocks: heading, paragraph runs with italic/bold, quote, preformatted, list, image + caption, rule) | what is printed, with the writer's emphasis and line breaks intact? |
| images (url, width, height) | how big can each image print, and at what resolution? |

## Magazine (the user's choices)
| field | question |
|---|---|
| name | masthead (defaults to the writer's name) |
| posts[] (ordered, oldest first) | what is inside, in what order |
| cover image | their own art, upload only |
| typography | one of five pairings, restyles the laid-out issue |

## Print file
| field | question |
|---|---|
| printer (Mixam / FedEx Office) | which spec |
| trim, bleed, page count | will the printer accept it? Mixam: Letter 8.5 x 11 in, 0.125 in bleed, pages a multiple of 4, staple binding 8 to 96 pages, self-cover. FedEx: Letter, no bleed (FedEx prints with a small margin), even page count |
| binding (staple / perfect PUR) | can it be stapled, or does it need a glued spine? past 96 pages it must be PUR |
| inside paper, cover paper | how thick is the book? (Mixam caliper per sheet) |
| spine width | how wide is the middle panel of the cover spread? (Mixam's cart has the final number) |

## Reality check (2026-10-28)
Every field fills from the public, keyless Substack API: `/api/v1/user/<handle>/public_profile`
(name, publications), `/api/v1/archive` (paged, ~24 rows per page whatever `limit` says, so page
until empty), `/api/v1/posts/<slug>` (`body_html`, `audience`). Paywalled bodies come back
truncated, which is why `audience` is carried and marked in the picker. Image width/height are
on each `<img>`. Nothing in the model is unfillable.

2026-10-28, PUR added: paper calipers and PUR page limits are in Mixam's calculator data
(`/api/products/1/100007`); the spine rule was fitted to its live `/api/offer` quotes and the cart.
