# ST:CC Card Dataset — Workflow
## Single source of operational truth.

**This repository is the dataset**: the card database, the TCG Schema vocabulary it is
mapped onto, the generated graph, and one page per card. Matthew McCue's strategy guides
and the Card Scanner live in the **ST:CC Strategy Compendium**
(https://periodic-agent.github.io/stcc-strategy/) and were removed from here on
24 Aug 2026, along with the conventions for the guide build pipeline, the scanner, the
shared design system, the index, and the editorial protocol. What remains is what the
data needs.

Published at **https://tcg-schema.github.io/stcc-strategy/**. The semantic root is
**https://tcg-schema.org/stcc**, which names no serving host on purpose — see the
Semantic layer section.

---

## Session Startup

Clone, don't fetch: `raw.githubusercontent.com` and `web_fetch` sit behind caches and can
return HTTP 200 with a silently stale copy.

```
git clone --depth 1 git@github.com:tcg-schema/stcc-strategy.git
```

The card JSONs at the repo root are the editing surface. Everything else the site serves
— the vocabulary, the graph, the 556 card pages, the sitemap — is generated from them:

```
python3 tools/build_ontology.py --report     # data/stcc-ontology.ttl + data/cards.jsonld
python3 tools/build_card_pages.py            # card/, index.html, sitemap.xml
python3 tools/test_ontology.py --core core.ttl   # curl -o core.ttl https://www.tcg-schema.org/core.ttl
```

Never hand-edit the ttl, the jsonld or a card page. `--check` on both generators exits 1
when a committed output differs from a fresh build.

**Cost discipline.** Work from the local clone and grep it; don't probe raw URLs file by
file, and batch bash calls — every tool round-trip replays the whole conversation.

---

---

## Push Pipeline

**Push ONLY after Periodic_agent reviews the presented files and explicitly approves. Never push before the go-ahead.**

**Current remote (24 Aug 2026): `git@github.com:tcg-schema/stcc-strategy.git` over SSH.**
The repo moved orgs, so `push_to_github.py` — which is hardcoded to
`periodic-agent/stcc-strategy` over HTTPS with a PAT — no longer targets this repository.
It is kept for the anonymity gate it carries and for the compendium repo. When pushing
over SSH, **set the commit author explicitly**: the local git identity is a real name,
and the Anonymity Rules below apply to commit metadata as much as to file contents:

```
git -c user.name=periodic-agent -c user.email=periodic-agent@users.noreply.github.com commit
```

The historical HTTPS pipeline:

```
GH_TOKEN=<token> python3 push_to_github.py --pii-file <path_to_pii_denylist.txt> <local_path> <repo_path> "commit message"
```
Fetch the script from the live repo before running. It shallow-clones the repo, copies the file in, commits, and pushes via git with a one-shot authenticated URL (no GitHub API dependency; `api.github.com` is blocked in some sandboxes while git over HTTPS works). Files deploy via GitHub Pages in ~60 seconds. Multi-file commits: `-m "msg" local:repo local:repo ...`.

Since v3 the script refuses to run without the PII denylist (`--pii-file` or `PII_FILE` env; see Anonymity Rules below). No denylist = no push, by design.

---

## GitHub Token Handling

**The token is NOT in the repo and NOT in the script.** It is a **fine-grained PAT** scoped to `periodic-agent/stcc-strategy` only, permission **Contents: read/write** (plus mandatory Metadata: read). Worst-case leak damage is limited to this one repo.

**Where it lives:** project knowledge file `git_pat_token.txt`. Every project chat can read it; Periodic_agent never types it.

**How to use it at push time:** read the token from the project knowledge file and pass it to the script via the `GH_TOKEN` environment variable, or point the script at the file directly:
```
python3 push_to_github.py <local_path> <repo_path> "message" --token-file <path_to_git_pat_token.txt>
```

**WARNING — token hygiene rules for every session:**
1. NEVER write the token value into any file saved to outputs or pushed to the repo. Not in scripts, not in HTML comments, not in WORKFLOW.md deltas.
2. NEVER print the token in chat, in logs, or in command echoes. The push script scrubs it from its own output; keep it that way.
3. NEVER hardcode it back into `push_to_github.py`. The previous hardcoded token was exposed publicly and had to be revoked (Jul 2026).
4. If the token ever appears in a pushed file or in the public repo history: tell Periodic_agent immediately so he can revoke it on GitHub.

**Expiry:** fine-grained PATs expire (1 year max). If a push fails with an auth error, the likely cause is expiry; Periodic_agent mints a new token and replaces `git_pat_token.txt` in project knowledge.

---

---

## Anonymity Rules

**This is an anonymous project.** The site owner appears everywhere — files, commit messages, configs, docs, chat-visible output — only as **Periodic_agent** (GitHub: periodic-agent). The owner's real name, personal email addresses, and machine username must never appear in anything that leaves the session.

**The denylist:** `pii_denylist.txt` lives in **project knowledge** (next to `git_pat_token.txt`), NEVER in the repo, never in outputs destined for pushing. One term per line, `#` for comments.

**The gate (fail closed):** `push_to_github.py` v3 refuses to push unless given the denylist (`--pii-file <path>` or `PII_FILE` env). It scans file contents (binary-safe, case-insensitive), repo paths, and the commit message; any hit blocks the entire push and reports the term masked. It also refuses to push the denylist itself. There is no bypass flag.

**Reusable standalone gate:** `tools/push_gate.py` — same scan logic plus `--scan-dir` (walk a folder) and `--scan-git-history` (scan every object in a repo's full history). Stdlib only; vendor it into any other project alongside its own denylist.

**Hygiene rules for every session:**
1. Watch indirect leaks: local Windows paths in tracebacks or logs, script headers, EXIF in photographed cards, autofilled author fields, example email addresses.
2. Never paste the denylist contents into chat, pushed files, or WORKFLOW deltas; refer to terms masked if a hit must be discussed.
3. If a personal identifier ever lands in the public repo: tell Periodic_agent immediately; remediation is a git-filter-repo rewrite, force-push, and GitHub support purge.

**Audit (quarterly, and before any public announcement):**
```
git clone https://github.com/periodic-agent/stcc-strategy.git audit && \
python3 audit/tools/push_gate.py --pii-file <path_to_pii_denylist.txt> --scan-git-history audit
```
Expected output: `push_gate: clean — no denylisted term in any object of audit`.

---

---

## Card Database

### File structure
```
box1.json    -- Captain's Chair, complete (250 cards)                         [repo ROOT]
box2.json    -- To Boldly Go, live (248 cards incl. Khan deck)                [repo ROOT]
box3.json    -- Second Contact, live (99 cards: Common, Freeman, Pike, Riker) [repo ROOT]
promo1.json  -- Promo Pack 1, complete (5 cards, split out of box1.json)      [repo ROOT]
promo2.json  -- Promo Pack 2, seeded (6 cards; traits/icons pending, Issue 5) [repo ROOT]
```
The boxN.json files live at the **repo root**, not in a `data/` folder.

### Canonical JSON schema (per card)
```json
{
  "id": "bruce-maddox",
  "name": "Bruce Maddox",
  "suit": "Person",
  "source": "Common",
  "game_box": "Captain's Chair",
  "species_traits": ["Human"],
  "regular_traits": ["Starfleet", "Scientist", "Engineer"],
  "other_traits": [],
  "icons": [
    {"specialty": "Research", "type": "Skill"},
    {"specialty": "Research", "type": "Focus"}
  ],
  "filename": "bruce-maddox.jpg"
}
```

### Trait classification — rulebook p.36 (canonical)
**Species Traits:** Alien, Aenar, Andorian, Android, Bajoran, Betazoid, Borg, Breen, Cardassian, Changeling, Ferengi, Human, Jem'Hadar, Kelpien, Klingon, Orion, Pakled, Reman, Romulan, Synthetic, Tellarite, Transcendent, Trill, Vorta, Vulcan, XB, Xindi

**Regular Traits:** Ambassador, Anomaly, Augment, Beverage, Business, Cloak, Communication, Creature, Doctor, Dominion, Engineer, Helmet, Hologram, Imperial, Mind Control, Ops, Pilot, Maquis, Scientist, Security, Shady, Spy, Starbase, Starfleet, Telepath, Time Travel, Weapon

**Other Traits:** Attack, Ongoing, Surprise, Wildcard

### Icon schema — rulebook p.17
- `specialty`: Research / Influence / Military / Any / Variable
- `type`: Skill / Focus
- **Any** + Skill or Focus: counts for all three specialties in the relevant filter
- **Variable** Skill: conditional value, shown in its own filter category
- No "Wild" terminology — not a rulebook term, eliminated from schema
- **Repeated objects, no `count`.** One `{type,specialty}` object per printed icon; a
  card with two Military Skills is two objects, not `{count:2}`. `normIcons` renders one
  pill per object, so repeats display correctly with no scanner logic. (Box 1 used a
  `count` field until Jul 2026; removed for a uniform one-object-per-icon model.)

### Icon filtering logic
- Selecting Research Skill returns: Research Skill + Any Skill cards
- Selecting Research Focus returns: Research Focus + Any Focus cards
- Selecting Variable returns: Variable Skill cards only
- Same logic applies to Influence and Military

### Suit conventions
- Market suits: Person, Ally, Ship, Cargo, Location, Encounter, Incident
- Crew deck only: Captain, Directive, Status
- **Captain and Directive are acceptable deviations from the rulebook** -- not official "suits" but used as suit values in the database for practical filtering. Noted and intentional.
- Captain cards colored gold, Directive cards gray, Status cards light blue

### Update cycle (revised 17 Aug 2026 -- CARD TEXT edition)
**The sheet is back, with a new job: card text.** Metadata for Boxes 1-3 and both promo
packs remains complete and canonical in the five JSON files at repo root (that part of
the 29 Jul 2026 retirement stands). What the JSONs still lack is rule text, so the Drive
sheet was regenerated from the ground up by `tools/build_text_workbook.py` (supersedes
`build_workbook.py`): one tab per box (now including Captain's Chair), one row per JSON
card (610), metadata pre-filled from the JSONs as read-only reference, card-image links,
and **Card text as the last column** -- seeded for 540 cards from Periodic_agent's
transcription (`data/card-text-source.csv`), empty/orange for the 70 that need entry
(Archer, Rebner and Khan decks, treated as ordinary decks). 36 Mission cards ride along
flagged "not in JSON yet" until the JSONs gain a Mission suit. Contributor/Notes columns
were dropped; credit history lives in the archived retired sheet.
- Division of authority: **metadata bugs -> fix the JSON; card text -> fix the sheet** until
  text verification completes, then text flows back into the JSONs via a future
  `tools/build_text_from_sheet.py` (same read-only-sheet discipline as
  `build_box2_from_sheet.py`) and the sheet retires again.
- Same Drive file ID as before; Periodic_agent replaces content via right-click ->
  Manage versions -> Upload new version (never delete-and-reupload). Archived copy of the
  retired metadata sheet: `archive/stcc-card-database-retired-2026-08-17.xlsx`.
- Card text is transcribed **exactly as printed**, typos included (see Misprints below).
  Abilities are separated by a line containing `---`.

Historical description of the metadata cycle follows, kept for Box 4/5 reactivation.
- File: `stcc-card-database.xlsx` on Periodic_agent's Drive (kept as .xlsx; volunteers edit via shared link in Sheets Office mode). Drive file ID stays constant.
- Tabs: README, TBG (Box 2), Second Contact (Box 3), Vocabulary. Status column tracks progress (AI-seeded — verify / verified / needs entry / unreadable). Card image column links to the live site.
- **Never regenerate the sheet wholesale.** To add cards: read the live sheet (Google Drive connector), merge by Card code (fallback key: box + name + suit), append ONLY new rows, hand Periodic_agent the updated .xlsx. Periodic_agent updates Drive via right-click → Manage versions → Upload new version (keeps the ID and the shared link; never delete-and-reupload).
- Existing rows are never modified by a merge; "verified" statuses and Contributor credits survive every update.
- **New guide imports feed the database:** when a TBG/Second Contact guide is imported, extract its card images to `img/box2/` or `img/box3/` (convention names) AND read the card faces into new sheet rows before the guide ships.
- Scanner build: read the sheet, validate traits against the Vocabulary tab (flag novel traits, don't reject), emit `box2.json` / `box3.json`, re-inject into the Card Scanner. Same schema as box1.json.
- Card codes (e.g. 2PER07/26) are the stable ids; optional for volunteers, backfilled during verification. See the variant convention below.
- **Duplicate card names within a deck are legitimate** — a deck can contain two copies (e.g. Big Helmet ×2 in Rebner, codes 2REB21/22 and 2REB22/22). Give the second card's `id` a `-2` suffix and keep both rows; do NOT deduplicate.

### Card number and variant (duplicate handling)

Column A of the sheet carries the printed card number and encodes duplicate status.
Contributors enter the number exactly as printed, e.g. `2PER14/26†`.

```
^(\d)([A-Z]+)(\d+)([A-Z]?)/(\d+)\s*(.)?$
   box  set    num  face  total  marker   (face = optional A/B letter on double-sided cards, e.g. 2KHA01A/22)
```

| marker | codepoint | `variant` | meaning |
|---|---|---|---|
| *(none)* | — | `original` | new in this box |
| `•` | U+2022 | `reprint` | gameplay-identical to the Box 1 card |
| `†` | U+2020 | `updated` | new traits or errata |
| anything else | — | **hard fail** | build stops |

`build_box2_from_sheet.py` emits `variant` and `card_number` onto every record.

**The hard fail is not optional and is not a comment on contributor care.** Sheets
autocorrect, mobile keyboards and paste from other sources silently substitute `·`
(U+00B7) or `∙` (U+2219) for `•` with no visible change to the typist. A silent fallback
to `original` is the one failure that hides itself: a `†` card would look brand new and
the resolver would never fire on it. All bad markers are collected and reported together
with their codepoints, so a single run fixes every cell.

A **blank** card number is not "no marker", it is `unclassified`. Treating it as
`original` would reintroduce the same silent failure through another door.

#### The four validation checks

1. **(gate)** Every `•`/`†` row must resolve to an existing Box 1 card, joined on `slug(name)`.
2. **(report)** Reverse check, the more valuable one: any **unmarked** Box 2 card whose name matches a Box 1 `id` is a missed transcription, which silently double-counts traits in a combined market with nothing visibly wrong on screen. Restricted to `deck == Common`: only market cards are reprinted across boxes, while captain decks legitimately reuse names (Georgiou's "Hostile Contact", Soval's "Energy Drain"). Flagging those every build trains people to ignore the check.
3. **(report)** For every `•` row, diff the trait fields against the Box 1 record. They are identical by definition, so any difference means the card should have been `†` — a change that would otherwise propagate silently to Box-1-only players. Trait **order** is not semantic; compare sorted.
4. **(gate)** Identity: a Box 2 `id` collides with a Box 1 `id` **if and only if** the card is marked. Bidirectional and sharper than 1 and 2 because it joins on `id` rather than name. An unmarked collision is a missed transcription; a marked card that does *not* collide is naming drift between the sheet's image cell and Box 1.

The script also prints the full `•`/`†` list for a human eyeball pass, turning the
classification from an assumption into something verified once.

#### Why there is no `supersedes` pointer

Box 2 stores `variant` only. Because a reprint keeps the same name, its `id` is already
identical to the Box 1 `id`, so the runtime pairing is a one-liner:

```js
const original = ALL_CARDS.find(x => x.box === 'core' && x.id === card.id);
```

A stored `supersedes` field would hold the exact string `id` already holds. Worse, it
would **bridge a name mismatch and let the two spellings drift apart indefinitely**.
Checks 1 and 4 are gates precisely so this `id` match can be trusted: they guarantee
every marked card resolves and no unmarked card collides. This is not theoretical —
it caught `Borg Spatial Trajector` vs `Trajectory`, a `•` on `Tellarites` that has no
Box 1 counterpart, and `Phlox` carrying `phlox-nx01.jpg` (id `phlox-nx01` would never
have matched `phlox`). A pointer field would have hidden the last one completely.

### Printed misprints — database vs guides

When a card's printed text is misprinted, the **card database follows the printed card**;
a strategy guide follows **McCue's prose**. Example: the core and TBG cards both read
`Xindi-Reptillian Battleship` (double-l misprint), so `box1.json`/`box2.json` use that
spelling — which also lets the id-resolver dedup the two printings. `ships.html` keeps
`Xindi-Reptilian` because that word sits in McCue's verbatim paragraph (Rule 1). When the
two diverge, **both are correct**, and the image file may exist under each spelling. The
id-resolver joins on `id`, so a printed-name correction to box1 must carry through name +
id + filename together (and the image renamed to match), or the reprint won't pair.

---

## Card Image Filename Convention

Filenames are derived from the card name as printed, with a deck prefix for crew-deck cards. The live `box1.json` (repo root) is the source of truth — in it, the `id` and `filename` fields share the same stem (`id` == `filename` minus `.jpg`). When adding cards, match an existing sibling in the same deck rather than re-deriving by hand.

### Base rule
1. Lowercase everything
2. Delete apostrophes, periods, and commas entirely — no replacement. `U.S.S.` → `uss`, `V'Ger` → `vger`, `Mek'Leth` → `mekleth`, `Worf, Son of Mogh` drops the comma
3. Strip accents to their base letter (é → e, ï → i, ñ → n, ç → c). Do NOT delete accented characters — keep the base letter so names stay readable
4. Convert spaces to single hyphens; collapse any resulting double hyphens; trim leading/trailing hyphens
5. Extension: `.jpg` (PNG only if transparency is needed)

### Deck prefix (the key rule)
6. **Common and Promo cards have no prefix:** `bird-of-prey.jpg`, `admiral-jarok.jpg`, `vger.jpg`
7. **Crew-deck cards are prefixed with the deck (captain) name:** `sisko-garak.jpg`, `picard-data.jpg`, `koloth-arne-darvin.jpg`
8. Disambiguator suffixes are **replaced by the prefix, not kept**: `Analyze (Picard)` → `picard-analyze.jpg`, never `analyze-picard.jpg` or `analyze-(picard).jpg`. Parentheses never appear in a filename.

### Captain cards double their name — this is intentional
9. Because the rule is "deck prefix + full printed name" with no carve-outs, captain cards repeat their name: `picard-jean-luc-picard.jpg`, `sisko-benjamin-sisko.jpg`, `burnham-michael-burnham.jpg`, `sela-sela.jpg`, `koloth-koloth-the-dahar-master.jpg`. This is deliberate — predictable beats pretty, and "what's on the card" is the one rule with zero exceptions. Do not "fix" the doubling.

### Examples
| Card (printed name) | Deck | Filename |
|---|---|---|
| Bird-of-Prey | Common | `bird-of-prey.jpg` |
| U.S.S. Enterprise-C | Common | `uss-enterprise-c.jpg` |
| V'Ger | Common | `vger.jpg` |
| Garak | Sisko | `sisko-garak.jpg` |
| Worf, Son of Mogh | Sisko | `sisko-worf-son-of-mogh.jpg` |
| Analyze (Picard) | Picard | `picard-analyze.jpg` |
| Jean-Luc Picard | Picard | `picard-jean-luc-picard.jpg` |
| Kang, the Dahar Master | Koloth | `koloth-kang-the-dahar-master.jpg` |

**Format:** JPG preferred, PNG if transparency needed. Full resolution — resize for web later.

**Folder structure & box-key mapping (canonical):**

Images live in numeric box folders on git: `img/box1/`, `img/box2/`, `img/box3/` (flat — filenames are globally unique across all 255 cards, so no per-suit subfolders are needed). JSON files follow the same scheme: `box1.json`, `box2.json`, `box3.json`.

The Card Scanner uses different *internal* box keys (`core`, `tbg`, `2nd`) in its filter logic and CSS. These keys are NOT disk paths. The scanner builds every image path by translating the internal key through this bridge table — it must never use the key directly as a folder name:

| Scanner key | Box | Image folder | JSON file |
|---|---|---|---|
| `core` | Captain's Chair | `img/box1/` | `box1.json` |
| `tbg` | To Boldly Go | `img/box2/` | `box2.json` |
| `2nd` | Second Contact | `img/box3/` | `box3.json` |
| `promo1` | Promo Pack 1 | `img/promo1/` | `promo1.json` |
| `promo2` | Promo Pack 2 | `img/promo2/` | `promo2.json` |

**One box = one JSON = one image folder** (decision Jul 2026, per Periodic_agent): every box, promo packs included, has its own JSON at repo root matching its image folder. Promo packs are linked to an expansion *wave*, not to a single box (Promo Pack 2 shipped alongside both To Boldly Go and Second Contact), so their data no longer lives inside an era box JSON. Promo rows keep `source: "Promo"` and carry `game_box: "Promo Pack 1"` / `"Promo Pack 2"`; the scanner assigns box membership from the source *file* (`_srcBox` stamp in `loadBoxes`), with `game_box` only as fallback for injected preview data. The earlier design (promo data inside box1.json/box2.json) was retired by `tools/split_promo_json.py`.

In the scanner code this table is the `BOX_FOLDER = { core:'box1', tbg:'box2', '2nd':'box3', promo1:'promo1', promo2:'promo2' }` constant. Image src is built as `img/<BOX_FOLDER[box]>/<filename>`. A missing image (404) falls back to a `NO IMAGE` placeholder via `onerror`, so partial image coverage is fine. Coverage as of 29 Jul 2026: `img/box2/` is complete (248/248, contributor scans, reprints and updated cards included) and `img/box3/` is complete (99/99); both at the display standard, 1170 px q80. `img/box1/` holds 248 of 250 (the 2 bot-play Directives are deliberately not done yet); uncovered cards show the placeholder. The Box 2 and Box 3 scans came as contributor image packages, imported by matching the card number printed bottom-left on each face (the unique key in the box JSON) plus title-banner and deck-folder cross-checks; the import scripts and scan-to-card mappings are parked on local disk beside each scan package (`img_table_scans/box N/import_tools/`), deliberately not in the repo.

> **Why this table exists:** the original Image-view gap was an undocumented mismatch between the scanner's internal keys (`core`/`tbg`/`2nd`) and the on-disk folders (`box1`/`box2`/`box3`). Documenting the bridge — not just the path — is what prevents a future instance from reintroducing it. If you add a box, add its row here AND to `BOX_FOLDER` in the scanner in the same change.

> **id / filename invariant:** both fields must always share the same stem. If one is corrected, regenerate the other in the same pass. Anything that keys off `id` then stays aligned with the image filename.

---

---

## Image Extraction Notes

### Promo / CDN-only guides — images must be user-downloaded (learned Jul 2026, Promo Pack 2)

Some BGG threads embed card images ONLY as `cf.geekdo-images.com` CDN URLs (no base64 in the SingleFile HTML). The Promo Pack 2 thread was one of these. For these:

- **The sandbox CANNOT download the images.** BGG's CDN returns `403 Forbidden` to server-side/sandboxed fetches. It serves normally from a real browser/OS network. So Claude generates a `download_[guide]_images.py` script, Periodic_agent runs it locally, and uploads the resulting files. Claude then pushes them to the repo. There is no way around the 403 from inside the session.
- **The HTML usually carries only the `__medium` (500x500) variant.** To get higher resolution, the download script should try resolution variants largest-first per image (`__original` -> `__large` -> `__medium`) and keep the first that resolves. Do not assume `__medium` is the best available.
- **BGG "png" cards often arrive as palette-mode PNG data with a `.jpg` extension.** Before pushing, convert them to real JPEG (`Image.open(f).convert('RGB').save(out,'JPEG',quality=92)`) so the file content matches the `.jpg` name the guide/JSON expect. Keep the convention filenames (promo cards: no deck prefix).
- **Promo images live in their own folder** per the box-key table: Promo Pack 1 -> `img/promo1/`, Promo Pack 2 -> `img/promo2/`. Data still lives in the era's box JSON (`box1.json` / `box2.json`), images do not.
- Once uploaded, switch the guide's `<img src>` from the CDN URL to the local `img/promo2/<name>.jpg` path so the site self-hosts.

### BGG SingleFile HTML — image formats encountered:
1. **CSS `--sf-img-N` variables with CDN `content=""` URLs** (Shran guide)
   → Extract URLs → run `download_images.py` → upload → embed with site naming
2. **Base64 WebP in `src=""` attribute** (TBG Locations guide)
   → Extract directly from HTML with Python/base64 (build_guide.py handles quoted and unquoted `src=`)
3. **CDN-only fallback** (some images only have `content=` URL, no base64)
   → See the Promo / CDN-only procedure above

### Image download script pattern
Claude generates `download_[guide]_images.py` per guide by extracting CDN URLs from the SingleFile HTML. Script uses stdlib only (`urllib.request`), no deps. Alt text from the SingleFile HTML is used to name files meaningfully (e.g. `burnham_board_basic.jpg`).

### Known image sets
- **Shran:** `shran_board_basic`, `shran_board_advanced`, `shran_available_1/2/3`, `shran_reinforcement`, `shran_development_1/2`
- **Burnham:** `burnham_board_basic`, `burnham_board_advanced`, `burnham_1` through `burnham_7`
- **TBG Locations:** 6 embedded WebP + 3 CDN (Cold Station 12, Tanuga IV, Tellar Prime)

---

---

## Session Delta — 24 Aug 2026 (Semantic layer)

### What shipped

The card database is published as linked data, and the Pages site now carries it:
every card is an addressable subject with its own page, the Card Scanner emits
machine-readable statements for what it renders, and the guides say which card
each section is about. Nothing about the card JSONs changed — they stay the editing
surface, and everything below is generated from them.

Mapped onto **TCG Schema Core** (`https://www.tcg-schema.org/core.ttl` — the
vocabulary behind the CardForge card creator; 54 classes, 182 properties).

### One root

Vocabulary and instances are both fragments of **`https://tcg-schema.org/stcc`**:

| Fragment | Example |
|---|---|
| vocabulary term (CamelCase) | `#SuitPerson`, `#TraitCardassian`, `#OpActivation` |
| vocabulary property | `#suit`, `#victoryPoints`, `#printingVariant` |
| instance (prefixed) | `#card-sisko-garak`, `#printing-core-sisko-garak`, `#set-core`, `#pool-core-sisko`, `#art-core-sisko-garak`, `#game-stcc` |

**No IRI names the host that serves the files**, so moving the site never rewrites
the graph. That is checked, not just intended: `test_ontology.py` fails if any IRI
in the vocabulary or graph mentions a serving host.

The split that makes this work: **identity is rooted, location is relative.**
Artwork has a rooted identity (`#art-core-phlox`) and a *relative* `schema:contentUrl`
(`../img/box1/phlox.jpg`) which resolves wherever the files are served — both
consumers, `data/cards.jsonld` and `card/<id>.html`, sit one directory deep. For the
same reason card pages use a self-referential relative `<link rel="canonical">`, and
`sitemap.xml` takes its base from the entries already in it: a sitemap may only list
URLs on the host that serves it, and a canonical pointing at a host that does not
serve the page yet would deindex the site.

The CamelCase/prefixed split is what tells vocabulary from instance in one flat
fragment space. `#game` had to become `#game-stcc` for that rule to hold — the gate
caught it.

### Files

| Path | Role |
|---|---|
| `data/stcc-ontology.ttl` | The vocabulary: 14 classes, 22 properties, 107 terms in 6 term sets. GENERATED. |
| `data/cards.jsonld` | 610 printings as `tcg:Card` + `tcg:CardPrinting`, ~20k triples. GENERATED. |
| `data/stcc-context.jsonld` | JSON-LD context. **Hand-maintained** — the contract the generator writes against. |
| `card/<id>.html` | 556 card pages: microdata + a per-card JSON-LD block. GENERATED. |
| `card/index.html`, `index.html` | Card index and the dataset hub (the site's front door). GENERATED. |
| `dataset.html` | Redirect stub: the hub was published under this path before the split. |
| `tools/build_ontology.py` | Generates the ttl + jsonld. `--check`, `--report`. |
| `tools/build_card_pages.py` | Generates the pages and folds them into `sitemap.xml`. `--check`. |
| `tools/test_ontology.py` | RDF gate, 18 assertions. Needs rdflib. |

`css/stcc.css` carries the card-page block (the 556 pages have no inline CSS, so they
stay diffable and restyling stays a one-file change); the guide-era rules in it are dead
weight kept only because trimming them risks the card pages. `robots.txt` publishes the
data rather than hiding it — a dataset site that blocks its own files would be a
contradiction.

### Modelling rules (the ones that will bite)

- **A JSON record is a printing, not a card.** Records sharing an `id` are printings
  of one `tcg:Card`, exactly as `resolveCards()` groups them. Card-level facts are the
  **resolved view** (updated printing if any, else earliest box) so the graph says what
  the scanner shows; `stcc:resolvedFrom` names the printing it came from.
- **Divergence is emitted, never flattened.** A printing whose printed facts differ from
  the resolved view carries its own `stcc:printed*` triples (5 today: 4 pre-errata faces
  plus one reprint whose transcription differs by a word). Identical reprints stay silent.
- **`stcc:printed*` are deliberately NOT subproperties of `tcg:cardType`/`cardSubtype`.**
  Those carry `rdfs:domain tcg:Card`, so a reasoner would infer every printing is itself
  a card. The card-level properties ARE subproperties, because there the domain holds.
  `test_ontology.py --core` checks this for every subproperty.
- **Comparison of printings sorts traits and icons.** Printed order is not semantic (the
  same point the reprint check makes); comparing in printed order reported 10 printings
  as divergent purely from list order.
- **Icons keep the one-node-per-printed-icon model**, in the JSON, the graph and the
  scanner's microdata alike. RDF triples are a set, so a shared term would collapse a
  card's two Military Skills into one.
- **Card pages link to guide passages and never quote them.** `data/strategy-index.json`
  is kept as a STATIC input: its generator reads guide HTML, which lives in the compendium
  repo now, so `build_strategy_index.py` cannot be run here. Regenerate it there and copy
  the two JSONs across. Card entries live under the `"cards"` key — reading `"guides"`
  yields no links at all and nothing looks wrong, which is exactly what shipped first.
- Closed vocabularies hard-fail on an unknown value; traits are open and only warn.
- `stcc:jsonKey` / `stcc:jsonValue` record the exact key and string each term comes from
  in the card JSON, so the JSON↔RDF mapping is machine-readable rather than prose here.

### Regeneration order

Card data changed? Run in this order — pages are built from the graph, so the graph
goes first:

```
python3 tools/build_ontology.py --report
python3 tools/build_card_pages.py
python3 tools/test_ontology.py --core core.ttl   # curl -o core.ttl https://www.tcg-schema.org/core.ttl
```

`--check` on both generators exits 1 when the committed output differs from a fresh
build, so they can be wired into `.github/workflows/` the way the strategy index is.
Without `--core` the two core-alignment assertions print SKIP rather than passing
silently.

### Notes

- `data/stcc-context.jsonld` does **not** lift `box1.json`..`promo2.json` directly: those
  carry display strings (`"Mind Control"`), not term IRIs, and JSON-LD cannot rewrite
  values. `cards.jsonld` is the linked-data view of the same data.
- Card pages **link** to guide passages and never quote them: `data/strategy-index.json`
  holds McCue's paragraphs verbatim, and his text belongs in his guides.
- `card/` is ~4.8 MB of HTML. Most of it is the per-page JSON-LD block, which is what
  makes each page self-describing; the img library is 341 MB for scale.
- The compendium and the Card Scanner were removed from this repo on 24 Aug 2026; the
  scanner's microdata patch and the guide-anchor patch went with them. Both are in git
  history (`9375a4d`) if the compendium repo wants them.
- `.github/workflows/strategy-index.yml` was removed with the guides. It rebuilt the index
  from guide HTML, so leaving it here would have rebuilt an EMPTY index on the next push
  and committed it over the data.
