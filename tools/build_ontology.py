#!/usr/bin/env python3
"""build_ontology.py -- ST:CC descriptor ontology + card instance graph (TCG Schema).

Maps the five card JSONs at repo root onto the TCG Schema core vocabulary
(https://tcg-schema.org/core.ttl) and emits:

    data/stcc-ontology.ttl    the ST:CC extension vocabulary (classes, properties,
                              and every closed term set: suits, traits, operation
                              kinds, specialties, setup positions, variants)
    data/cards.jsonld         all 610 card records as tcg:Card + tcg:CardPrinting
    data/stcc-context.jsonld  is hand-maintained, NOT generated -- it is the
                              contract this script writes against; --check verifies
                              every key this script emits is defined there.

Both outputs come from one run so the vocabulary can never drift from the data
it describes (Rule 7: generators ship with their output).

Modelling decisions, and why:

- **Card vs printing.** Each JSON record is one PRINTING. Records sharing an `id`
  are printings of one abstract tcg:Card, exactly as the scanner's resolveCards()
  groups them. Card-level facts are the RESOLVED view (updated printing if any,
  else earliest box) so the graph says what cards.html shows; printing-level
  facts are collector number, set, deck, variant, artwork.
- **Divergence is emitted, not flattened.** A printing whose printed suit/traits/
  icons/VP differ from the resolved view carries stcc:printed* triples of its own.
  Identical printings (the 45 reprints) stay silent rather than duplicating the
  card. That is what makes an `updated` card readable at both levels.
- **stcc:printed* are NOT subproperties of the tcg: card properties.** tcg:cardType
  and tcg:cardSubtype carry rdfs:domain tcg:Card, so an RDFS reasoner would infer
  that every printing IS a card. The card-level properties (stcc:suit, the three
  trait properties) ARE subproperties, because there the domain is satisfied.
- **Icons keep the JSON's one-object-per-printed-icon model** (WORKFLOW: "repeated
  objects, no count"). RDF triples are a set, so `stcc:hasIcon stcc:SkillMilitary`
  twice would collapse to one; each printed icon therefore gets its own node with
  a stable IRI, and multiplicity survives.
- **Every term is family-prefixed** (SuitCaptain, PosCaptain, TraitSurprise,
  OpSurprise). Two collisions exist today -- Captain/Status are suits AND setup
  positions, Surprise is a trait AND an operation kind -- and a published IRI is
  the one thing that cannot be renamed later, so the prefix is uniform rather
  than applied only where it is currently needed.
- **One root for everything.** Vocabulary and instances are both fragments of
  https://tcg-schema.org/stcc : terms are CamelCase (#SuitPerson), instances are
  prefixed (#card-sisko-garak, #printing-core-sisko-garak, #set-core, #pool-core-sisko,
  #art-core-sisko-garak, #game-stcc). No IRI names the host that happens to serve the files, so
  moving the site does not rewrite the graph. Local names never contain "/", so every
  IRI still writes as a Turtle prefixed name.

Closed vocabularies hard-fail on an unknown value, the same philosophy as
build_box2_from_sheet.py's variant markers: a silent fallback is the one failure
that hides itself. Traits are OPEN (a new box adds traits) and only warn.

Usage:
  python3 tools/build_ontology.py                 # write both outputs
  python3 tools/build_ontology.py --check         # exit 1 if outputs are stale
  python3 tools/build_ontology.py --report        # coverage / divergence summary

Stdlib only.
"""
import argparse
import json
import os
import re
import sys
from collections import OrderedDict, defaultdict

# --- namespaces -------------------------------------------------------------
# Vocabulary is minted alongside core on tcg-schema.org; instances are minted on
# the site that publishes the data. Changing either is a one-line edit plus a
# regen, which is precisely why they are constants and not spelled out inline.
ROOT = "https://tcg-schema.org/stcc"
VOCAB = ROOT + "#"          # vocabulary AND instances are fragments of the root
CORE = "https://tcg-schema.org/core#"
SITE = ROOT + "/"           # canonical base for served files (images, documents)
CONTEXT_URL = SITE + "data/stcc-context.jsonld"

BOXES = [("core", "box1.json", "Captain's Chair", "box1"),
         ("tbg", "box2.json", "To Boldly Go", "box2"),
         ("2nd", "box3.json", "Second Contact", "box3"),
         ("promo1", "promo1.json", "Promo Pack 1", "promo1"),
         ("promo2", "promo2.json", "Promo Pack 2", "promo2")]
BOX_ORDER = [b[0] for b in BOXES]

# --- closed vocabularies (hard fail on anything else) -----------------------
SUITS = ["Person", "Ally", "Ship", "Cargo", "Location", "Encounter", "Incident",
         "Captain", "Directive", "Status"]
SPECIALTIES = ["Research", "Influence", "Military", "Any", "Variable"]
ICON_TYPES = ["Skill", "Focus"]
VARIANTS = ["original", "reprint", "updated"]
OPERATION_KINDS = ["play", "support", "control", "resupply", "cleanup", "activation",
                   "passive", "reaction", "special", "surprise", "endgame", "cost",
                   "banner"]
POSITIONS = ["Starting", "Available", "Development", "Reserve", "Advanced", "Captain",
             "Deployed", "Discard", "Rewards", "Status", "Controlled Location",
             "Incident Deck", "Solo Campaign", "Solo Challenge"]
# Rulebook p.36 buckets. Membership is data-driven; the bucket names are not.
TRAIT_BUCKETS = [("species_traits", "SpeciesTrait", "species"),
                 ("regular_traits", "RegularTrait", "regular"),
                 ("other_traits", "OtherTrait", "other")]

# Operation families, from data/ops.json (colour is presentation, category is not).
OP_CATEGORY = {"play": "play", "support": "play", "control": "play",
               "resupply": "upkeep", "cleanup": "upkeep",
               "activation": "table", "passive": "table", "reaction": "table",
               "endgame": "endgame", "special": "special", "surprise": "special",
               "cost": "devcost", "banner": "banner"}


def camel(value):
    """'Mind Control' -> 'MindControl'; "Vau N'Akat" -> 'VauNAkat'; 'NX-01' -> 'NX01'."""
    parts = re.split(r"[^A-Za-z0-9]+", value)
    out = []
    for p in parts:
        if not p:
            continue
        out.append(p if p.isupper() or p[0].isupper() else p[0].upper() + p[1:])
    return "".join(out)


def ttl_str(s):
    return '"%s"' % s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


class Fail(Exception):
    pass


def load_cards(repo):
    records = []
    for key, fname, gamebox, folder in BOXES:
        path = os.path.join(repo, fname)
        with open(path, encoding="utf-8") as fh:
            for rec in json.load(fh):
                if rec.get("game_box") != gamebox:
                    raise Fail("%s: %s has game_box %r, expected %r"
                               % (fname, rec.get("id"), rec.get("game_box"), gamebox))
                records.append((key, folder, rec))
    return records


def validate(records, warn):
    """Closed vocabularies gate; open ones (traits, decks) report."""
    bad = []
    traits = defaultdict(set)
    for key, _folder, r in records:
        where = "%s/%s" % (key, r.get("id"))
        if r["suit"] not in SUITS:
            bad.append("%s: unknown suit %r" % (where, r["suit"]))
        if r.get("variant") and r["variant"] not in VARIANTS:
            bad.append("%s: unknown variant %r" % (where, r["variant"]))
        if r.get("position_indicator") and r["position_indicator"] not in POSITIONS:
            bad.append("%s: unknown position_indicator %r" % (where, r["position_indicator"]))
        for icon in r.get("icons") or []:
            if icon.get("specialty") not in SPECIALTIES:
                bad.append("%s: unknown icon specialty %r" % (where, icon.get("specialty")))
            if icon.get("type") not in ICON_TYPES:
                bad.append("%s: unknown icon type %r" % (where, icon.get("type")))
        for strip in r.get("strips") or []:
            if strip.get("kind") not in OPERATION_KINDS:
                bad.append("%s: unknown operation kind %r" % (where, strip.get("kind")))
        stem = os.path.splitext(r.get("filename") or "")[0]
        if stem and stem != r["id"]:
            bad.append("%s: filename stem %r != id (WORKFLOW invariant)" % (where, stem))
        for field, _cls, bucket in TRAIT_BUCKETS:
            for t in r.get(field) or []:
                traits[bucket].add(t)
    # A trait slug collision would silently merge two traits into one IRI.
    seen = {}
    for bucket, names in traits.items():
        for name in names:
            slug = "Trait" + camel(name)
            if slug in seen and seen[slug] != name:
                bad.append("trait slug collision: %r and %r both -> %s"
                           % (seen[slug], name, slug))
            seen[slug] = name
    if bad:
        raise Fail("card data failed validation:\n  " + "\n  ".join(bad))
    return traits


def group(records):
    """id -> printings, in box order. Mirrors resolveCards() in cards.html."""
    by_id = OrderedDict()
    for key, folder, r in records:
        by_id.setdefault(r["id"], []).append((key, folder, r))
    for cid, prints in by_id.items():
        prints.sort(key=lambda p: BOX_ORDER.index(p[0]))
    return by_id


def resolved(prints):
    """Text version the scanner shows: the updated printing if any, else earliest box."""
    upd = [p for p in prints if p[2].get("variant") == "updated"]
    return upd[-1] if upd else prints[0]


def coalesce(prints, field):
    """First non-null across printings -- the resolver's rule for vp/position/away_team."""
    for _k, _f, r in prints:
        v = r.get(field)
        if v is not None and v != "":
            return v
    return None


# Instance IRIs are fragments of the same root document as the vocabulary, so the
# whole graph -- terms and data alike -- is addressed under one IRI and nothing is
# tied to whichever host currently serves the files. Local names avoid "/" so every
# IRI still writes as a Turtle prefixed name.
def card_iri(cid):
    return VOCAB + "card-" + cid


def printing_iri(box, cid):
    return VOCAB + "printing-" + box + "-" + cid


def deck_iri(box, source):
    return VOCAB + "pool-" + box + "-" + re.sub(r"[^a-z0-9]+", "-", source.lower()).strip("-")


def set_iri(box):
    return VOCAB + "set-" + box


def art_iri(box, cid):
    return VOCAB + "art-" + box + "-" + cid


def trait_terms(rec):
    out = []
    for field, _cls, _bucket in TRAIT_BUCKETS:
        out.append(["stcc:Trait" + camel(t) for t in rec.get(field) or []])
    return out


def icon_terms(rec):
    return [(i["type"], i["specialty"]) for i in rec.get("icons") or []]


def printed_view(rec):
    """The comparable printed facts of one record.

    Traits and icons compare SORTED: printed order is not semantic (WORKFLOW's
    reprint check makes the same point). Comparing in printed order reported 10
    printings as divergent purely because a trait list was written in a different
    order in a later box.
    """
    traits = tuple(tuple(sorted(bucket)) for bucket in trait_terms(rec))
    return (rec["suit"], traits, tuple(sorted(icon_terms(rec))),
            rec.get("glory"), rec.get("position_indicator"),
            tuple((s["kind"], s.get("action"), s.get("qual"), s["text"])
                  for s in rec.get("strips") or []))


# --- ontology (Turtle) ------------------------------------------------------
HEADER = """\
@prefix stcc:   <{vocab}> .
@prefix tcg:    <{core}> .
@prefix schema: <https://schema.org/> .
@prefix rdf:    <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs:   <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd:    <http://www.w3.org/2001/XMLSchema#> .
@prefix owl:    <http://www.w3.org/2002/07/owl#> .

# GENERATED by tools/build_ontology.py -- edit the script, not this file.
# Term sets are derived from box1.json .. promo2.json, so the vocabulary cannot
# drift from the cards it describes.

<{vocabbase}>
  a owl:Ontology ;
  rdfs:label "TCG Schema -- Star Trek: Captain's Chair"@en ;
  rdfs:comment "Game-specific extension of TCG Schema Core for Star Trek: Captain's Chair (WizKids). Covers the printed card vocabulary: suits, the three trait buckets, skill/focus icons, operation strips, victory points, setup positions and printing variants. Vocabulary and card instances share this root: terms are CamelCase fragments, instances are prefixed fragments (card-, printing-, set-, pool-, art-, game-)."@en ;
  rdfs:seeAlso <{site}stcc.ttl> ;
  owl:imports <https://tcg-schema.org/core> .

####################
# CLASSES          #
####################

stcc:Suit a rdfs:Class ;
  rdfs:label "Suit"@en ;
  rdfs:comment "The printed suit of a card. Captain, Directive and Status are crew-deck suits rather than market suits; they are deliberate deviations from the rulebook, used as suit values for practical filtering."@en ;
  rdfs:subClassOf tcg:CardType .

stcc:Trait a rdfs:Class ;
  rdfs:label "Trait"@en ;
  rdfs:comment "A printed trait. Rulebook p.36 sorts traits into three buckets, modelled as the subclasses below."@en ;
  rdfs:subClassOf tcg:CardSubtype .

stcc:SpeciesTrait a rdfs:Class ; rdfs:label "SpeciesTrait"@en ; rdfs:subClassOf stcc:Trait .
stcc:RegularTrait a rdfs:Class ; rdfs:label "RegularTrait"@en ; rdfs:subClassOf stcc:Trait .
stcc:OtherTrait   a rdfs:Class ; rdfs:label "OtherTrait"@en   ; rdfs:subClassOf stcc:Trait .

stcc:Specialty a rdfs:Class ;
  rdfs:label "Specialty"@en ;
  rdfs:comment "Research / Influence / Military, plus Any (counts for all three) and Variable (a conditional value). Rulebook p.17."@en ;
  rdfs:subClassOf schema:DefinedTerm .

stcc:Icon a rdfs:Class ;
  rdfs:label "Icon"@en ;
  rdfs:comment "One printed skill or focus icon. Each printed icon is its own node: a card with two Military Skills carries two stcc:Icon nodes, never a count, mirroring the repeated-objects rule in the card JSON. RDF triples are a set, so a shared term would collapse the repeat."@en ;
  rdfs:subClassOf schema:Intangible .

stcc:SkillIcon a rdfs:Class ; rdfs:label "SkillIcon"@en ; rdfs:subClassOf stcc:Icon .
stcc:FocusIcon a rdfs:Class ; rdfs:label "FocusIcon"@en ; rdfs:subClassOf stcc:Icon .

stcc:Operation a rdfs:Class ;
  rdfs:label "Operation"@en ;
  rdfs:comment "One printed operation strip: a keyword band (PLAY, ACTIVATION, REACTION, ...) with its rules text. Strips are ordered as printed."@en ;
  rdfs:subClassOf tcg:Ability .

stcc:OperationKind a rdfs:Class ;
  rdfs:label "OperationKind"@en ;
  rdfs:comment "The keyword of an operation strip, used as the tcg:abilityType of an stcc:Operation. ACTIVATION, PASSIVE and REACTION share a printed colour but are different rules, so each kind is its own term."@en ;
  rdfs:subClassOf schema:DefinedTerm .

stcc:SetupPosition a rdfs:Class ;
  rdfs:label "SetupPosition"@en ;
  rdfs:comment "Where a card starts the game (the printed position indicator). Analogous to tcg:zoneRole, which is not reused because its domain is tcg:DeckListEntry."@en ;
  rdfs:subClassOf schema:DefinedTerm .

stcc:PrintingVariant a rdfs:Class ;
  rdfs:label "PrintingVariant"@en ;
  rdfs:comment "How a printing relates to the earliest printing of the same card: original, reprint (gameplay-identical) or updated (new traits or errata). Read from the marker on the printed card number."@en ;
  rdfs:subClassOf schema:DefinedTerm .

stcc:CardPool a rdfs:Class ;
  rdfs:label "CardPool"@en ;
  rdfs:comment "The group a printing belongs to inside its box: a captain's deck, the shared Common market, or Promo. Named 'Deck' in the card JSON's `source` field."@en ;
  rdfs:subClassOf tcg:Deck .

####################
# PROPERTIES       #
####################

# --- card level (the resolved view: updated printing if any, else earliest box)

stcc:suit a rdf:Property ;
  rdfs:label "suit"@en ;
  rdfs:domain tcg:Card ; rdfs:range stcc:Suit ;
  rdfs:subPropertyOf tcg:cardType ;
  stcc:jsonKey "suit" .

stcc:speciesTrait a rdf:Property ;
  rdfs:label "speciesTrait"@en ;
  rdfs:domain tcg:Card ; rdfs:range stcc:SpeciesTrait ;
  rdfs:subPropertyOf tcg:cardSubtype ;
  stcc:jsonKey "species_traits" .

stcc:regularTrait a rdf:Property ;
  rdfs:label "regularTrait"@en ;
  rdfs:domain tcg:Card ; rdfs:range stcc:RegularTrait ;
  rdfs:subPropertyOf tcg:cardSubtype ;
  stcc:jsonKey "regular_traits" .

stcc:otherTrait a rdf:Property ;
  rdfs:label "otherTrait"@en ;
  rdfs:domain tcg:Card ; rdfs:range stcc:OtherTrait ;
  rdfs:subPropertyOf tcg:cardSubtype ;
  stcc:jsonKey "other_traits" .

stcc:hasIcon a rdf:Property ;
  rdfs:label "hasIcon"@en ;
  rdfs:comment "One node per printed icon; repeats are meaningful."@en ;
  rdfs:domain tcg:Card ; rdfs:range stcc:Icon ;
  stcc:jsonKey "icons" .

stcc:specialty a rdf:Property ;
  rdfs:label "specialty"@en ;
  rdfs:domain stcc:Icon ; rdfs:range stcc:Specialty .

stcc:victoryPoints a rdf:Property ;
  rdfs:label "victoryPoints"@en ;
  rdfs:comment "The number in the bottom-right corner of the card. This is Victory Points in the rulebook, NOT Glory (the blue token some card text refers to); the two were conflated until Aug 2026 and the JSON key is still `glory`. Focus cards print '?' and carry no value. Values can be negative."@en ;
  rdfs:domain tcg:Card ; rdfs:range xsd:integer ;
  stcc:jsonKey "glory" .

stcc:startingPosition a rdf:Property ;
  rdfs:label "startingPosition"@en ;
  rdfs:domain tcg:Card ; rdfs:range stcc:SetupPosition ;
  rdfs:seeAlso tcg:zoneRole ;
  stcc:jsonKey "position_indicator" .

stcc:awayTeamSize a rdf:Property ;
  rdfs:label "awayTeamSize"@en ;
  rdfs:comment "The away-team size printed on a captain card. A STRING, not an integer: two captains print a plus (Archer '2+', Pike '4+')."@en ;
  rdfs:domain tcg:Card ; rdfs:range xsd:string ;
  stcc:jsonKey "away_team" .

stcc:resolvedFrom a rdf:Property ;
  rdfs:label "resolvedFrom"@en ;
  rdfs:comment "The printing whose printed facts are asserted at card level: the updated printing if the card has one, else the earliest-box printing."@en ;
  rdfs:domain tcg:Card ; rdfs:range tcg:CardPrinting .

# --- operation strips

stcc:costsAction a rdf:Property ;
  rdfs:label "costsAction"@en ;
  rdfs:comment "True when the strip prints the action cost ahead of its keyword, false for Free. Absent when the card prints neither."@en ;
  rdfs:domain stcc:Operation ; rdfs:range xsd:boolean ;
  stcc:jsonKey "action" .

stcc:qualifier a rdf:Property ;
  rdfs:label "qualifier"@en ;
  rdfs:comment "Verbatim qualifier between the keyword dash and the colon: 'Action, Requires 3 Military', 'Bot only', 'Attack', ..."@en ;
  rdfs:domain stcc:Operation ; rdfs:range xsd:string ;
  stcc:jsonKey "qual" .

stcc:operationCategory a rdf:Property ;
  rdfs:label "operationCategory"@en ;
  rdfs:comment "The printed family a kind is boxed with; consecutive same-family strips merge into one box on the card. From data/ops.json."@en ;
  rdfs:domain stcc:OperationKind ; rdfs:range xsd:string .

# --- printing level

stcc:printingVariant a rdf:Property ;
  rdfs:label "printingVariant"@en ;
  rdfs:domain tcg:CardPrinting ; rdfs:range stcc:PrintingVariant ;
  stcc:jsonKey "variant" .

stcc:inPool a rdf:Property ;
  rdfs:label "inPool"@en ;
  rdfs:domain tcg:CardPrinting ; rdfs:range stcc:CardPool ;
  stcc:jsonKey "source" .

# Printing-level printed facts, emitted ONLY where a printing diverges from the
# card's resolved view. Deliberately NOT subproperties of tcg:cardType /
# tcg:cardSubtype: those carry rdfs:domain tcg:Card, so a reasoner would infer
# that every printing is itself a card.
stcc:printedSuit a rdf:Property ;
  rdfs:label "printedSuit"@en ;
  rdfs:domain tcg:CardPrinting ; rdfs:range stcc:Suit ; rdfs:seeAlso stcc:suit .

stcc:printedTrait a rdf:Property ;
  rdfs:label "printedTrait"@en ;
  rdfs:domain tcg:CardPrinting ; rdfs:range stcc:Trait ; rdfs:seeAlso stcc:speciesTrait .

stcc:printedIcon a rdf:Property ;
  rdfs:label "printedIcon"@en ;
  rdfs:domain tcg:CardPrinting ; rdfs:range stcc:Icon ; rdfs:seeAlso stcc:hasIcon .

stcc:printedVictoryPoints a rdf:Property ;
  rdfs:label "printedVictoryPoints"@en ;
  rdfs:domain tcg:CardPrinting ; rdfs:range xsd:integer ; rdfs:seeAlso stcc:victoryPoints .

stcc:printedStartingPosition a rdf:Property ;
  rdfs:label "printedStartingPosition"@en ;
  rdfs:domain tcg:CardPrinting ; rdfs:range stcc:SetupPosition ; rdfs:seeAlso stcc:startingPosition .

# --- mapping helper

stcc:jsonKey a rdf:Property ;
  rdfs:label "jsonKey"@en ;
  rdfs:comment "The key this term is read from in box1.json .. promo2.json. Makes the JSON-to-RDF mapping machine-readable rather than prose."@en ;
  rdfs:domain rdf:Property ; rdfs:range xsd:string .

stcc:jsonValue a rdf:Property ;
  rdfs:label "jsonValue"@en ;
  rdfs:comment "The exact string this term appears as in the card JSON."@en ;
  rdfs:domain schema:DefinedTerm ; rdfs:range xsd:string .
"""


def build_ontology(traits):
    out = [HEADER.format(vocab=VOCAB, core=CORE, site=SITE,
                         vocabbase=VOCAB.rstrip("#"))]
    a = out.append

    def termset(local, label, comment):
        a("\nstcc:%s a schema:DefinedTermSet ;\n  rdfs:label %s ;\n  rdfs:comment %s .\n"
          % (local, ttl_str(label), ttl_str(comment)))

    def term(local, cls, label, setname, extra=""):
        a("stcc:%s a %s ; rdfs:label %s ; schema:inDefinedTermSet stcc:%s ; "
          "stcc:jsonValue %s%s .\n"
          % (local, cls, ttl_str(label), setname, ttl_str(label), extra))

    a("\n####################\n# TERM SETS        #\n####################\n")

    termset("suits", "Suits", "The ten suit values used in the card database.")
    for s in SUITS:
        term("Suit" + camel(s), "stcc:Suit", s, "suits")

    termset("traits", "Traits",
            "Every trait printed on a card, sorted into the rulebook's three buckets. "
            "This set is OPEN: a new box adds traits.")
    for _field, cls, bucket in TRAIT_BUCKETS:
        a("\n# %s traits (%d)\n" % (bucket, len(traits[bucket])))
        for t in sorted(traits[bucket]):
            term("Trait" + camel(t), "stcc:" + cls, t, "traits")

    a("\n")
    termset("specialties", "Specialties", "Rulebook p.17 icon specialties.")
    for s in SPECIALTIES:
        term("Specialty" + camel(s), "stcc:Specialty", s, "specialties")

    a("\n")
    termset("operationKinds", "Operation kinds",
            "The keyword band printed on an operation strip.")
    for k in OPERATION_KINDS:
        term("Op" + camel(k), "stcc:OperationKind", k, "operationKinds",
             " ;\n  stcc:operationCategory %s" % ttl_str(OP_CATEGORY[k]))

    a("\n")
    termset("setupPositions", "Setup positions",
            "The printed position indicator: where a card starts the game.")
    for p in POSITIONS:
        term("Pos" + camel(p), "stcc:SetupPosition", p, "setupPositions")

    a("\n")
    termset("printingVariants", "Printing variants",
            "Read from the marker on the printed card number: none = original, "
            "bullet = reprint, dagger = updated.")
    for v in VARIANTS:
        term("Variant" + camel(v), "stcc:PrintingVariant", v, "printingVariants")

    return "".join(out)


# --- instance graph (JSON-LD) ----------------------------------------------
def build_cards(by_id, records):
    nodes = []
    game = {"id": VOCAB + "game-stcc", "type": "tcg:CardGame",
            "name": "Star Trek: Captain's Chair"}
    nodes.append(game)

    for key, _fname, gamebox, folder in BOXES:
        nodes.append({"id": set_iri(key), "type": "tcg:CardSet", "name": gamebox,
                      "setCode": key, "inGame": game["id"]})

    pools = OrderedDict()
    for key, folder, r in records:
        iri = deck_iri(key, r["source"])
        if iri not in pools:
            label = r["source"] if r["source"] != "Common" else "Common"
            pools[iri] = {"id": iri, "type": "stcc:CardPool",
                          "name": "%s (%s)" % (label, dict((b[0], b[2]) for b in BOXES)[key]),
                          "isPartOf": set_iri(key)}
    nodes.extend(pools.values())

    divergent = 0
    for cid, prints in by_id.items():
        rkey, rfolder, rrec = resolved(prints)
        card = OrderedDict()
        card["id"] = card_iri(cid)
        card["type"] = "tcg:Card"
        card["name"] = rrec["name"]
        card["inGame"] = game["id"]
        card["suit"] = "stcc:Suit" + camel(rrec["suit"])
        for field, _cls, bucket in TRAIT_BUCKETS:
            vals = ["stcc:Trait" + camel(t) for t in rrec.get(field) or []]
            if vals:
                card[bucket + "Trait"] = vals
        icons = []
        for n, icon in enumerate(rrec.get("icons") or [], 1):
            icons.append(OrderedDict([
                ("id", card_iri(cid) + "-icon-" + str(n)),
                ("type", "stcc:" + icon["type"] + "Icon"),
                ("specialty", "stcc:Specialty" + camel(icon["specialty"]))]))
        if icons:
            card["hasIcon"] = icons
        vp = coalesce(prints, "glory")
        if vp is not None:
            card["victoryPoints"] = vp
        pos = coalesce(prints, "position_indicator")
        if pos:
            card["startingPosition"] = "stcc:Pos" + camel(pos)
        away = coalesce(prints, "away_team")
        if away:
            card["awayTeamSize"] = away
        ops = []
        for n, strip in enumerate(rrec.get("strips") or [], 1):
            op = OrderedDict([
                ("id", card_iri(cid) + "-op-" + str(n)),
                ("type", "stcc:Operation"),
                ("abilityType", "stcc:Op" + camel(strip["kind"])),
                ("orderIndex", n),
                ("abilityText", strip["text"])])
            if strip.get("action") is not None:
                op["costsAction"] = strip["action"]
            if strip.get("qual"):
                op["qualifier"] = strip["qual"]
            ops.append(op)
        if ops:
            card["hasAbility"] = ops
        card["resolvedFrom"] = printing_iri(rkey, cid)
        card["hasPrinting"] = [printing_iri(k, cid) for k, _f, _r in prints]
        nodes.append(card)

        base = printed_view(rrec)
        earliest = printing_iri(prints[0][0], cid)
        for key, folder, rec in prints:
            p = OrderedDict()
            p["id"] = printing_iri(key, cid)
            p["type"] = "tcg:CardPrinting"
            p["printsCard"] = card_iri(cid)
            p["inSet"] = set_iri(key)
            p["inPool"] = deck_iri(key, rec["source"])
            if rec.get("card_number"):
                p["collectorNumber"] = rec["card_number"]
            variant = rec.get("variant")
            if variant:
                p["printingVariant"] = "stcc:Variant" + camel(variant)
                if variant in ("reprint", "updated") and p["id"] != earliest:
                    p["reprintOf"] = earliest
            if rec.get("filename"):
                # Identity is the #art- IRI; the content URL is a LOCATION, and is
                # kept relative so it names no host and still resolves wherever the
                # files are served. Both consumers of it -- data/cards.jsonld and
                # card/<id>.html -- sit one directory deep, so "../img/..." is
                # correct from either. test_ontology.py asserts that shape.
                p["printingArtwork"] = {
                    "id": art_iri(key, cid),
                    "type": "schema:ImageObject",
                    "contentUrl": "../img/" + folder + "/" + rec["filename"]}
            # Printing-level printed facts only where this printing diverges.
            if printed_view(rec) != base:
                divergent += 1
                p["printedSuit"] = "stcc:Suit" + camel(rec["suit"])
                pt = []
                for field, _cls, _bucket in TRAIT_BUCKETS:
                    pt.extend("stcc:Trait" + camel(t) for t in rec.get(field) or [])
                if pt:
                    p["printedTrait"] = pt
                pi = []
                for n, icon in enumerate(rec.get("icons") or [], 1):
                    pi.append(OrderedDict([
                        ("id", p["id"] + "-icon-" + str(n)),
                        ("type", "stcc:" + icon["type"] + "Icon"),
                        ("specialty", "stcc:Specialty" + camel(icon["specialty"]))]))
                if pi:
                    p["printedIcon"] = pi
                if rec.get("glory") is not None:
                    p["printedVictoryPoints"] = rec["glory"]
                if rec.get("position_indicator"):
                    p["printedStartingPosition"] = "stcc:Pos" + camel(rec["position_indicator"])
                if rec.get("strips"):
                    p["printingRulesText"] = "\n---\n".join(s["text"] for s in rec["strips"])
            nodes.append(p)

    # One root means one flat local-name space: two nodes sharing a local name
    # would silently merge into one subject.
    seen = {}
    for node in nodes:
        local = node["id"].split("#", 1)[1]
        if local in seen:
            raise Fail("instance IRI collision on #%s (%s and %s)"
                       % (local, seen[local], node.get("name", node["id"])))
        seen[local] = node.get("name", node["id"])

    doc = OrderedDict()
    doc["@context"] = CONTEXT_URL
    doc["@graph"] = nodes
    return doc, divergent


def check_local_names(doc):
    """Every fragment in the graph, nested nodes included, must be unique."""
    seen = {}
    dupes = []

    def walk(node, owner):
        if isinstance(node, dict):
            iri = node.get("id")
            if isinstance(iri, str) and "#" in iri:
                local = iri.split("#", 1)[1]
                if local in seen and seen[local] != owner:
                    dupes.append("#%s (%s, %s)" % (local, seen[local], owner))
                seen[local] = owner
            for k, v in node.items():
                if k != "id":
                    walk(v, iri or owner)
        elif isinstance(node, list):
            for v in node:
                walk(v, owner)

    for n in doc["@graph"]:
        walk(n, n.get("id"))
    if dupes:
        raise Fail("instance IRI collisions: " + ", ".join(dupes[:5]))


def cross_check(repo, ttl, doc):
    """Every key the graph emits must be in the context; every stcc: term it
    references must be defined in the ontology. Without this the three files can
    disagree silently -- an undefined key is simply dropped by a JSON-LD parser,
    which loses data with nothing visibly wrong."""
    problems = []
    ctx_path = os.path.join(repo, "data", "stcc-context.jsonld")
    with open(ctx_path, encoding="utf-8") as fh:
        ctx = json.load(fh)["@context"]

    defined_terms = set(re.findall(r"^stcc:(\w+) a ", ttl, re.M))
    used_keys, used_terms = set(), set()

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                used_keys.add(k)
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
        elif isinstance(node, str) and node.startswith("stcc:"):
            used_terms.add(node[5:])

    walk(doc["@graph"])
    missing_keys = sorted(k for k in used_keys if k not in ctx)
    missing_terms = sorted(t for t in used_terms if t not in defined_terms)
    if missing_keys:
        problems.append("keys emitted but not in stcc-context.jsonld: %s"
                        % ", ".join(missing_keys))
    if missing_terms:
        problems.append("terms used but not defined in stcc-ontology.ttl: %s"
                        % ", ".join(missing_terms))
    if problems:
        raise Fail("; ".join(problems))


def report(by_id, records, divergent):
    print("cards (distinct ids): %d" % len(by_id))
    print("printings:            %d" % len(records))
    print("multi-printing cards: %d" % sum(1 for p in by_id.values() if len(p) > 1))
    print("divergent printings:  %d  (printed facts differ from the resolved view)"
          % divergent)
    ops = sum(len(r.get("strips") or []) for _k, _f, r in records)
    icons = sum(len(r.get("icons") or []) for _k, _f, r in records)
    print("operation strips:     %d" % ops)
    print("printed icons:        %d" % icons)
    notext = sum(1 for cid, p in by_id.items() if not (resolved(p)[2].get("strips")))
    print("cards without text:   %d  (strips not yet transcribed)" % notext)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if the committed outputs differ from a fresh build")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()

    try:
        records = load_cards(args.repo)
        traits = validate(records, warn=True)
    except Fail as exc:
        print("build_ontology: %s" % exc, file=sys.stderr)
        return 1

    by_id = group(records)
    ttl = build_ontology(traits)
    cards, divergent = build_cards(by_id, records)
    try:
        check_local_names(cards)
        cross_check(args.repo, ttl, cards)
    except Fail as exc:
        print("build_ontology: %s" % exc, file=sys.stderr)
        return 1
    cards_text = json.dumps(cards, indent=1, ensure_ascii=False) + "\n"

    ttl_path = os.path.join(args.repo, "data", "stcc-ontology.ttl")
    ld_path = os.path.join(args.repo, "data", "cards.jsonld")

    if args.check:
        stale = []
        for path, fresh in ((ttl_path, ttl), (ld_path, cards_text)):
            try:
                with open(path, encoding="utf-8") as fh:
                    if fh.read() != fresh:
                        stale.append(path)
            except FileNotFoundError:
                stale.append(path + " (missing)")
        if stale:
            print("STALE: " + ", ".join(stale), file=sys.stderr)
            return 1
        print("OK: ontology and card graph are current.")
        return 0

    with open(ttl_path, "w", encoding="utf-8") as fh:
        fh.write(ttl)
    with open(ld_path, "w", encoding="utf-8") as fh:
        fh.write(cards_text)
    print("wrote %s (%.1f KB)" % (ttl_path, len(ttl) / 1024.0))
    print("wrote %s (%.1f KB)" % (ld_path, len(cards_text) / 1024.0))
    if args.report:
        report(by_id, records, divergent)
    return 0


if __name__ == "__main__":
    sys.exit(main())
