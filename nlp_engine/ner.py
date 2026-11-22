"""Named entity recognition: spaCy statistical NER + case-aware dictionary matching + temporal extractor.

Labels exposed: PERSON, LOCATION, DATE, TIME, ORGANISATION, OBJECT, OTHER.
spaCy's small model often mislabels Victorian names (e.g. "Ashford" -> ORG); the case lexicon corrects those
spans, and the rule-based temporal extractor supplies TIME entities.
"""
import re
from functools import lru_cache
from spacy.matcher import PhraseMatcher
from spacy.util import filter_spans
from spacy.tokens import Span

from .lexicon import CaseLexicon
from .spacy_loader import get_nlp
from .temporal import extract_times, extract_days

LABEL_MAP = {"PERSON": "PERSON", "GPE": "LOCATION", "LOC": "LOCATION", "FAC": "LOCATION", "ORG": "ORGANISATION",
             "DATE": "DATE", "TIME": "TIME", "NORP": "OTHER", "MONEY": "OTHER", "CARDINAL": "OTHER",
             "ORDINAL": "OTHER", "PRODUCT": "OBJECT", "WORK_OF_ART": "OBJECT", "EVENT": "OTHER", "QUANTITY": "OTHER"}


@lru_cache(maxsize=64)
def _matchers(sig, people_json, places, objects):
    import json
    nlp = get_nlp()
    people = json.loads(people_json)
    out = {}
    for label, terms in (("PERSON", [(a, k) for k, al in people.items() for a in al]),
                         ("LOCATION", [(p, p) for p in places]),
                         ("OBJECT", [(o, o) for o in objects])):
        pm = PhraseMatcher(nlp.vocab, attr="LOWER")
        keys = {}
        for term, key in terms:
            if len(term) < 2:
                continue
            fixed = re.sub(r"\b(mr|mrs|dr|st|capt|col)\.", lambda m: m.group(0).capitalize(), term)  # spaCy abbreviation exceptions are case-sensitive
            pm.add(f"{label}|{term}", [nlp.make_doc(fixed)])
            keys[f"{label}|{term}"] = key
        out[label] = (pm, keys)
    return out


def _lex_matchers(lex: CaseLexicon):
    import json
    people = {p.key: tuple(p.aliases) for p in lex.people}
    sig = hash((json.dumps(people, sort_keys=True), tuple(lex.places), tuple(lex.objects)))
    return _matchers(sig, json.dumps(people, sort_keys=True), tuple(lex.places), tuple(lex.objects))


_STOP_PERSON = {"the", "a", "an", "i", "he", "she", "it", "they"}


def extract_entities(text: str, lex: CaseLexicon = None, context: str = ""):
    """Return a list of dicts: text, label, start, end, source (spacy | lexicon | temporal), key (person key)."""
    nlp = get_nlp()
    doc = nlp(text)
    spans = []
    if lex is not None:
        for label, (pm, keys) in _lex_matchers(lex).items():
            for mid, s, e in pm(doc):
                name = nlp.vocab.strings[mid]
                span = Span(doc, s, e, label=label)
                spans.append((span, "lexicon", keys.get(name)))
    key_by_span = {(sp.start_char, sp.end_char): k for sp, _, k in spans}
    lex_spans = [sp for sp, _, _ in spans]
    # statistical entities, skipped where a lexicon span overlaps
    stat = []
    for ent in doc.ents:
        if ent.label_ in ("TIME",):  # replaced by temporal extractor below
            continue
        label = LABEL_MAP.get(ent.label_, "OTHER")
        if ent.label_ == "PERSON" and ent.text.lower() in _STOP_PERSON:
            continue
        stat.append(Span(doc, ent.start, ent.end, label=label))
    stat = [sp for sp in stat if not any(sp.start < l.end and l.start < sp.end for l in lex_spans)]   # lexicon wins overlaps
    merged = filter_spans(lex_spans + stat)
    results = []
    for sp in merged:
        src = "lexicon" if (sp.start_char, sp.end_char) in key_by_span else "spacy"
        results.append({"text": sp.text, "label": sp.label_, "start": sp.start_char, "end": sp.end_char,
                        "source": src, "key": key_by_span.get((sp.start_char, sp.end_char))})
    for tm in extract_times(text, context):
        results = [r for r in results if r["end"] <= tm.start or r["start"] >= tm.end]
        results.append({"text": tm.text, "label": "TIME", "start": tm.start, "end": tm.end, "source": "temporal",
                        "key": None, "normalised": tm.label(), "ambiguous": tm.ambiguous})
    # weekday names / dates as DATE
    for m in re.finditer(r"\b(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b", text):
        if not any(r["start"] <= m.start() < r["end"] for r in results):
            results.append({"text": m.group(0), "label": "DATE", "start": m.start(), "end": m.end(), "source": "rule",
                            "key": None})
    results.sort(key=lambda r: r["start"])
    return results


def entity_summary(entities):
    out = {}
    for e in entities:
        out.setdefault(e["label"], [])
        if e["text"] not in out[e["label"]]:
            out[e["label"]].append(e["text"])
    return out


def highlight_html(text, entities):
    from django.utils.html import escape
    out, last = [], 0
    for e in entities:
        if e["start"] < last:
            continue
        out.append(escape(text[last:e["start"]]))
        out.append(f'<mark class="ent ent-{e["label"]}" title="{e["label"]}">{escape(text[e["start"]:e["end"]])}'
                   f'<sup>{e["label"][:3]}</sup></mark>')
        last = e["end"]
    out.append(escape(text[last:]))
    return "".join(out)
