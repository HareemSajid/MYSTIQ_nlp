"""Implicit-knowledge / information-leakage detection.

A statement *leaks* knowledge when it contains a specific detail (a place, a distinctive noun phrase or time phrase) that
(a) appears in a private source such as the anonymous letter, and (b) appears in NO public source (newspapers) and
(c) the speaker did not author the private source. "I wish Edward had not gone alone down to Wapping Stairs at first
light" leaks details that exist only in the withheld letter.
"""
import re
from .lexicon import CaseLexicon
from .spacy_loader import get_nlp
from .ner import extract_entities

PUBLIC_TYPES = {"Newspaper"}
PRIVATE_TYPES = {"Letter", "Note"}
GENERIC = {"time", "day", "night", "morning", "evening", "thing", "way", "man", "word", "nothing", "anyone", "one", "matter",
           "account", "office", "house", "firm", "club", "papers", "story", "sense", "step", "life"}
_STOP_HEADS = {"statement", "inspector", "notice", "interview", "letter"}


def candidate_phrases(text, lex):
    doc = get_nlp()(text)
    phrases = set()
    for e in extract_entities(text, lex):
        if e["label"] in ("LOCATION", "OBJECT") and len(e["text"]) > 3:
            phrases.add(e["text"].lower())
    for nc in doc.noun_chunks:
        toks = [t for t in nc if not (t.is_stop or t.is_punct or t.pos_ == "DET")]
        if not toks:
            continue
        head = nc.root.lemma_.lower()
        if head in GENERIC or head in _STOP_HEADS or nc.root.pos_ == "PRON":
            continue
        ph = " ".join(t.text.lower() for t in toks)
        if len(ph) > 3 and (len(toks) >= 2 or nc.root.pos_ == "PROPN"):
            phrases.add(ph)
    # time-like phrases ("first light") are valuable: keep adjective+noun bigrams around light/dawn/midnight
    for m in re.finditer(r"\b(first light|dawn|sunrise|low tide|the turn of the tide)\b", text.lower()):
        phrases.add(m.group(1))
    return phrases


def _contains(text_low, phrase):
    return re.search(r"\b%s\b" % re.escape(phrase), text_low) is not None


def detect_leaks(case, statement_text, speaker_key, documents=None):
    lex = CaseLexicon.from_case(case)
    docs = documents if documents is not None else list(case.documents.select_related("suspect"))
    public = [d for d in docs if d.doc_type in PUBLIC_TYPES]
    private = [d for d in docs if d.doc_type in PRIVATE_TYPES and not (d.suspect and d.suspect.key == speaker_key)]
    # the speaker's own statement documents are not sources of knowledge for this check
    out = []
    if not public:      # no notion of "public record" in this case (e.g. no newspapers): leakage is not meaningful
        return {"leaks": [], "flagged": False, "explanation": ""}
    pub_low = " ".join(d.content.lower() for d in public) + " " + (case.introduction + " " + case.objective).lower()
    aliases = {a for p in lex.people for a in p.aliases}
    for ph in sorted(candidate_phrases(statement_text, lex)):
        if _contains(pub_low, ph) or ph in aliases:
            continue
        src = [d for d in private if _contains(d.content.lower(), ph)]
        if src:
            out.append({"phrase": ph, "source_doc": src[0].key, "source_title": src[0].title})
    # one distinctive detail can be a coincidence; two or more shared private-only details is a pattern
    return {"leaks": out, "flagged": len(out) >= 2,
            "explanation": (f"The statement mentions {', '.join(repr(o['phrase']) for o in out)}, which appear in "
                            f"{out[0]['source_title']} but in no public source." if out else "")}
