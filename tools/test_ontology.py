#!/usr/bin/env python3
"""test_ontology.py -- gate for the ST:CC card ontology and its instance graph.

Parses data/stcc-ontology.ttl and data/cards.jsonld as RDF and asserts that the
graph says what the vocabulary claims. Exit 1 = do not push. Run after any change
to the card JSONs, the ontology generator, or the JSON-LD context:

    python3 tools/test_ontology.py                       # ontology + graph
    python3 tools/test_ontology.py --core path/to/core.ttl   # also check core alignment

Without --core, the checks that need TCG Schema Core print SKIP rather than
passing silently: a check that quietly does nothing is worse than no check.
Fetch core with:  curl -o core.ttl https://www.tcg-schema.org/core.ttl

Requires rdflib.
"""
import argparse
import json
import os
import sys

try:
    import rdflib
    from rdflib import Graph, RDF, RDFS, URIRef, Literal
except ImportError:
    print("test_ontology: rdflib is required (pip install rdflib)", file=sys.stderr)
    sys.exit(2)

STCC = "https://tcg-schema.org/stcc#"
TCG = "https://tcg-schema.org/core#"
SCHEMA = "https://schema.org/"

FAILURES = []
SKIPS = []


def check(name, ok, detail=""):
    if ok:
        print("  PASS  %s" % name)
    else:
        print("  FAIL  %s%s" % (name, ("\n        " + detail) if detail else ""))
        FAILURES.append(name)


def skip(name, why):
    print("  SKIP  %s (%s)" % (name, why))
    SKIPS.append(name)


def load_cards_graph(repo):
    """Parse cards.jsonld with the context resolved locally, so the test never
    depends on the context having been published yet."""
    with open(os.path.join(repo, "data", "cards.jsonld"), encoding="utf-8") as fh:
        doc = json.load(fh)
    with open(os.path.join(repo, "data", "stcc-context.jsonld"), encoding="utf-8") as fh:
        doc["@context"] = json.load(fh)["@context"]
    g = Graph()
    g.parse(data=json.dumps(doc), format="json-ld")
    return g, doc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--core", help="path to a local copy of TCG Schema core.ttl")
    args = ap.parse_args()

    onto = Graph()
    onto.parse(os.path.join(args.repo, "data", "stcc-ontology.ttl"), format="turtle")
    print("ontology: %d triples" % len(onto))
    cards, doc = load_cards_graph(args.repo)
    print("card graph: %d triples\n" % len(cards))

    # --- vocabulary integrity -------------------------------------------------
    # Vocabulary and instances share one root, so the local name says which is
    # which: CamelCase (#SuitPerson, #victoryPoints) is vocabulary and must be
    # declared in the ontology; lowercase (#card-garak) is an instance and must
    # carry a known prefix. Without this split every card id reads as an
    # undeclared term.
    INSTANCE_PREFIXES = ("card-", "printing-", "set-", "pool-", "art-", "game-")

    def is_vocab(local):
        return local[:1].isupper() or (local[:1].islower() and "-" not in local)

    declared = {str(s) for s in onto.subjects(RDF.type, None) if str(s).startswith(STCC)}
    used = {str(o) for o in cards.objects(None, None)
            if isinstance(o, URIRef) and str(o).startswith(STCC)}
    used |= {str(p) for p in cards.predicates(None, None) if str(p).startswith(STCC)}
    vocab_used = {u for u in used if is_vocab(u[len(STCC):])}
    undefined = sorted(u.replace(STCC, "stcc:") for u in vocab_used - declared)
    check("every stcc: vocabulary term used by the graph is declared in the ontology",
          not undefined, ", ".join(undefined[:8]))

    all_locals = {str(n)[len(STCC):] for n in
                  set(cards.subjects(None, None)) | set(cards.objects(None, None))
                  if isinstance(n, URIRef) and str(n).startswith(STCC)}
    stray = sorted(l for l in all_locals
                   if not is_vocab(l) and not l.startswith(INSTANCE_PREFIXES))
    check("every instance fragment uses a known prefix (card-/printing-/set-/pool-/art-/game-)",
          not stray, ", ".join(stray[:8]))

    collisions = []
    for l in all_locals:
        if is_vocab(l) and l.startswith(INSTANCE_PREFIXES):
            collisions.append(l)
    check("vocabulary and instance fragment spaces do not overlap",
          not collisions, ", ".join(collisions[:5]))

    unused = sorted(
        d.replace(STCC, "stcc:") for d in declared - vocab_used
        if (URIRef(d), RDF.type, URIRef(SCHEMA + "DefinedTermSet")) not in onto
        and not any(onto.triples((URIRef(d), RDFS.subClassOf, None)))
        and (URIRef(d), RDF.type, RDF.Property) not in onto)
    check("every DefinedTerm in the vocabulary is used by the graph",
          not unused, ", ".join(unused))

    # --- range conformance ----------------------------------------------------
    bad_ranges = []
    for prop, rng in onto.subject_objects(RDFS.range):
        if not str(rng).startswith(STCC):
            continue
        for subj, obj in cards.subject_objects(prop):
            if not isinstance(obj, URIRef):
                continue
            types = set(cards.objects(obj, RDF.type)) | set(onto.objects(obj, RDF.type))
            expanded = set(types)
            for t in types:  # one hop up the class hierarchy is enough here
                expanded |= set(onto.objects(t, RDFS.subClassOf))
            if rng not in expanded:
                bad_ranges.append("%s %s %s" % (subj, prop, obj))
    check("every object of an stcc: property matches its declared range",
          not bad_ranges, "\n        ".join(bad_ranges[:5]))

    # --- domain conformance ---------------------------------------------------
    bad_domains = []
    for prop, dom in onto.subject_objects(RDFS.domain):
        for subj in set(cards.subjects(prop, None)):
            types = set(cards.objects(subj, RDF.type))
            expanded = set(types)
            for t in types:
                expanded |= set(onto.objects(t, RDFS.subClassOf))
            if dom not in expanded:
                bad_domains.append("%s is %s, not %s (via %s)"
                                   % (subj, [str(t) for t in types], dom, prop))
    check("every subject of an stcc: property matches its declared domain",
          not bad_domains, "\n        ".join(bad_domains[:5]))

    # --- the modelling promises the ontology makes ----------------------------
    cardsg = set(cards.subjects(RDF.type, URIRef(TCG + "Card")))
    printings = set(cards.subjects(RDF.type, URIRef(TCG + "CardPrinting")))
    check("cards and printings are disjoint sets of nodes",
          not (cardsg & printings),
          ", ".join(str(x) for x in list(cardsg & printings)[:3]))

    orphan = [str(p) for p in printings if not any(cards.objects(p, URIRef(TCG + "printsCard")))]
    check("every printing points at its card", not orphan, ", ".join(orphan[:3]))

    unlinked = [str(c) for c in cardsg if not any(cards.objects(c, URIRef(TCG + "hasPrinting")))]
    check("every card has at least one printing", not unlinked, ", ".join(unlinked[:3]))

    # resolvedFrom must be one of the card's own printings
    bad_resolved = []
    for c in cardsg:
        rf = list(cards.objects(c, URIRef(STCC + "resolvedFrom")))
        own = set(cards.objects(c, URIRef(TCG + "hasPrinting")))
        if len(rf) != 1 or rf[0] not in own:
            bad_resolved.append(str(c))
    check("every card resolves from one of its own printings",
          not bad_resolved, ", ".join(bad_resolved[:3]))

    # icon multiplicity: repeated printed icons must survive as distinct nodes
    with open(os.path.join(args.repo, "box1.json"), encoding="utf-8") as fh:
        b1 = json.load(fh)
    multi = [c for c in b1 if len(c.get("icons") or []) > 1]
    ok_multi = True
    detail = ""
    for c in multi[:50]:
        node = URIRef(STCC + "card-" + c["id"])
        n = len(list(cards.objects(node, URIRef(STCC + "hasIcon"))))
        if n != len(c["icons"]):
            ok_multi = False
            detail = "%s: %d icon nodes for %d printed icons" % (c["id"], n, len(c["icons"]))
            break
    check("repeated printed icons survive as distinct nodes (no set collapse)",
          ok_multi, detail)

    # artwork: identified under the root, served from the canonical site base
    bad_img = []
    for _s, o in cards.subject_objects(URIRef(SCHEMA + "contentUrl")):
        u = str(o)
        if "/img/box" not in u and "/img/promo" not in u:
            bad_img.append(u)
    check("artwork content URLs use the img/<box>/<file> convention",
          not bad_img, ", ".join(bad_img[:3]))

    # Checked against the JSON document, not the parsed graph: rdflib resolves
    # relative IRIs against a base at parse time, so by the time it is a triple the
    # relativeness is gone. "No host in the file" is a property of the file.
    raw_urls = []

    def walk_urls(node):
        if isinstance(node, dict):
            if "contentUrl" in node and isinstance(node["contentUrl"], str):
                raw_urls.append(node["contentUrl"])
            for v in node.values():
                walk_urls(v)
        elif isinstance(node, list):
            for v in node:
                walk_urls(v)

    walk_urls(doc["@graph"])
    not_relative = sorted({u for u in raw_urls if not u.startswith("../img/")})
    check("artwork content URLs are relative in the file (no host baked in)",
          not not_relative and bool(raw_urls), ", ".join(not_relative[:3]))

    # the whole point of the one-root design: no IRI names a serving host
    foreign = sorted({str(n) for _t in (cards, onto) for tr in _t for n in tr
                      if isinstance(n, URIRef) and "periodic-agent.github.io" in str(n)})
    check("no IRI in the vocabulary or graph names a serving host",
          not foreign, ", ".join(foreign[:3]))

    rooted = [str(s) for s in set(cards.subjects(None, None))
              if isinstance(s, URIRef) and not str(s).startswith(STCC)]
    check("every subject in the graph is a fragment of the semantic root",
          not rooted, ", ".join(rooted[:3]))

    # --- alignment with TCG Schema Core ---------------------------------------
    if args.core:
        core = Graph()
        core.parse(args.core, format="turtle")
        core_terms = {str(s) for s in core.subjects(RDF.type, None)}
        referenced = set()
        for g in (onto, cards):
            for s, p, o in g:
                for node in (s, p, o):
                    if isinstance(node, URIRef) and str(node).startswith(TCG):
                        referenced.add(str(node))
        missing = sorted(r.replace(TCG, "tcg:") for r in referenced - core_terms)
        check("every tcg: term referenced exists in TCG Schema Core",
              not missing, ", ".join(missing))

        # The domain trap: a subproperty inherits its parent's rdfs:domain, so
        # subclassing a property whose domain is a different class silently
        # retypes our subjects.
        clashes = []
        for prop, parent in onto.subject_objects(RDFS.subPropertyOf):
            ours = set(onto.objects(prop, RDFS.domain))
            theirs = set(core.objects(parent, RDFS.domain))
            for od in ours:
                for td in theirs:
                    if od != td and (od, RDFS.subClassOf, td) not in onto:
                        clashes.append("%s domain %s vs parent %s domain %s"
                                       % (prop, od, parent, td))
        check("no stcc: subproperty inherits a conflicting domain from core",
              not clashes, "\n        ".join(clashes))
    else:
        skip("every tcg: term referenced exists in TCG Schema Core", "no --core")
        skip("no stcc: subproperty inherits a conflicting domain from core", "no --core")

    print()
    if FAILURES:
        print("%d assertion(s) FAILED: %s" % (len(FAILURES), ", ".join(FAILURES)))
        return 1
    print("All assertions passed%s." % (" (%d skipped)" % len(SKIPS) if SKIPS else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
