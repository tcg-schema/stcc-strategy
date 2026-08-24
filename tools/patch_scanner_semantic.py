#!/usr/bin/env python3
"""patch_scanner_semantic.py -- microdata + dataset discovery for cards.html.

The Card Scanner renders its cards client-side, so the published page carries no
machine-readable statement about them. This patch makes every rendered card entry
an RDF subject: itemscope/itemtype/itemid on the entry plus hidden <link>/<meta>
children carrying suit, traits, icons, VP and starting position in the ST:CC
vocabulary, and a schema:url pointing at that card's own page.

Nothing visible changes: <link> and <meta> do not render, and no existing markup,
class or handler is touched.

cards.html is edited by several sessions and is never regenerated from a private
base (WORKFLOW: File Naming Convention). So this is an idempotent patch that
asserts every anchor and refuses to run twice, and builds the whole new file in
memory before opening the destination -- the lesson from patch_scanner_strategy.py,
which once truncated the scanner to zero bytes when a patch failed mid-write.

Usage:
  python3 tools/patch_scanner_semantic.py [cards.html] [-o out.html]
"""
import argparse
import sys

MARK = "SEMANTIC_MICRODATA_START"

HEAD = """<!-- """ + MARK + """ (tools/patch_scanner_semantic.py) -->
<link rel="alternate" type="application/ld+json" href="data/cards.jsonld" title="Card graph (JSON-LD)">
<link rel="alternate" type="text/turtle" href="data/stcc-ontology.ttl" title="ST:CC vocabulary (Turtle)">
<script type="application/ld+json">
{"@context":"https://schema.org/","@type":"Dataset",
 "name":"Star Trek: Captain's Chair card data",
 "description":"Every card in Star Trek: Captain's Chair as linked data, mapped onto the TCG Schema vocabulary.",
 "url":"dataset.html",
 "distribution":[{"@type":"DataDownload","encodingFormat":"application/ld+json","contentUrl":"data/cards.jsonld"},
                 {"@type":"DataDownload","encodingFormat":"text/turtle","contentUrl":"data/stcc-ontology.ttl"}]}
</script>
<!-- SEMANTIC_MICRODATA_END -->
"""

JS = """
// --- """ + MARK + """ -------------------------------------------------
// Every card entry is published as an RDF subject in the ST:CC vocabulary
// (https://tcg-schema.org/stcc#). Values are emitted as <link>/<meta>, which
// render nothing, so this is invisible on screen and complete to a parser.
// semTerm() MUST stay in step with camel() in tools/build_ontology.py: the two
// mint the same IRIs from the same printed strings.
const SEM_ROOT='https://tcg-schema.org/stcc#';
const SEM_CORE='https://tcg-schema.org/core#';
const SEM_SCHEMA='https://schema.org/';
function semTerm(prefix, value){
  const parts=String(value).split(/[^A-Za-z0-9]+/).filter(Boolean).map(p=>
    (p===p.toUpperCase()||p[0]===p[0].toUpperCase()) ? p : p[0].toUpperCase()+p.slice(1));
  return SEM_ROOT+prefix+parts.join('');
}
function semLink(el, prop, href){
  const n=document.createElement('link'); n.setAttribute('itemprop',prop); n.setAttribute('href',href);
  el.appendChild(n);
}
function semMeta(el, prop, content){
  const n=document.createElement('meta'); n.setAttribute('itemprop',prop); n.setAttribute('content',content);
  el.appendChild(n);
}
function semAnnotate(el, c){
  el.setAttribute('itemscope','');
  el.setAttribute('itemtype', SEM_CORE+'Card');
  el.setAttribute('itemid', SEM_ROOT+'card-'+c.id);
  semMeta(el, SEM_SCHEMA+'name', c.name||'');
  semLink(el, SEM_SCHEMA+'url', 'card/'+c.id+'.html');
  if(c.suit) semLink(el, SEM_ROOT+'suit', semTerm('Suit', c.suit));
  (c.species||[]).forEach(t=>semLink(el, SEM_ROOT+'speciesTrait', semTerm('Trait', t)));
  (c.regular||[]).forEach(t=>semLink(el, SEM_ROOT+'regularTrait', semTerm('Trait', t)));
  (c.other||[]).forEach(t=>semLink(el, SEM_ROOT+'otherTrait', semTerm('Trait', t)));
  // One node per printed icon, never a count: repeats are meaningful and a shared
  // term would collapse them (same rule as the JSON and the ontology).
  (c.skills||[]).forEach((s,i)=>{
    const m=/^(\\S+)\\s+(Skill|Focus)$/.exec(s); if(!m) return;
    const node=document.createElement('span');
    node.setAttribute('itemprop', SEM_ROOT+'hasIcon');
    node.setAttribute('itemscope','');
    node.setAttribute('itemtype', SEM_ROOT+m[2]+'Icon');
    node.setAttribute('itemid', SEM_ROOT+'card-'+c.id+'-icon-'+(i+1));
    node.style.display='none';
    semLink(node, SEM_ROOT+'specialty', semTerm('Specialty', m[1]));
    el.appendChild(node);
  });
  if(c.vp!==null && c.vp!==undefined) semMeta(el, SEM_ROOT+'victoryPoints', String(c.vp));
  if(c.position_indicator) semLink(el, SEM_ROOT+'startingPosition', semTerm('Pos', c.position_indicator));
  if(c.away_team) semMeta(el, SEM_ROOT+'awayTeamSize', String(c.away_team));
}
// --- SEMANTIC_MICRODATA_END ---------------------------------------------

"""

ANCHORS = [
    ("</head>", None),
    ("function buildPillCard(c){", None),
    ("  el.className='card-entry'; el.dataset.suit=c.suit||'';", None),
    ("function buildImgCard(c){\n  const el=document.createElement('div');\n"
     "  el.className='card-img-entry';", None),
]


def patch(text):
    if MARK in text:
        raise SystemExit("patch_scanner_semantic: already applied (marker present); "
                         "nothing to do")
    for anchor, _ in ANCHORS:
        n = text.count(anchor)
        if n != 1:
            raise SystemExit("patch_scanner_semantic: anchor found %d times, expected 1:\n  %r"
                             % (n, anchor[:70]))

    out = text.replace("</head>", HEAD + "</head>", 1)
    out = out.replace("function buildPillCard(c){", JS + "function buildPillCard(c){", 1)
    out = out.replace("  el.className='card-entry'; el.dataset.suit=c.suit||'';",
                      "  el.className='card-entry'; el.dataset.suit=c.suit||'';\n"
                      "  semAnnotate(el, c);", 1)
    out = out.replace("function buildImgCard(c){\n  const el=document.createElement('div');\n"
                      "  el.className='card-img-entry';",
                      "function buildImgCard(c){\n  const el=document.createElement('div');\n"
                      "  el.className='card-img-entry';\n  semAnnotate(el, c);", 1)
    if MARK not in out or "semAnnotate(el, c);" not in out:
        raise SystemExit("patch_scanner_semantic: post-condition failed, nothing written")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", default="cards.html")
    ap.add_argument("-o", "--out")
    args = ap.parse_args()
    with open(args.path, encoding="utf-8") as fh:
        text = fh.read()
    new = patch(text)                      # built in full before anything is opened for write
    dest = args.out or args.path
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write(new)
    print("patched %s (+%d bytes)" % (dest, len(new) - len(text)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
