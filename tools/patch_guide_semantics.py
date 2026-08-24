#!/usr/bin/env python3
"""patch_guide_semantics.py -- type the card anchors in the guides.

Market guides (and a few captain guides) already head each card's section with
<h3 id="card-id">. This turns those headings into typed references to the card
IRI, so a guide section states which card it is about instead of only looking
like it:

    <h3 id="sisko-garak" itemscope itemtype="https://tcg-schema.org/core#Card"
        itemid="https://tcg-schema.org/stcc#card-sisko-garak">Garak (Person)
        <link itemprop="https://schema.org/url" href="card/sisko-garak.html"></h3>

ONLY attributes and a void <link> are added -- no text is inserted, moved or
altered, so the canonical text in text/<slug>.txt is untouched (Rule 1). Run
verify_guide.py over every patched guide afterwards; that is the gate that proves
it, and this script prints the command.

Idempotent: a heading that already carries itemid is skipped, and an id that is
not a known card id is left alone.

Usage:
  python3 tools/patch_guide_semantics.py [--repo .] [--dry-run] [guide.html ...]
"""
import argparse
import glob
import json
import os
import re
import sys

VOCAB = "https://tcg-schema.org/stcc#"
CORE = "https://tcg-schema.org/core#"
SKIP = {"cards.html", "index.html", "dataset.html", "cards_v3.html", "cards_v2_2.html",
        "card-browser-mockup.html", "harmless_kitten.html", "archer-scoring.html"}

HEAD_RE = re.compile(r'(<h([23])\s+id="([^"]+)")(\s*>)')


def card_ids(repo):
    ids = {}
    for name in ("box1.json", "box2.json", "box3.json", "promo1.json", "promo2.json"):
        with open(os.path.join(repo, name), encoding="utf-8") as fh:
            for card in json.load(fh):
                ids.setdefault(card["id"], card["name"])
    return ids


def patch_text(text, ids):
    added = [0]

    def repl(m):
        open_tag, level, anchor, close = m.groups()
        if anchor not in ids or "itemid=" in m.group(0):
            return m.group(0)
        added[0] += 1
        return ('%s itemscope itemtype="%sCard" itemid="%scard-%s"%s'
                % (open_tag, CORE, VOCAB, anchor, close))

    out = HEAD_RE.sub(repl, text)
    # The <link> goes just inside the closing tag of each annotated heading, so the
    # heading's own text is never touched.
    out = re.sub(r'<h([23])\s+id="([^"]+)" itemscope[^>]*>.*?</h\1>',
                 add_link_wrapper, out, flags=re.S)
    return out, added[0]


def add_link_wrapper(m):
    level, anchor = m.group(1), m.group(2)
    block = m.group(0)
    if 'href="card/%s.html"' % anchor in block:
        return block
    return block[:-len("</h%s>" % level)] + \
        '<link itemprop="https://schema.org/url" href="card/%s.html"></h%s>' % (anchor, level)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("guides", nargs="*")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    ids = card_ids(args.repo)
    targets = args.guides or [os.path.basename(p) for p in
                              sorted(glob.glob(os.path.join(args.repo, "*.html")))]
    touched = []
    for name in targets:
        if os.path.basename(name) in SKIP:
            continue
        path = os.path.join(args.repo, os.path.basename(name))
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        new, added = patch_text(text, ids)
        if new == text:
            continue
        if not args.dry_run:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(new)
        touched.append((os.path.basename(path), added))

    for name, n in touched:
        print("%-38s %3d card anchors typed" % (name, n))
    if not touched:
        print("nothing to do (already typed, or no card anchors)")
        return 0
    print("\nNow prove the text did not move:")
    for name, _ in touched:
        slug = name[:-5]
        print("  python3 tools/verify_guide.py %s text/%s.txt --img-root ." % (name, slug))
    return 0


if __name__ == "__main__":
    sys.exit(main())
