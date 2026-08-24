# tools/ — dataset tooling

The card JSONs at the repo root are the editing surface. Everything the site serves is
generated from them by the scripts here, and **generators ship with their output**: a
push of generated files without its generator is incomplete.

Python 3, stdlib only unless noted.

## The semantic layer

| Script | Purpose |
|---|---|
| `build_ontology.py` | Maps the five card JSONs onto TCG Schema Core → `data/stcc-ontology.ttl` (vocabulary, term sets derived from the data so they cannot drift) + `data/cards.jsonld` (556 cards, 610 printings). `--check` exits 1 if the committed output is stale; `--report` prints coverage and divergence. |
| `build_card_pages.py` | Reads the graph → `card/<id>.html` (556 microdata pages), `card/index.html`, `index.html` (the hub), `dataset.html` (redirect stub) and `sitemap.xml`. Page content comes from the same builder as the graph, so a page cannot describe a card differently. `--check`. |
| `test_ontology.py` | Gate. Parses both files as RDF and asserts the graph says what the vocabulary claims — 18 assertions including domain/range conformance, one-node-per-icon, and that no IRI names a serving host. `--core core.ttl` adds alignment checks against TCG Schema Core. **Requires rdflib.** |

## Card data

| Script | Purpose |
|---|---|
| `build_box2_from_sheet.py` | Rebuilds a box JSON from the community sheet. Runs the four variant checks; two are gates. Fix the **sheet**, never the JSON. Needs openpyxl. |
| `build_text_from_sheet.py` | Imports card text (operation strips) from the sheet into every box JSON. Read-only on the sheet. Needs openpyxl. |
| `build_text_workbook.py` / `build_workbook.py` | Generate the community workbook from the JSONs. Needs openpyxl. |
| `carddata.py` / `carddata2.py` | Structured record of Box 2/3 cards as read from card faces; raw material for the JSONs, independent of the sheet. |
| `fill_image_filenames.py` | Fills `filename` from scans on disk, keyed on the `id` == filename-stem invariant. |
| `split_promo_json.py` | Historical: split the promo rows out of the era box JSONs into `promo1.json` / `promo2.json`. |
| `extract_strip_colors.py` | Samples operation-strip colours from card scans → `data/strip-palette.json`. |

## Images

| Script | Purpose |
|---|---|
| `shrink_card_images.py` | The filter step for every image import: max width 1170 px, JPEG q80, progressive. Skips anything already within the standard. Needs PIL. |
| `make_montage.py` | Tiles card images into labelled grids so a session can read several card faces per image view. Needs PIL. |
| `../extract_cards.py` | Delineates and deskews individual cards out of a multi-card scan. Needs PIL. |

## Publishing

| Script | Purpose |
|---|---|
| `push_gate.py` | Standalone anonymity gate: scans a file, a directory or a repo's whole git history against a denylist. Stdlib only; vendor it anywhere. |
| `../push_to_github.py` | The HTTPS/PAT push pipeline with the fail-closed PII gate. **Hardcoded to `periodic-agent/stcc-strategy`** — this repo now pushes over SSH to `tcg-schema/stcc-strategy`, so the script is kept for the gate it carries and for the compendium repo. See WORKFLOW.md. |

## Kept but not runnable here

`build_strategy_index.py` + `strategy_index_config.json` generate
`data/strategy-index.json` / `strategy-cards.json`, which the card pages use to link out
to the guide sections that discuss each card. The generator reads **guide HTML**, which
lives in the compendium repo now — run it there and copy the two JSONs across. It ships
here because its output does.
