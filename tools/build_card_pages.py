#!/usr/bin/env python3
"""build_card_pages.py -- one dereferenceable HTML page per card, plus the dataset hub.

Every card IRI in the graph (https://tcg-schema.org/stcc#card-<id>) gets a page at
card/<id>.html that carries the same statements as RDF microdata, so the published
site IS the dataset rather than merely linking to it. Emits:

    card/<id>.html      556 card pages, microdata-typed, with a per-card JSON-LD block
    card/index.html     A-Z index of every card page
    dataset.html        the hub: what the vocabulary is, how the IRIs are shaped,
                        where the machine-readable files are
    sitemap.xml         card pages folded in (existing entries are preserved)

Design notes:

- **The page renders what the graph says, from the same builder.** Page content comes
  from build_ontology.build_cards(), not from a second walk over the JSONs, so a page
  cannot describe a card differently from cards.jsonld.
- **Guide passages are LINKED, never quoted.** data/strategy-index.json carries McCue's
  paragraphs verbatim, and Rule 1 keeps his text in his guides; a card page deep-links
  into the guide instead of republishing the prose on a new page.
- **Microdata, not RDFa.** It is what the sibling CardForge project emits for the same
  vocabulary, and itemprop/itemid express everything needed here.
- Images use relative paths so the pages render wherever the site is served; the RDF
  keeps the canonical absolute contentUrl. Those are different jobs.

Usage:
  python3 tools/build_card_pages.py [--repo .] [--check]

Stdlib only.
"""
import argparse
import html
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_ontology as bo  # noqa: E402

CORE = bo.CORE
VOCAB = bo.VOCAB
ROOT = bo.ROOT
SITE = bo.SITE

GOAT = ('<script data-goatcounter="https://stcc-compendium.goatcounter.com/count"\n'
        '        async src="//gc.zgo.at/count.js"></script>')
# The strategy guides live in the compendium repo, not here. Card pages link out to
# them absolutely; data/strategy-index.json is kept as a static input because its
# generator cannot run without the guide HTML.
COMPENDIUM = "https://periodic-agent.github.io/stcc-strategy/"
# Where this dataset is served. Sitemap <loc> must name the serving host, which the
# semantic root deliberately does not.
SITE_HOST = "https://tcg-schema.github.io/stcc-strategy/"
THEME = {"core": "", "tbg": "theme-tbg", "2nd": "theme-sc",
         "promo1": "", "promo2": "theme-tbg"}
BOX_LABEL = dict((b[0], b[2]) for b in bo.BOXES)
BOX_FOLDER = dict((b[0], b[3]) for b in bo.BOXES)


def e(s):
    return html.escape(str(s), quote=True)


def term_label(term):
    """'stcc:TraitMindControl' -> the printed string, via the ontology's jsonValue."""
    return TERM_LABELS.get(term, term.split(":")[-1])


TERM_LABELS = {}


def load_term_labels(ttl):
    for local, label in re.findall(r"^stcc:(\w+) a [^;]+; rdfs:label \"([^\"]+)\"", ttl, re.M):
        TERM_LABELS["stcc:" + local] = label


def prop(name, ns=VOCAB):
    return ns + name


def chip(term, cls="chip"):
    return ('<a class="%s" href="%s">%s</a>'
            % (cls, e(VOCAB.rstrip("#") + "#" + term.split(":")[-1]), e(term_label(term))))


def card_page(card, printings, guides, ctx_url):
    cid = card["id"].split("#card-", 1)[1]
    name = card["name"]
    box = printings[0]["id"].split("#printing-", 1)[1].rsplit("-" + cid, 1)[0]
    theme = THEME.get(box, "")

    # image: the resolved printing's art if it has any, else any printing's
    img = None
    for p in printings:
        art = p.get("printingArtwork")
        if art:
            img = art["contentUrl"]
            break

    P = lambda n: e(prop(n))            # noqa: E731  stcc: property IRI
    C = lambda n: e(prop(n, CORE))      # noqa: E731  tcg: property IRI

    out = []
    a = out.append
    a("<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">")
    a('<meta name="viewport" content="width=device-width,initial-scale=1">')
    a("<title>%s &mdash; ST:CC Card</title>" % e(name))
    desc = "%s: %s card from %s in Star Trek: Captain's Chair." % (
        name, term_label(card["suit"]).lower(), BOX_LABEL[box])
    a('<meta name="description" content="%s">' % e(desc))
    a('<link rel="canonical" href="%s.html">' % e(cid))
    a('<link rel="alternate" type="application/ld+json" href="../data/cards.jsonld" '
      'title="Card graph (JSON-LD)">')
    a('<link rel="alternate" type="text/turtle" href="../data/stcc-ontology.ttl" '
      'title="ST:CC vocabulary (Turtle)">')
    a('<link rel="icon" href="../icons8-star-trek-symbol-96.png">')
    a('<link rel="stylesheet" href="../css/stcc.css?v=1">')
    a('<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@600;700&'
      'family=Exo+2:wght@300;400;600&display=swap" rel="stylesheet">')
    a("</head>")
    a('<body%s>' % ((' class="%s"' % theme) if theme else ""))
    a('<div class="nav-bar"><a href="../index.html">&larr; ST:CC Dataset</a> '
      '&middot; <a href="index.html">Card index</a> &middot; '
      '<a href="%sindex.html">Strategy Compendium</a></div>' % e(COMPENDIUM))
    a('<main class="cardpage">')
    a('<article itemscope itemtype="%s" itemid="%s">' % (e(CORE + "Card"), e(card["id"])))
    a('<h1 itemprop="%s">%s</h1>' % (e("https://schema.org/name"), e(name)))
    a('<div class="cp-sub">%s &middot; %s</div>'
      % (e(term_label(card["suit"])), e(BOX_LABEL[box])))
    a('<div class="cp-grid">')

    a('<div class="cp-art">')
    if img:
        a('<img src="%s" alt="%s" loading="lazy">' % (e(img), e(name)))
    else:
        a('<div class="pr">No card image yet.</div>')
    a("</div>")

    a('<div><dl class="cp-facts">')
    a('<dt>Suit</dt><dd>%s<link itemprop="%s" href="%s"></dd>'
      % (chip(card["suit"]), P("suit"), e(VOCAB + card["suit"].split(":")[1])))

    for key, label, propname in (("speciesTrait", "Species traits", "speciesTrait"),
                                 ("regularTrait", "Traits", "regularTrait"),
                                 ("otherTrait", "Other traits", "otherTrait")):
        if card.get(key):
            a("<dt>%s</dt><dd>" % label)
            for t in card[key]:
                a(chip(t))
                a('<link itemprop="%s" href="%s">' % (P(propname), e(VOCAB + t.split(":")[1])))
            a("</dd>")

    if card.get("hasIcon"):
        a("<dt>Icons</dt><dd>")
        for icon in card["hasIcon"]:
            kind = "Skill" if icon["type"].endswith("SkillIcon") else "Focus"
            a('<span class="chip" itemprop="%s" itemscope itemtype="%s" itemid="%s">'
              '%s %s<link itemprop="%s" href="%s"></span>'
              % (P("hasIcon"), e(VOCAB + kind + "Icon"), e(icon["id"]),
                 e(term_label(icon["specialty"])), kind,
                 P("specialty"), e(VOCAB + icon["specialty"].split(":")[1])))
        a("</dd>")

    if "victoryPoints" in card:
        a('<dt>Victory points</dt><dd itemprop="%s">%s</dd>'
          % (P("victoryPoints"), e(card["victoryPoints"])))
    if card.get("startingPosition"):
        a('<dt>Starts in</dt><dd>%s<link itemprop="%s" href="%s"></dd>'
          % (chip(card["startingPosition"]), P("startingPosition"),
             e(VOCAB + card["startingPosition"].split(":")[1])))
    if card.get("awayTeamSize"):
        a('<dt>Away team</dt><dd itemprop="%s">%s</dd>'
          % (P("awayTeamSize"), e(card["awayTeamSize"])))
    a("</dl></div></div>")

    if card.get("hasAbility"):
        a("<h2>Card text</h2>")
        for op in card["hasAbility"]:
            a('<div class="op" itemprop="%s" itemscope itemtype="%s" itemid="%s">'
              % (C("hasAbility"), e(CORE + "Ability"), e(op["id"])))
            a('<div class="op-kind">%s<link itemprop="%s" href="%s"></div>'
              % (e(term_label(op["abilityType"]).upper()), C("abilityType"),
                 e(VOCAB + op["abilityType"].split(":")[1])))
            if op.get("qualifier"):
                a('<div class="op-qual" itemprop="%s">%s</div>'
                  % (P("qualifier"), e(op["qualifier"])))
            a('<div itemprop="%s">%s</div>' % (C("abilityText"), e(op["abilityText"])))
            a('<meta itemprop="%s" content="%s">' % (C("orderIndex"), e(op["orderIndex"])))
            a("</div>")

    a("<h2>Printings</h2>")
    for p in printings:
        pbox = p["id"].split("#printing-", 1)[1].rsplit("-" + cid, 1)[0]
        a('<div class="pr" itemprop="%s" itemscope itemtype="%s" itemid="%s">'
          % (C("hasPrinting"), e(CORE + "CardPrinting"), e(p["id"])))
        bits = [e(BOX_LABEL[pbox])]
        if p.get("collectorNumber"):
            bits.append('<code itemprop="%s">%s</code>'
                        % (C("collectorNumber"), e(p["collectorNumber"])))
        if p.get("printingVariant"):
            bits.append(e(term_label(p["printingVariant"])))
            bits.append('<link itemprop="%s" href="%s">'
                        % (P("printingVariant"), e(VOCAB + p["printingVariant"].split(":")[1])))
        a(" &middot; ".join(bits))
        a('<link itemprop="%s" href="%s">' % (C("inSet"), e(p["inSet"])))
        if p.get("printingArtwork"):
            a('<link itemprop="%s" href="%s">'
              % (C("printingArtwork"), e(p["printingArtwork"]["contentUrl"])))
        a("</div>")

    if guides:
        a("<h2>Discussed in</h2>")
        a('<div class="pr">Strategy guides by Matthew McCue that cover this card, in the '
          '<a href="%s">ST:CC Strategy Compendium</a>:</div>' % e(COMPENDIUM))
        for g in guides:
            href = (COMPENDIUM + g["guide"] + ("#" + g["anchor"] if g.get("anchor") else ""))
            a('<div class="pr">&rarr; <a itemprop="%s" href="%s">%s</a>%s</div>'
              % (C("rulesReference"), e(href), e(g["guide"].replace(".html", "")),
                 (" &mdash; " + e(g["heading"])) if g.get("heading") else ""))

    a('<div class="cp-iri">This card is <code>%s</code> in the '
      '<a href="../index.html">ST:CC dataset</a>.</div>' % e(card["id"]))
    a("</article>")
    a("</main>")
    a('<div class="nav-bar"><a href="../index.html">&larr; ST:CC Dataset</a></div>')
    a("<footer>Card images &copy; WizKids.</footer>")

    subgraph = {"@context": ctx_url, "@graph": [card] + printings}
    a('<script type="application/ld+json">%s</script>'
      % json.dumps(subgraph, ensure_ascii=False))
    a(GOAT)
    a("</body>\n</html>")
    return "\n".join(out) + "\n"


def index_page(cards):
    out = ["<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">",
           '<meta name="viewport" content="width=device-width,initial-scale=1">',
           "<title>Card Index &mdash; ST:CC</title>",
           '<meta name="description" content="Every Star Trek: Captain\'s Chair card, '
           'one page per card, with machine-readable data.">',
           '<link rel="icon" href="../icons8-star-trek-symbol-96.png">',
           '<link rel="stylesheet" href="../css/stcc.css?v=1">',
           '<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@600;700&'
           'family=Exo+2:wght@300;400;600&display=swap" rel="stylesheet">',
           "</head>\n<body>",
           '<div class="nav-bar"><a href="../index.html">&larr; ST:CC Dataset</a> '
           '&middot; <a href="%sindex.html">Strategy Compendium</a></div>' % COMPENDIUM,
           '<main class="idx"><h1>Card Index</h1>',
           '<p>One page per card, each carrying its own machine-readable description.</p>',
           "<ul>"]
    for card in sorted(cards, key=lambda c: c["name"].lower()):
        cid = card["id"].split("#card-", 1)[1]
        out.append('<li><a href="%s.html">%s</a></li>' % (e(cid), e(card["name"])))
    out += ["</ul></main>",
            '<div class="nav-bar"><a href="../index.html">&larr; ST:CC Dataset</a></div>',
            "<footer>Card images &copy; WizKids.</footer>", GOAT, "</body>\n</html>"]
    return "\n".join(out) + "\n"


def dataset_page(stats, ctx_url):
    rows = "".join(
        "<tr><td>%s</td><td>%s</td></tr>" % (e(k), e(v)) for k, v in stats)
    ld = {"@context": "https://schema.org/", "@type": "Dataset",
          "name": "Star Trek: Captain's Chair card data",
          "description": "Every card in Star Trek: Captain's Chair as linked data, "
                         "mapped onto the TCG Schema vocabulary.",
          "url": SITE_HOST,
          "license": "https://creativecommons.org/licenses/by/4.0/",
          "creator": {"@type": "Person", "name": "Periodic_agent"},
          "distribution": [
              {"@type": "DataDownload", "encodingFormat": "application/ld+json",
               "contentUrl": SITE + "data/cards.jsonld"},
              {"@type": "DataDownload", "encodingFormat": "text/turtle",
               "contentUrl": SITE + "data/stcc-ontology.ttl"}]}
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ST:CC Card Dataset</title>
<meta name="description" content="The Star Trek: Captain's Chair card database as linked data: vocabulary, card graph, and one dereferenceable page per card.">
<link rel="canonical" href="index.html">
<link rel="alternate" type="application/ld+json" href="data/cards.jsonld" title="Card graph (JSON-LD)">
<link rel="alternate" type="text/turtle" href="data/stcc-ontology.ttl" title="ST:CC vocabulary (Turtle)">
<link rel="icon" href="icons8-star-trek-symbol-96.png">
<link rel="stylesheet" href="css/stcc.css?v=1">
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@600;700&family=Exo+2:wght@300;400;600&display=swap" rel="stylesheet">
</head>
<body>
<div class="nav-bar"><a href="card/index.html">Card index</a> &middot; <a href="{compendium}index.html">Strategy Compendium</a></div>
<main class="ds">
<h1>ST:CC Card Dataset</h1>
<p>Every card in <em>Star Trek: Captain's Chair</em> is published as linked data, mapped onto
<a href="https://www.tcg-schema.org/core.ttl">TCG Schema Core</a> &mdash; the same vocabulary the
CardForge card creator emits. The card JSONs stay the editing surface; this is a generated view
of them, so the two cannot disagree.</p>

<h2>The root</h2>
<p>Vocabulary and data share one root, <code>{root}</code>. Terms are CamelCase fragments and
instances are prefixed fragments, so nothing in the graph names whichever host serves the files:</p>
<table>
<tr><td><code>{root}#SuitPerson</code></td><td>a vocabulary term</td></tr>
<tr><td><code>{root}#victoryPoints</code></td><td>a vocabulary property</td></tr>
<tr><td><code>{root}#card-sisko-garak</code></td><td>a card</td></tr>
<tr><td><code>{root}#printing-core-sisko-garak</code></td><td>one printing of it</td></tr>
<tr><td><code>{root}#set-core</code>, <code>#pool-core-sisko</code></td><td>set, card pool</td></tr>
</table>

<h2>Files</h2>
<div class="files">
<a href="data/stcc-ontology.ttl"><strong>stcc-ontology.ttl</strong> &mdash; the vocabulary: classes, properties, and every closed term set (Turtle)</a>
<a href="data/cards.jsonld"><strong>cards.jsonld</strong> &mdash; the card graph: every card and printing (JSON-LD)</a>
<a href="data/stcc-context.jsonld"><strong>stcc-context.jsonld</strong> &mdash; the JSON-LD context the graph is written against</a>
<a href="card/index.html"><strong>card/&lt;id&gt;.html</strong> &mdash; one page per card, carrying the same statements as microdata</a>
</div>

<h2>What is in it</h2>
<table>{rows}</table>

<h2>Modelling</h2>
<p>A record in the card JSONs is a <strong>printing</strong>, not a card. Printings sharing an id are
printings of one <code>tcg:Card</code>, whose card-level facts are the resolved view &mdash; the updated
printing if the card has one, else the earliest box &mdash; which is what the Card Scanner shows.
A printing whose printed face differs from that view keeps its own <code>stcc:printed*</code> statements,
so an errata'd card is readable at both levels.</p>
<p>Each printed icon is its own node rather than a term with a count: RDF triples are a set, and a
card with two Military Skills would otherwise collapse to one.</p>

<h2>Where the guides went</h2>
<p>This repository is the dataset. Matthew McCue's strategy guides live in the
<a href="{compendium}index.html">ST:CC Strategy Compendium</a>, and each card page links
to the sections that discuss it.</p>

<h2>Reuse</h2>
<p>The data is a community resource &mdash; link it, query it, build on it. Card images
&copy; WizKids. A pointer back is appreciated but not required.</p>
</main>
<div class="nav-bar"><a href="card/index.html">Card index</a></div>
<footer>Card images &copy; WizKids.</footer>
<script type="application/ld+json">{ld}</script>
{goat}
</body>
</html>
""".format(site=SITE_HOST, root=ROOT, rows=rows, ld=json.dumps(ld, ensure_ascii=False),
           goat=GOAT, compendium=COMPENDIUM)


def update_sitemap(repo, cids, write=True):
    """Build the whole sitemap. Every URL this repo serves is generated here now that
    the guides live elsewhere, so there is nothing to preserve -- and a stale guide
    entry would advertise a 404."""
    date = "2026-08-24"
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
             '  <url><loc>%s</loc><lastmod>%s</lastmod></url>' % (SITE_HOST, date),
             '  <url><loc>%scard/index.html</loc><lastmod>%s</lastmod></url>' % (SITE_HOST, date)]
    lines += ['  <url><loc>%scard/%s.html</loc><lastmod>%s</lastmod></url>' % (SITE_HOST, c, date)
              for c in sorted(cids)]
    lines.append("</urlset>")
    new = "\n".join(lines) + "\n"
    path = os.path.join(repo, "sitemap.xml")
    if write:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(new)
    return new


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    with open(os.path.join(args.repo, "data", "stcc-ontology.ttl"), encoding="utf-8") as fh:
        load_term_labels(fh.read())
    with open(os.path.join(args.repo, "data", "cards.jsonld"), encoding="utf-8") as fh:
        graph = json.load(fh)
    ctx_url = graph["@context"]
    nodes = graph["@graph"]
    cards = [n for n in nodes if n.get("type") == "tcg:Card"]
    printings = {}
    for n in nodes:
        if n.get("type") == "tcg:CardPrinting":
            printings.setdefault(n["printsCard"], []).append(n)

    try:
        with open(os.path.join(args.repo, "data", "strategy-index.json"), encoding="utf-8") as fh:
            # NOTE: card entries live under "cards"; "guides" is keyed by guide
            # filename. Reading the wrong key silently yields no links at all,
            # which is exactly what shipped the first time.
            sidx = json.load(fh).get("cards", {})
    except (FileNotFoundError, ValueError):
        sidx = {}

    outdir = os.path.join(args.repo, "card")
    if not args.check:
        os.makedirs(outdir, exist_ok=True)

    written, stale = 0, []
    cids = []
    for card in cards:
        cid = card["id"].split("#card-", 1)[1]
        cids.append(cid)
        hits = []
        for entry in sidx.get(cid, []):
            # One link per guide, and pick the hit that is actually ABOUT this card:
            # an anchor hit is exact by construction, then a heading naming the card;
            # the first hit is often a neighbouring card's paragraph that mentions it.
            candidates = entry.get("hits", [])
            hit = next((h for h in candidates if h.get("mode") == "anchor"), None)
            if hit is None:
                hit = next((h for h in candidates
                            if h.get("heading", "").lower().startswith(card["name"].lower())), None)
            if hit is None and candidates:
                hit = candidates[0]
            if hit:
                hits.append({"guide": entry["guide"], "anchor": hit.get("anchor"),
                             "heading": hit.get("heading"), "count": entry.get("count")})
        page = card_page(card, printings.get(card["id"], []), hits, ctx_url)
        path = os.path.join(outdir, cid + ".html")
        if args.check:
            try:
                with open(path, encoding="utf-8") as fh:
                    if fh.read() != page:
                        stale.append(path)
            except FileNotFoundError:
                stale.append(path + " (missing)")
        else:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(page)
            written += 1

    stats = [("Cards", len(cards)), ("Printings", sum(len(v) for v in printings.values())),
             ("Sets", 5), ("Vocabulary terms", len(TERM_LABELS)),
             ("Card pages", len(cards))]
    stub = ('<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<title>ST:CC Card Dataset</title>\n'
            '<link rel="canonical" href="index.html">\n'
            '<meta http-equiv="refresh" content="0; url=index.html">\n</head>\n'
            '<body><p>This page moved to <a href="index.html">the dataset home</a>.</p>'
            '</body>\n</html>\n')
    pages = [(os.path.join(outdir, "index.html"), index_page(cards)),
             (os.path.join(args.repo, "index.html"), dataset_page(stats, ctx_url)),
             # dataset.html was published before the compendium moved out; keep the
             # stub so links minted under that path still land (same convention as
             # card-browser-mockup.html did for the scanner rename).
             (os.path.join(args.repo, "dataset.html"), stub)]
    for path, content in pages:
        if args.check:
            try:
                with open(path, encoding="utf-8") as fh:
                    if fh.read() != content:
                        stale.append(path)
            except FileNotFoundError:
                stale.append(path + " (missing)")
        else:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(content)
            written += 1

    fresh_sitemap = update_sitemap(args.repo, cids, write=not args.check)
    if args.check:
        with open(os.path.join(args.repo, "sitemap.xml"), encoding="utf-8") as fh:
            if fh.read() != fresh_sitemap:
                stale.append("sitemap.xml")
        if stale:
            print("STALE: %d file(s), e.g. %s" % (len(stale), ", ".join(stale[:3])),
                  file=sys.stderr)
            return 1
        print("OK: card pages, dataset page and sitemap are current.")
        return 0

    print("wrote %d pages (%d cards) + sitemap" % (written, len(cards)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
