# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

The **ST:CC Card Dataset**: every card in Star Trek: Captain's Chair published as linked
data, mapped onto [TCG Schema Core](https://www.tcg-schema.org/core.ttl). Served by GitHub
Pages at `https://tcg-schema.github.io/stcc-strategy/` from `tcg-schema/stcc-strategy`.

The five card JSONs at the repo root (`box1.json`..`promo2.json`) are the **only** thing
edited by hand. The vocabulary, the graph, the 556 card pages, the hub and the sitemap are
all generated from them — never hand-edit those.

Matthew McCue's strategy guides and the Card Scanner used to live here and were removed on
24 Aug 2026; they are the **ST:CC Strategy Compendium** at
`https://periodic-agent.github.io/stcc-strategy/`. Anything about guide builds, canonical
text, the scanner or the shared design system belongs there, not here. Both are in this
repo's git history up to `9375a4d` if something needs recovering.

`WORKFLOW.md` is the single source of operational truth and is more detailed than this file.

## Environment

Python 3.8 and node 16. The generators are stdlib-only; `tools/test_ontology.py` needs
**rdflib** (present). `PIL` and `openpyxl` are **not** installed, so the image tools and the
sheet/workbook tools need them installed first.

## Commands

```bash
# Regenerate, in this order — the pages are built from the graph
python3 tools/build_ontology.py --report     # data/stcc-ontology.ttl + data/cards.jsonld
python3 tools/build_card_pages.py            # card/, card/index.html, index.html, sitemap.xml

# Gates — run before presenting anything for push
python3 tools/build_ontology.py --check      # committed output vs a fresh build
python3 tools/build_card_pages.py --check
python3 tools/test_ontology.py --core core.ttl   # curl -o core.ttl https://www.tcg-schema.org/core.ttl

# Card data from the community sheet (needs openpyxl)
python3 tools/build_box2_from_sheet.py sheet.xlsx "TBG (Box 2)" "To Boldly Go" --box1 box1.json -o box2.json
python3 tools/build_text_from_sheet.py --sheet stcc-card-database.xlsx [--dry-run]
```

## Architecture

**One root.** Vocabulary and instances are both fragments of `https://tcg-schema.org/stcc`:
terms are CamelCase (`#SuitPerson`, `#victoryPoints`), instances are prefixed
(`#card-sisko-garak`, `#printing-core-sisko-garak`, `#set-core`, `#pool-core-sisko`,
`#art-core-phlox`, `#game-stcc`). That split is what tells vocabulary from instance in one
flat fragment space, and it is enforced by the gate. **No IRI names a serving host** —
`test_ontology.py` fails if one does.

**Identity is rooted, location is relative.** Artwork has a rooted identity (`#art-core-phlox`)
and a relative `schema:contentUrl` (`../img/box1/phlox.jpg`) that resolves wherever the site
is served; card pages use relative self-referential canonicals. `sitemap.xml` is the
exception and carries `SITE_HOST`, because a sitemap may only list URLs on the host serving it.

**A record is a printing, not a card.** Records sharing an `id` are printings of one
`tcg:Card` whose card-level facts are the *resolved view* — the updated printing if any,
else the earliest box. A printing whose printed face differs keeps its own `stcc:printed*`
statements. `stcc:printed*` are deliberately **not** subproperties of `tcg:cardType`/
`cardSubtype`, whose `rdfs:domain` is `tcg:Card`: a reasoner would otherwise infer that
every printing is a card. The card-level properties are subproperties, where the domain holds.

**Each printed icon is its own node.** RDF triples are a set, so a shared term would collapse
a card's two Military Skills into one — the same reason the JSON has no `count` field.

## Rules that bite

1. **Regeneration order**: `build_ontology.py` → `build_card_pages.py` → gates.
2. **Closed vocabularies hard-fail**; traits are open and only warn. An unknown suit,
   variant, icon or operation kind stops the build — a silent fallback is the one failure
   that hides itself.
3. **`data/strategy-index.json` is a static input here.** Its generator reads guide HTML,
   which lives in the compendium repo. Card entries are under the **`cards`** key —
   reading `guides` yields no links and looks fine, which is how it shipped broken once.
4. **`id` == `filename` stem, always.** Correct one and regenerate the other in the same pass.
5. **Printed misprints follow the card**: `Xindi-Reptillian Battleship` keeps its two Ls.
   Reprints leave `filename` blank so the resolver serves the original's scan.
6. **Pushing**: the remote is `git@github.com:tcg-schema/stcc-strategy.git` over SSH, but the
   local git identity is a real name and this project's anonymity rule covers commit metadata.
   Commit as `-c user.name=periodic-agent -c user.email=periodic-agent@users.noreply.github.com`.
   Push only after explicit approval.
