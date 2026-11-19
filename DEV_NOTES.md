# Development notes

Running log of assumptions, decisions, known problems and open items for the app build described in
`PRD.md`. Update this file whenever one of them changes. Newest facts win over the PRD where they differ.

Last updated: 2026-11-17.

## Where things stand

| Area | State |
| --- | --- |
| Scraper (`monitor.py`, `brands/`) | Runs twice a day on GitHub Actions (01:07 and 13:07 UTC, 06:07 and 18:07 Pakistan time) and writes to the `monitor-state` branch. A full run of 91 brands took about 6 hours on 2026-11-17. Digest emails are off since 2026-11-17 (`MONITOR_EMAIL: 'off'` in `brands.yml`); the owner uses the app's Changes tab instead |
| Database schema (`supabase/migrations/`) | Applied to the hosted Supabase project (region ap-southeast-2, Sydney) |
| Ingest (`pipeline/`) | Running. First hosted load on 2026-11-17 (run by hand from Actions) took about 20 minutes: 28 brands, 111,727 live products, matching the local load exactly |
| App API (SQL functions for search, feeds, article page, chart) | Written and tested locally (`supabase/migrations/20261116000003_api.sql`, `pipeline/tests/test_api.py`) |
| Mobile app (`app/`) | Expo SDK 58 app. Written: Home feeds, Search and Brand pages with filters and a result count, Article page with price chart, Changes (daily change log), Profile; Watchlist is a placeholder. Typecheck passes and 10 logic tests pass (`npm test`). Lint passes and `npx expo export --platform web` bundles. Never run on a device or opened in a browser. Chart is hand-drawn with react-native-svg (not victory-native), styling is plain StyleSheet (not NativeWind). `app/.env` holds the Supabase URL and anon key and is gitignored; copy `app/.env.example` on a new machine |
| Push notifications, accounts UI | Not started |

## Decisions and assumptions

- **Private test first.** The first goal is an Android build on the owner's own phone. No Play Store work, no public users, until the owner asks.
- **Free Supabase tier (500 MB).** The full catalog is 1.31 GB and does not fit. Only brands listed under `include` in `pipeline/ingest_brands.json` are loaded.
- **The owner picks the brands.** Agents must not add or remove brands in that list on their own. On 2026-11-16 the owner chose 31 brands (see `pipeline/ingest_brands.json`); J. was in the first list and the owner removed it for space. Bachaa Party and Mango are not wanted for now.
- **Size of the selection.** The 28 selected brands that have snapshots measure 401 MB locally (111,727 live products, full history from 2026-11-11). Outfitters, Khushposh and Equator are selected but have no snapshot yet; they load automatically once one exists, if there is room. Brands load in the order listed, and a brand that has never been loaded is not started once the database reaches 420 MB (`INGEST_MAX_DB_MB`); the ingest log line `NOT LOADED` names any brand left out. The hosted database has not been measured, and history and events for these brands took about 33 MB over the first five days (a week in which the 11.11 sales ended, so probably above normal). At that rate the remaining room lasts only a few weeks, so pruning old events or dropping a brand will be needed.
- **Daily scans only.** No proxy, no hourly tier. `brands.scan_tier` exists but nothing reads it yet.
- **The app lives in `app/` in this repository**, not in a separate repository as the PRD first said: there is no second repository yet and one checkout is simpler for a single owner. It has its own `package.json` and can be split out later with `git subtree split`.
- **Names are placeholders.** App name `StockWatch PK`, Android package `com.stockwatchpk.app.dev`. The package ID must be final before the first Play Store upload.
- **Categories and gender** come from `pipeline/normalize.py` plus per-brand settings in `pipeline/brand_types.json`. Order: an exact match on the brand's own product type in that file wins; otherwise keyword rules over the brand's type, then the title, then tags and URL handle (first match wins; bare "shirt", "shirts" and "short" count only when nothing else matched); finally, for brands marked `primary` (the 11 shoe brands), "formal" and "other" become footwear. The file was drafted on 2026-11-18 from the 31 selected brands' data and the owner may edit it. Result on those brands (about 112,000 products): western 42%, footwear 22%, unstitched 7%, eastern 12%, bags and accessories 11%, formal 6%, other 0.6%. Gender is unknown for 31%. Still weak: nightwear, and "formal" depends on brands tagging it.
- **Re-labelling is automatic.** Each ingest compares a hash of `normalize.py` and `brand_types.json` with the one stored in `pipeline_meta`; when it differs, every stored product is re-labelled from its stored title, type, tags and handle (only changed rows are written; about 9 seconds locally for 112,000 products). So a rule or file change reaches the live database on the next ingest run, not only at each brand's next scrape.
- **Brand's own categories (brand page).** `brand_types(brand_id)` lists the brand's product types with at least 3 live products; `search_products(p_types => …)` filters by them. `show_types: false` in `brand_types.json` hides them for brands whose types are colours, seasons, codes or system values (Cambridge, Charcoal, Engine, Ismail Farid, Royal Tag, Uniworth). Breakout, Cougar and Swag Kicks have no types. The app shows the 12 most common and a "More" chip.
- **Product-level price = lowest price over all listed variants**, in stock or not, so a size selling out never looks like a price change.
- **History starts 2026-11-11.** That is the first commit on `monitor-state`; nothing older exists.
- **Events older than 24 hours are stored with `notifiable = false`**, so backfills never notify.
- **Search.** Every word must match (stemmed English full-text over title, brand, type, category, tags); the last word also matches as a prefix. If nothing matches, it falls back to fuzzy title matching (trigram word similarity 0.4). SKU is not searched.
- **"Newest" is weak for now.** Every product loaded in a brand's first scan has the same `first_seen_at`, so the newest sort and the new-arrivals feed only become meaningful for products that appear after that.
- **Home feed "price drops"** ranks by percentage drop over the latest three days that have data, not literally today.
- **Chart series is not downsampled.** `price_series` returns at most the latest 1,000 change points; with daily scans that is years away.
- **Filters live in a side panel** (2026-11-19, owner's request): Home, Search, brand pages and Changes each have one "⚙ Filters" button; the panel edits a draft and shows the matching count before applying. Home is a filterable product list across all brands (default sort "recent activity": latest price change, restock or first appearance). Product lists can be limited to articles that appeared in a day's change log, or on any day, optionally by kind of change (`p_changed_day`, `p_change_kinds`); on a brand page this combines with the brand's own categories. Price ranges come from the 20/40/60/80% points of the current results (`search_price_stats`, `change_price_stats`; `app/src/lib/filters.ts` rounds them) and Min / Max boxes are always shown.
- **Tabs are Home, Search, Changes, Watchlist, Profile.** Android allows five, so on 2026-11-17 the Changes tab took the place of the Inbox placeholder. Personal alerts (PRD NOTIF-3) are to be shown inside Watchlist or behind a bell on Home, not as a sixth tab.
- **Changes tab** reads `change_days`, `change_summary` and `recent_changes` (`supabase/migrations/20261117000001_counts_and_changes.sql`). Days are Pakistan calendar days (Asia/Karachi). It lists product-level events only; the per-size restock events are not shown there. It can be sorted (newest, biggest percentage drop, price either way) and filtered by shared category and price; a change's price is the price right after it for price events, otherwise the product's current lowest price. Filters stay when switching days. It also filters by stock now (in stock / sold out now, judged on the product's current state, not at the time of the change) and gender.
- **Excluding brands and categories:** brand and category chips (Search, brand pages, Changes) cycle off → only this → hide this (shown crossed out with ✕). Server parameters `p_exclude_brand_ids` / `p_exclude_categories`; products with no category are never hidden by a category exclusion. On the Changes tab the brand include/exclude is applied in the app to the summary counts so hidden brands keep their chip.
- **App requests omit default arguments** (`compact()` in `app/src/lib/api.ts`), so an app update that adds a database parameter keeps working against the previous database version until a new filter is actually used. A brand's first scan creates no events, so a newly added brand shows no changes until its second scan.
- **Result counts** come from `search_products_count`, which shares its filter code with `search_products` (`private.search_clause`) and stops counting at 10,001 (shown as "10,000+").
- **Deploy order for database changes:** a migration reaches the hosted database only when `ingest.yml` runs (daily, or by hand). App code that calls a new or changed function breaks until then, so run the ingest workflow by hand right after pushing such a change.
- **Do not wrap a sized `Pressable` in `<Link asChild>`.** On the owner's phone the Home cards lost their 148 px width and showed full-screen images, almost certainly because `Link asChild` dropped the function-form `style`. Navigation now uses `Pressable` with `router.push(...)` everywhere, and sizing lives on an outer `View`.
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

## Phone build and notifications

- **Installable build:** `app/eas.json` profile `preview` makes an APK for internal distribution, on update channel `preview`.
- **Database settings live in `app/app.json` → `extra.supabase`** (URL and anon key; public by design, RLS protects the data). On 2026-11-18 two over-the-air updates went out without them, because `eas update --environment preview` does not read `app/.env` and no EAS environment variables were set; the app showed "Not connected yet". `EXPO_PUBLIC_*` variables still take precedence when set (for example to point at a local database). Build: `npx eas-cli build -p android --profile preview` from `app/` after `eas login` and `eas init`.
- **Over-the-air updates:** `expo-updates` with `runtimeVersion` policy `appVersion`. JavaScript changes ship with `npx eas-cli update --channel preview --message "..."` and apply after the app is closed and reopened (up to twice). Adding a native package or changing native config needs a new APK; bump `version` in `app.json` when that happens so old builds do not receive incompatible updates.
- **"New data is in" push:** after each ingest run that loaded at least one scan, `pipeline/notify_run.py` sends one push per registered phone through the Expo Push Service, summarising notifiable product-level changes; tapping opens the Changes tab. Phones register anonymously via `register_device` into `broadcast_devices` (not readable by the app; capped at 500). Tokens Expo reports as `DeviceNotRegistered` are deleted. `PUSH_NOTIFY=off` disables it; a push failure never fails the ingest. Delivery receipts are not checked.
- **Android push needs Firebase:** `app/google-services.json` (added to the build automatically by `app/app.config.ts` when present) and the FCM V1 service-account key uploaded to Expo (`eas credentials`). Service-account JSON files are gitignored. Without them the app works but cannot register for pushes. Expo Go on Android cannot receive pushes at all.
- **Permission prompt** appears on first launch (acceptable for the owner's test; PRD AUTH-6 wants it after showing value, for the public release).

## Watchlist (anonymous accounts)

- Each phone signs in with a **Supabase anonymous account** the first time it needs one (startup push registration or the first ☆ Watch). Watches, devices and the inbox use the user tables and RLS from `20261116000002_users.sql`, so a later Google or email sign-in can be linked to the same account. **Requires "Allow anonymous sign-ins" in the Supabase dashboard** (Authentication → Sign In / Providers); it was off on 2026-11-18 and the app shows a message until it is on.
- A watch covers the whole article (not one size yet) and alerts on every product-level change: price drop or rise, back in stock, sold out, sale started or ended, removed. `price_at_watch` is filled by a trigger; at most 300 watches per account.
- After each ingest run `pipeline/notify_watches.py` writes one `notifications` row per user and event (unique, so re-runs never repeat an alert) and sends one push per user: the alert itself, or "N watched articles changed" opening the Watchlist. Alerts for a user with no registered phone are kept with status `held` and still appear in the in-app Alerts list.
- `register_my_device` moves a push token to the newest account that registers it (a reinstall creates a new anonymous account and loses the old watchlist; linking a real sign-in will fix that).
- Reinstalling the app or clearing its data loses the anonymous session and with it the watchlist.

## Operational facts

- **Calls from the app are cancelled after about 3 seconds** on the hosted (free) database. On 2026-11-20 any sort that read every product (discount, recent price change, recent activity, price) and an unfiltered price-statistics call hit that limit, although the same queries took well under a second locally. Every sort the app offers now has an index in exactly its ORDER BY form (`20261120000001_sort_indexes.sql`), and `search_price_stats` measures broad results on a 10% page sample. New sorts or whole-table queries need the same treatment; test them against the live database, not only locally.

- **Database size (free plan stops writes above 500 MB; it was 485 MB on 2026-11-19).** At the owner's request: products keep at most 3 images (Shopify's changing `?v=` parameter removed, which also stops daily row rewrites), descriptions are cut to 500 characters, and product-level option lists are not stored (`normalize.py`, `ingest.py`). Changes (`product_events`) older than 90 days and products removed from the store over 60 days ago are deleted (price history is kept). The typo-tolerant search fallback and its trigram index are gone, so search words must match. `pipeline/maintain.py` applies all of this to stored rows in batches before every ingest; `ingest.yml` input `compact: yes` additionally rebuilds indexes and tables, each only if the database plus a second copy stays under 495 MB (`COMPACT_MAX_DB_MB`), and logs what it skipped. Plain VACUUM makes freed space reusable but the reported size only drops after a rebuild.

- **Repository moved on 2026-11-19** to the public repo `github.com/fafo-0847/brands-monitor` (unlimited Actions minutes). Every branch there starts from a single "Initial commit": the history was not carried over, and `monitor-state` held a copy of the code, not the brand snapshots. Scraping therefore restarted every brand from a fresh baseline (first scan, no change report). The database kept all products and history. `pipeline/ingest.py` handles the missing history: when a brand's last loaded commit is not in the branch, it logs a warning and loads only the newest snapshot, which is compared with the database as usual. A local backup of the old history is the branch `history-backup` on the owner's machine; the old repo `soban23/brands-monitor` returned "not found" on 2026-11-19.
- Secrets must be set again in the new repo: `DATABASE_URL` (required), `MONITOR_PROXY` and `EXPO_ACCESS_TOKEN` (optional).

- `DATABASE_URL` (GitHub secret) must be the Supabase **session pooler** string. The direct connection is IPv6-only and GitHub runners have no IPv6.
- `ingest.yml` is triggered by the brands workflow finishing, and `workflow_run` triggers only work once the workflow file is on the default branch.
- `ingest.yml` works on GitHub, including the partial fetch of `monitor-state`. A run exits with an error only when a brand could not be processed; rejected snapshots and brands left out for space are shown as warnings.
- The hosted API answers through the anon key: search (including the typo fallback) and the three home feeds returned data on 2026-11-17. Calls took 0.5 to 1.9 seconds measured from the owner's machine in Pakistan; the project is in Sydney, so much of that is distance.
- `DATABASE_URL` user name for the pooler is `postgres.<project-ref>`, and special characters in the password must be URL-encoded.
- The repository is private. Private repositories get 2,000 free Actions minutes a month and each job is rounded up to a minute; the brands workflow runs one job per brand per day. Actual usage has not been measured.
- A full local backfill (206 commits, all brands) took 9.5 minutes. A daily run re-reads every snapshot; against the hosted database expect it to be slower because staging rows are uploaded.
- Local test database: `docker run -d --name stockwatch-pg -e POSTGRES_PASSWORD=postgres -p 54329:5432 pgvector/pgvector:pg17`. Connect with `127.0.0.1`, not `localhost` (IPv6 lookup stalls for 8 seconds per connection on Windows).
- On the owner's machine that container holds two loaded databases: `stockwatch` (every brand) and `stockwatch_free` (64 mid-sized and small brands, an earlier trial subset that is not the owner's selection).

## Open items

1. Owner emails were turned off on 2026-11-17 at the owner's request (`MONITOR_EMAIL=off`). With email off the baseline is saved without sending; with it on, the rule that a failed email leaves the baseline untouched still holds (`tests/test_brands_run.py`).
2. Fix the 25,000-product cut-off in `brands/engine.py`.
3. Decide final app name, package ID and domain before any store upload.
4. Hand-check category / gender labels on a sample and tune `pipeline/normalize.py`.
5. Push notifications (`pipeline/notify_push.py`) are not written.
6. No retention policy for `product_events` or history yet; decide before the database nears its limit.
7. SKU search is not indexed (`variants.sku` has no index).
8. **Equator** cannot be scraped from GitHub (Cloudflare refuses cloud-server addresses; it loads normally from the owner's home connection and its robots.txt allows catalog pages). Owner's decision on 2026-11-20: leave it for now. Planned option: a Windows Task Scheduler job on the owner's PC that scrapes Equator twice a day and pushes `brands/equator/state.json` to `monitor-state`, with Equator removed from the GitHub matrix. Do not route it through free proxies or disguise the scraper.
