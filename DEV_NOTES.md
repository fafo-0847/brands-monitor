# Development notes

Running log of assumptions, decisions, known problems and open items for the app build described in
`PRD.md`. Update this file whenever one of them changes. Newest facts win over the PRD where they differ.

Last updated: 2026-11-17.

## Where things stand

| Area | State |
| --- | --- |
| Scraper (`monitor.py`, `brands/`) | Unchanged. Runs daily on GitHub Actions, writes to the `monitor-state` branch, still emails the owner |
| Database schema (`supabase/migrations/`) | Written and tested locally. Applied to the hosted Supabase project by the first `ingest.yml` run |
| Ingest (`pipeline/`) | Written, tested, full backfill verified locally. Not yet run against the hosted database |
| App API (SQL functions for search, feeds, article page, chart) | Written and tested locally (`supabase/migrations/20261116000003_api.sql`, `pipeline/tests/test_api.py`) |
| Mobile app (`app/`) | Expo SDK 58 app. Written: Home feeds, Search with filters, Brand page, Article page with price chart, Profile; Watchlist and Inbox are placeholders. Typecheck passes and 10 logic tests pass (`npm test`). Lint passes and `npx expo export --platform web` bundles. Never run on a device or opened in a browser. Chart is hand-drawn with react-native-svg (not victory-native), styling is plain StyleSheet (not NativeWind). `app/.env` holds the Supabase URL and anon key and is gitignored; copy `app/.env.example` on a new machine |
| Push notifications, accounts UI | Not started |

## Decisions and assumptions

- **Private test first.** The first goal is an Android build on the owner's own phone. No Play Store work, no public users, until the owner asks.
- **Free Supabase tier (500 MB).** The full catalog is 1.31 GB and does not fit. Only brands listed under `include` in `pipeline/ingest_brands.json` are loaded.
- **The owner picks the brands.** Agents must not add or remove brands in that list on their own. On 2026-11-16 the owner chose 31 brands (see `pipeline/ingest_brands.json`); J. was in the first list and the owner removed it for space. Bachaa Party and Mango are not wanted for now.
- **Size of the selection.** The 28 selected brands that have snapshots measure 401 MB locally (111,727 live products, full history from 2026-11-11). Outfitters, Khushposh and Equator are selected but have no snapshot yet; they load automatically once one exists, if there is room. Brands load in the order listed, and a brand that has never been loaded is not started once the database reaches 420 MB (`INGEST_MAX_DB_MB`); the ingest log line `NOT LOADED` names any brand left out. The hosted database has not been measured, and history and events for these brands took about 33 MB over the first five days (a week in which the 11.11 sales ended, so probably above normal). At that rate the remaining room lasts only a few weeks, so pruning old events or dropping a brand will be needed.
- **Daily scans only.** No proxy, no hourly tier. `brands.scan_tier` exists but nothing reads it yet.
- **The app lives in `app/` in this repository**, not in a separate repository as the PRD first said: there is no second repository yet and one checkout is simpler for a single owner. It has its own `package.json` and can be split out later with `git subtree split`.
- **Names are placeholders.** App name `StockWatch PK`, Android package `com.stockwatchpk.app.dev`. The package ID must be final before the first Play Store upload.
- **Categories and gender are keyword guesses** (`pipeline/normalize.py`). Coverage on the full catalog: gender for 74% of products, size for 81% of variants in size-level brands, 6% of products in category `other`. Accuracy has not been checked by hand.
- **Product-level price = lowest price over all listed variants**, in stock or not, so a size selling out never looks like a price change.
- **History starts 2026-11-11.** That is the first commit on `monitor-state`; nothing older exists.
- **Events older than 24 hours are stored with `notifiable = false`**, so backfills never notify.
- **Search.** Every word must match (stemmed English full-text over title, brand, type, category, tags); the last word also matches as a prefix. If nothing matches, it falls back to fuzzy title matching (trigram word similarity 0.4). SKU is not searched.
- **"Newest" is weak for now.** Every product loaded in a brand's first scan has the same `first_seen_at`, so the newest sort and the new-arrivals feed only become meaningful for products that appear after that.
- **Home feed "price drops"** ranks by percentage drop over the latest three days that have data, not literally today.
- **Chart series is not downsampled.** `price_series` returns at most the latest 1,000 change points; with daily scans that is years away.
- **Image URLs are hotlinked** from each brand's CDN; nothing is rehosted.

## Brand selection and sizes

Budget: keep the selected brands under about 400 MB (roughly 100,000 products) so history and user data have room inside 500 MB. Sizes below are estimates from a local load of every brand on 2026-11-16 (rows plus indexes); the hosted database has not been measured.

| Brand | Slug | Live products | Approx. MB |
| --- | --- | --- | --- |
| J. (Junaid Jamshed) | `j-junaid-jamshed` | 24,345 | 101 |
| Khazanay | `khazanay` | 25,000 | 86 |
| Stylo | `stylo` | 25,000 | 86 |
| Bachaa Party | `bachaa-party` | 25,000 | 70 |
| Saya | `saya` | 12,445 | 61 |
| Engine | `engine` | 18,507 | 59 |
| Edenrobe | `edenrobe` | 18,874 | 53 |
| Zellbury | `zellbury` | 17,653 | 47 |
| Generation | `generation` | 7,778 | 41 |
| Bonanza Satrangi | `bonanza-satrangi` | 10,531 | 37 |
| Charcoal | `charcoal` | 11,027 | 31 |
| Maria B | `maria-b` | 8,832 | 30 |
| Eminent | `eminent` | 5,707 | 25 |
| Gul Ahmed / Ideas | `gul-ahmed-ideas` | 7,143 | 25 |
| Uniworth | `uniworth` | 7,299 | 24 |
| Diners | `diners` | 6,475 | 23 |
| Borjan | `borjan` | 5,200 | 23 |
| OnlineThriftStore.pk | `onlinethriftstore-pk` | 9,561 | 22 |
| Cambridge | `cambridge` | 4,851 | 22 |
| Ethnic | `ethnic` | 5,109 | 20 |
| MTJ | `mtj` | 6,115 | 20 |
| Unze London | `unze-london` | 4,543 | 19 |
| Furor | `furor` | 6,520 | 19 |
| 1st Step | `1st-step` | 5,244 | 19 |
| Asim Jofa | `asim-jofa` | 6,946 | 18 |
| So Kamal | `so-kamal` | 6,429 | 18 |
| Insignia | `insignia` | 4,631 | 17 |
| Limelight | `limelight` | 5,479 | 15 |
| Sana Safinaz | `sana-safinaz` | 5,062 | 14 |
| Preloved Labels | `preloved-labels` | 4,166 | 12 |
| Lulusar | `lulusar` | 2,826 | 11 |
| Zeesy | `zeesy` | 2,255 | 11 |
| Ndure | `ndure` | 2,272 | 10 |
| Servis | `servis` | 2,670 | 10 |
| Nishat Linen | `nishat-linen` | 3,005 | 10 |
| Swag Kicks | `swag-kicks` | 3,323 | 9 |
| Mocciani | `mocciani` | 1,886 | 8 |
| Cross Stitch | `cross-stitch` | 2,068 | 8 |
| Bata | `bata` | 2,266 | 8 |
| Alkaram Studio | `alkaram-studio` | 1,892 | 7 |
| Rastah | `rastah` | 1,760 | 7 |
| ThriftShop.pk | `thriftshop-pk` | 3,479 | 7 |
| Starlet | `starlet` | 1,506 | 6 |
| Beechtree | `beechtree` | 1,410 | 6 |
| Ismail Farid | `ismail-farid` | 1,949 | 5 |
| Logo | `logo` | 1,737 | 5 |
| Zeen | `zeen` | 1,681 | 5 |
| Beyond East | `beyond-east` | 1,664 | 5 |
| Monark | `monark` | 1,507 | 4 |
| Lawrencepur | `lawrencepur` | 1,122 | 4 |
| Zara Shahjahan | `zara-shahjahan` | 1,041 | 4 |
| Batik | `batik` | 848 | 4 |
| Elan | `elan` | 1,125 | 3 |
| Urban Sole | `urban-sole` | 837 | 3 |
| WeWear | `wewear` | 757 | 3 |
| Sputnik | `sputnik` | 879 | 3 |
| Threads & Motifs | `threads-motifs` | 845 | 3 |
| Agha Noor | `agha-noor` | 740 | 3 |
| Baroque | `baroque` | 844 | 3 |
| Dynasty Fabrics | `dynasty-fabrics` | 458 | 3 |
| Chinyere | `chinyere` | 866 | 2 |
| Cougar | `cougar` | 2,346 | 2 |
| Shaffer | `shaffer` | 688 | 2 |
| Royal Tag | `royal-tag` | 905 | 2 |
| Giordano | `giordano` | 293 | 2 |
| Ego | `ego` | 715 | 2 |
| Aldo | `aldo` | 694 | 2 |
| Breakout | `breakout` | 2,141 | 2 |
| Hush Puppies | `hush-puppies` | 247 | 2 |
| Manto | `manto` | 523 | 2 |
| Focus Clothing | `focus-clothing` | 437 | 2 |
| Groovy | `groovy` | 418 | 1 |
| Amir Adnan | `amir-adnan` | 462 | 1 |
| Walkeaze | `walkeaze` | 249 | 1 |
| Jadeno | `jadeno` | 382 | 1 |
| Sapphire | `sapphire` | 1,131 | 1 |
| Jafferjees | `jafferjees` | 317 | 1 |
| AWKWRD | `awkwrd` | 304 | 1 |
| Orient Textiles | `orient-textiles` | 820 | 1 |
| Bareeze | `bareeze` | 948 | 1 |
| Kross Kulture | `kross-kulture` | 180 | 1 |
| Chester Bernard | `chester-bernard` | 165 | 1 |
| Retro Walk | `retro-walk` | 114 | 1 |
| Garderobe | `garderobe` | 112 | 1 |
| Khaadi | `khaadi` | 110 | 1 |

Not available to pick:

| Reason | Brands |
| --- | --- |
| Scraper strategy `unavailable` | charizma, mushq, metro, kayseria, leisure-club, ecs, image (see `brands/README.md`) |
| Not scraped in CI | mango (429 from datacenter IPs) |
| No snapshot on `monitor-state` yet | Any configured brand whose scan has not succeeded since the move to `brands/<slug>/` (on 2026-11-16 this included outfitters and khushposh). Once a snapshot exists they can be selected |

To add a brand: add its slug to `include`, check free space with `python -m pipeline.ingest --stats`, run the ingest.

To drop a loaded brand and reuse its space: remove the slug from `include`, then run `python -m pipeline.ingest --drop <slug>`. It deletes the brand's products, variants, history, events, scans and cursor (and any user watches on those products). There is no workflow for this; it is run by hand with `DATABASE_URL` set.

## Known problems in the data

- **25,000-product cut-off.** `strategy_shopify_json` stops at 100 pages × 250. Khazanay, Stylo and Bachaa Party hit it exactly, so their catalogs are incomplete and the set returned can differ between scans (false "new"/"removed" events). Warn the owner if any of the three is selected before the scraper is fixed.
- **Cougar, 2026-11-16.** The scraper accepted a partial catalog (866 products, 2,346 the day before) and overwrote its baseline. The ingest rejected that snapshot. If the next scan is complete it loads normally; if Cougar keeps returning the short catalog every snapshot is rejected until someone runs `python -m pipeline.ingest --brand cougar --force`.
- **Product-level brands have no sizes**: khaadi, sapphire (`sfcc`), bareeze, cougar, mango (`sitemap_jsonld`), breakout, equator, orient-textiles (`hydrogen_listing`). `brands.granularity = 'product'`; the app must hide size filters and size watches for them.
- **Image lists churn.** Shopify image URLs carry a `?v=` parameter that changes; such a change rewrites the product row but creates no event.
- **A removed product keeps its last price and stock values.** Always filter on `removed_at is null`.
- **Lama Retail** labels rupee prices as SAR at the source; the scraper corrects this (`pkr_labelled_as`).

## Operational facts

- `DATABASE_URL` (GitHub secret) must be the Supabase **session pooler** string. The direct connection is IPv6-only and GitHub runners have no IPv6.
- `ingest.yml` is triggered by the brands workflow finishing, and `workflow_run` triggers only work once the workflow file is on the default branch.
- `ingest.yml` and `pipeline-tests.yml` have not yet run on GitHub. The partial fetch of `monitor-state` (`--filter=blob:none`, snapshots downloaded on demand) is untested there.
- The repository is private. Private repositories get 2,000 free Actions minutes a month and each job is rounded up to a minute; the brands workflow runs one job per brand per day. Actual usage has not been measured.
- A full local backfill (206 commits, all brands) took 9.5 minutes. A daily run re-reads every snapshot; against the hosted database expect it to be slower because staging rows are uploaded.
- Local test database: `docker run -d --name stockwatch-pg -e POSTGRES_PASSWORD=postgres -p 54329:5432 pgvector/pgvector:pg17`. Connect with `127.0.0.1`, not `localhost` (IPv6 lookup stalls for 8 seconds per connection on Windows).
- On the owner's machine that container holds two loaded databases: `stockwatch` (every brand) and `stockwatch_free` (64 mid-sized and small brands, an earlier trial subset that is not the owner's selection).

## Open items

1. Owner emails are still on. Turn them off after the hosted ingest has run cleanly for 3 days (`PRD.md` M1).
2. Fix the 25,000-product cut-off in `brands/engine.py`.
3. Decide final app name, package ID and domain before any store upload.
4. Hand-check category / gender labels on a sample and tune `pipeline/normalize.py`.
5. Push notifications (`pipeline/notify_push.py`) are not written.
6. No retention policy for `product_events` or history yet; decide before the database nears its limit.
7. SKU search is not indexed (`variants.sku` has no index).
