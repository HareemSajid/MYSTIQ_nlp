"""Build the per-case knowledge base: clean -> sentence-aware chunks -> metadata.

Audience control (prevents information leakage):
  public            documents, statements, public suspect profile, timeline, case context   (player + Watson + suspects)
  watson            fixed hints (only released hints are ever retrievable)
  suspect:<key>     that suspect's private persona knowledge and authored interview topics (that suspect only)
The canonical answer key (CaseSolution) is NEVER chunked or indexed.
"""
import re
from dataclasses import dataclass, field, asdict
from nlp_engine.lexicon import CaseLexicon
from nlp_engine.spacy_loader import get_nlp
from nlp_engine.temporal import extract_times

TARGET_WORDS = 70
MAX_WORDS = 110


@dataclass
class Chunk:
    id: str
    case_number: int
    kind: str                   # document | statement | profile | timeline | context | hint | persona | topic
    text: str                   # text shown / cited
    title: str = ""
    doc_key: str = ""
    doc_type: str = ""
    suspect_key: str = ""
    author: str = ""
    datetime: str = ""
    audience: str = "public"
    hint_order: int = 0
    persons: list = field(default_factory=list)
    times: list = field(default_factory=list)
    day: str = ""

    def to_dict(self):
        return asdict(self)

    def embed_text(self):
        head = f"{self.title}. " if self.title else ""
        return head + self.text


def clean(text: str) -> str:
    text = text.replace("\u2014", " - ").replace("\u2013", "-")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_chunks(text: str, target=TARGET_WORDS, maximum=MAX_WORDS):
    """Sentence-aware windows of ~target words, one-sentence overlap so a fact is never split from its context.
    Short documents (<= maximum words) stay whole."""
    text = clean(text)
    if len(text.split()) <= maximum:
        return [text]
    nlp = get_nlp()
    sents = []
    for para in text.split("\n"):
        para = para.strip()
        if para:
            sents.extend(s.text.strip() for s in nlp(para).sents if s.text.strip())
    chunks, cur, n = [], [], 0
    for s in sents:
        w = len(s.split())
        if cur and n + w > target:
            chunks.append(" ".join(cur))
            cur = cur[-1:]            # overlap
            n = len(cur[0].split()) if cur else 0
        cur.append(s)
        n += w
    if cur:
        chunks.append(" ".join(cur))
    return chunks


def _persons(text, lex: CaseLexicon):
    low = text.lower()
    found = []
    for p in lex.people:
        for a in p.aliases:
            if len(a) > 3 and re.search(r"\b%s\b" % re.escape(a), low):
                found.append(p.key)
                break
    return sorted(set(found))


def build_case_chunks(case):
    lex = CaseLexicon.from_case(case)
    out = []

    def mk(**kw):
        c = Chunk(case_number=case.number, **kw)
        c.persons = _persons(c.text, lex)
        c.times = sorted({t.minutes for t in extract_times(c.text) if t.minutes is not None})
        out.append(c)
        return c

    mk(id=f"c{case.number}:context:intro:0", kind="context", title=f"Case introduction: {case.title}",
       text=clean(case.introduction + " " + case.objective))
    for d in case.documents.all():
        parts = split_chunks(d.content)
        for i, part in enumerate(parts):
            mk(id=f"c{case.number}:document:{d.key}:{i}", kind="document", title=d.title, doc_key=d.key,
               doc_type=d.doc_type, suspect_key=d.suspect.key if d.suspect else "", author=d.author,
               datetime=d.datetime_text, text=part)
    for i, s in enumerate(case.statements.select_related("suspect", "document")):
        mk(id=f"c{case.number}:statement:{i}", kind="statement", title=f"Statement of {s.suspect.name}",
           doc_key=s.document.key if s.document else "", doc_type="Statement", suspect_key=s.suspect.key,
           author=s.suspect.name, datetime=s.document.datetime_text if s.document else "", text=clean(s.text))
    for s in case.suspects.all():
        prof = (f"{s.name}, {s.role}. Background: {s.background} Motive: {s.motive} Relationship: {s.relationship} "
                f"Known whereabouts: {s.whereabouts}")
        mk(id=f"c{case.number}:profile:{s.key}:0", kind="profile", title=f"Profile of {s.name}", suspect_key=s.key,
           doc_type="Profile", text=clean(prof))
        aud = f"suspect:{s.key}"
        mk(id=f"c{case.number}:persona:{s.key}:0", kind="persona", title=f"Private knowledge of {s.name}",
           suspect_key=s.key, audience=aud, text=clean(f"Personality: {s.personality} {s.private_knowledge} "
                                                      f"Does not know: {s.does_not_know}"))
        for j, t in enumerate(s.topics):
            mk(id=f"c{case.number}:topic:{s.key}:{j}", kind="topic", title=f"{s.name} on: {t['q'].split('?')[0]}",
               suspect_key=s.key, audience=aud, text=clean(f"Questions: {t['q']} Answer: {t['a']}"))
    for e in case.timeline.all().select_related("source"):
        mk(id=f"c{case.number}:timeline:{e.id}", kind="timeline",
           title=f"Timeline {e.day_label or 'day of incident'} {e.time_label}",
           doc_key=e.source.key if e.source else "", doc_type="Timeline",
           text=f"{e.time_label}: {e.text}", day=e.day_label)
    for h in case.hints.all():
        mk(id=f"c{case.number}:hint:{h.order}", kind="hint", title=f"Watson hint {h.order}", audience="watson",
           hint_order=h.order, text=clean(h.text))
    return out
