# ST:CC Card Dataset

Every card in **Star Trek: Captain's Chair** (WizKids) as linked data, mapped onto
[TCG Schema Core](https://www.tcg-schema.org/core.ttl).

Live at **https://tcg-schema.github.io/stcc-strategy/**

## The root

Vocabulary and data share one root, **`https://tcg-schema.org/stcc`**. Vocabulary terms
are CamelCase fragments, instances are prefixed fragments, and **no IRI names the host
that serves the files** — so the graph survives the site moving.

| IRI | |
|---|---|
| `…/stcc#SuitPerson`, `…/stcc#TraitCardassian` | vocabulary terms |
| `…/stcc#suit`, `…/stcc#victoryPoints` | vocabulary properties |
| `…/stcc#card-sisko-garak` | a card |
| `…/stcc#printing-core-sisko-garak` | one printing of it |
| `…/stcc#set-core`, `…/stcc#pool-core-sisko` | a set, a card pool |

## Files

| URL | Contents |
|---|---|
| `data/stcc-ontology.ttl` | The vocabulary: 14 classes, 22 properties, 107 terms in 6 term sets (Turtle) |
| `data/cards.jsonld` | The graph: 556 cards, 610 printings, ~20k triples (JSON-LD) |
| `data/stcc-context.jsonld` | The JSON-LD context the graph is written against |
| `card/<id>.html` | One page per card, carrying the same statements as microdata |
| `box1.json` … `promo2.json` | The card database itself — the editing surface everything else is built from |
| `img/box1/<card>.jpg` | Card images, one file per card (`box1`..`box3`, `promo1`, `promo2`) |

**Filenames are permanent.** Once a card image ships, its URL never changes.

## Using it

The data is a community resource — link it, query it, build on it.

```bash
curl -s https://tcg-schema.github.io/stcc-strategy/data/cards.jsonld | jq \
  '.["@graph"][] | select(.suit == "stcc:SuitPerson") | .name'
```

A record in the card JSONs is a **printing**, not a card: printings sharing an `id` are
printings of one `tcg:Card`, whose card-level facts are the resolved view (the updated
printing if there is one, else the earliest box). A printing whose printed face differs
keeps its own `stcc:printed*` statements, so errata are readable at both levels.

## Regenerating

The JSONs are the only thing edited by hand. Everything else is generated:

```bash
python3 tools/build_ontology.py --report        # ttl + jsonld
python3 tools/build_card_pages.py               # card pages, index, sitemap
python3 tools/test_ontology.py --core core.ttl  # gate (needs rdflib)
```

## The strategy guides

Matthew McCue's strategy guides and the Card Scanner are the **ST:CC Strategy
Compendium**: https://periodic-agent.github.io/stcc-strategy/ — each card page here links
to the guide sections that discuss it.

Card images © WizKids. Card data compiled by Periodic_agent with the ST:CC community.
