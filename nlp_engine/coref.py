"""Coreference / reference resolution for investigation text.

Practical pipeline (no heavy coref model required): spaCy dependency parse + case roster.
 * name, surname, title and role aliases ("Mr. Whitmore", "the caretaker", "the stout gentleman") -> the same person
 * pronouns he/him/his, she/her, they/them resolved by gender agreement, recency and grammatical-subject salience
 * "I" resolved to the document's author/speaker when known
"""
from collections import defaultdict
from .lexicon import CaseLexicon
from .ner import _lex_matchers
from .spacy_loader import get_nlp

MASC = {"he", "him", "his", "himself"}
FEM = {"she", "her", "hers", "herself"}
PLUR = {"they", "them", "their", "theirs"}
FIRST = {"i", "me", "my", "mine", "myself"}


def resolve(text: str, lex: CaseLexicon, speaker_key: str = None):
    nlp = get_nlp()
    doc = nlp(text)
    mentions = []   # (token_start_char, end_char, person_key, kind, sentence_idx, is_subject)
    sent_idx = {}
    for i, sent in enumerate(doc.sents):
        for t in sent:
            sent_idx[t.i] = i
    for label, (pm, keys) in _lex_matchers(lex).items():
        if label != "PERSON":
            continue
        for mid, s, e in pm(doc):
            key = keys[nlp.vocab.strings[mid]]
            span = doc[s:e]
            subj = any(t.dep_ in ("nsubj", "nsubjpass") for t in span)
            mentions.append({"start": span.start_char, "end": span.end_char, "text": span.text, "person": key,
                             "kind": "name", "sent": sent_idx.get(s, 0), "subject": subj, "tok": s})
    # drop shorter overlapping alias spans
    mentions.sort(key=lambda m: (m["start"], -(m["end"] - m["start"])))
    clean = []
    for m in mentions:
        if clean and m["start"] < clean[-1]["end"]:
            continue
        clean.append(m)
    mentions = clean
    pron = []
    for t in doc:
        low = t.lower_
        if low in MASC | FEM | PLUR or (low in FIRST and speaker_key):
            pron.append(t)
    resolved = []
    for t in pron:
        low = t.lower_
        if low in FIRST:
            resolved.append({"start": t.idx, "end": t.idx + len(t.text), "text": t.text, "person": speaker_key,
                             "kind": "first-person", "sent": sent_idx[t.i], "tok": t.i, "confidence": 0.95})
            continue
        want = "m" if low in MASC else "f" if low in FEM else None
        best, best_score = None, 0.0
        for m in mentions:
            if m["tok"] >= t.i:
                continue
            dist = sent_idx[t.i] - m["sent"]
            if dist > 2:
                continue
            p = lex.person_by_key(m["person"])
            if want and (not p or p.gender != want):
                continue
            if not want and p and p.key == speaker_key:
                continue
            score = 1.0 / (1 + dist) + (0.6 if m["subject"] else 0.0) + 0.001 * m["tok"]
            if score > best_score:
                best, best_score = m, score
        if best:
            resolved.append({"start": t.idx, "end": t.idx + len(t.text), "text": t.text, "person": best["person"],
                             "kind": "pronoun", "sent": sent_idx[t.i], "tok": t.i,
                             "confidence": round(min(0.95, 0.45 + best_score / 3), 2), "antecedent": best["text"]})
    allm = sorted(mentions + resolved, key=lambda m: m["start"])
    clusters = defaultdict(list)
    for m in allm:
        if m.get("person"):
            clusters[m["person"]].append({k: m[k] for k in ("text", "start", "end", "kind") if k in m})
    annotated = _annotate(text, [m for m in resolved if m.get("person")], lex)
    return {"clusters": [{"person": k, "name": (lex.person_by_key(k).name if lex.person_by_key(k) else k),
                          "mentions": v} for k, v in clusters.items()],
            "resolved_pronouns": resolved, "annotated": annotated}


def _annotate(text, resolved, lex):
    out, last = [], 0
    for r in sorted(resolved, key=lambda r: r["start"]):
        p = lex.person_by_key(r["person"])
        out.append(text[last:r["end"]])
        out.append(f" [{p.name if p else r['person']}]")
        last = r["end"]
    out.append(text[last:])
    return "".join(out)


def alias_map(lex: CaseLexicon):
    """alias -> person key (for role descriptions like 'the caretaker')."""
    return {a: k for a, k in lex.all_alias_patterns()}
