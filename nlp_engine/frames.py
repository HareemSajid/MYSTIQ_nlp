"""Event-frame extraction: turns a sentence/passage into (actor, predicate, place, object, time, negation, stance).

Frames let the NLI layer check *whether two statements are even about the same event* (same person, place, day and
time) before any contradiction is declared -- the guard against keyword-based false contradictions.
"""
import re
from dataclasses import dataclass, field
from .coref import resolve
from .epistemic import classify
from .lexicon import CaseLexicon, WEEKDAYS
from .spacy_loader import get_nlp
from .temporal import extract_times, extract_days

IRREGULAR = {"left": "leave", "stood": "stand", "rose": "rise", "saw": "see", "took": "take", "taken": "take",
             "held": "hold", "heard": "hear", "went": "go", "came": "come", "sat": "sit", "kept": "keep",
             "struck": "strike", "stopped": "stop", "returned": "return", "carried": "carry", "opened": "open",
             "locked": "lock", "bolted": "bolt", "stepped": "step", "crossed": "cross", "rises": "rise",
             "crosses": "cross", "leaves": "leave", "carries": "carry", "handled": "handle", "touched": "touch",
             "noticed": "notice", "observed": "observe", "entered": "enter", "remained": "remain", "stayed": "stay",
             "fetched": "fetch", "removed": "remove", "waited": "wait", "worked": "work", "typed": "type"}

CLASSES = {
    "MOVE_OUT": {"leave", "depart", "exit", "quit", "withdraw", "rise", "alight", "stand"},
    "GO_TO": {"go", "come", "enter", "arrive", "cross", "walk", "approach", "visit", "call"},
    "PRESENT": {"remain", "stay", "wait", "post", "sit", "type", "work", "write", "read", "play"},
    "SEE": {"see", "observe", "notice", "spot", "watch", "glimpse", "view"},
    "HEAR": {"hear"},
    "TOUCH": {"touch", "handle", "hold", "take", "open", "remove", "steal", "fetch", "return", "replace", "use", "issue"},
    "LOCK": {"lock", "bolt", "unlock"},
    "STRIKE": {"strike", "chime"},
    "STOP": {"stop"},
    "CARRY": {"carry", "bring"},
    "ASSUME": {"assume", "suppose", "presume", "think", "believe", "imagine", "guess"},
}
LEMMA_TO_CLASS = {l: c for c, ls in CLASSES.items() for l in ls}
OBJECT_GROUPS = [
    {"emerald", "stone", "jewel", "gem"}, {"manuscript", "psalter", "codex"}, {"key", "keys"},
    {"letter", "note", "message", "telegram"}, {"cup", "loving cup", "chalice"}, {"cabinet", "key cabinet"},
    {"seat", "chair", "place"}, {"clock", "regulator", "timepiece"}, {"window", "latch"}, {"door"},
    {"design", "sheet", "escapement", "drawing"}, {"sideboard"}, {"ledger"}, {"valise", "luggage", "bag"},
    {"overcoat", "coat", "ulster"}, {"jade"}, {"veil"}, {"receipt"}, {"salver"}, {"shawl"}, {"fan"},
]
SCOPE_WORDS = {"second", "spare", "another", "duplicate", "other", "extra"}
POSSESSIVE = {"his", "her", "their", "its"}


def _group(word):
    w = word.lower()
    for g in OBJECT_GROUPS:
        if w in g:
            return sorted(g)[0]
    return None


def places_overlap(a, b):
    return a == b or a in b or b in a


@dataclass
class Act:
    cls: str
    lemma: str
    negated: bool = False
    actor: str = None
    patient: str = None
    passive: bool = False
    objects: set = field(default_factory=set)


@dataclass
class Frame:
    text: str
    speaker: str = None
    stance: dict = field(default_factory=dict)
    acts: list = field(default_factory=list)
    people: list = field(default_factory=list)
    places: set = field(default_factory=set)
    objects: set = field(default_factory=set)
    times: list = field(default_factory=list)
    t_at: int = None
    t_from: int = None
    t_until: int = None
    stop_time: int = None
    days: set = field(default_factory=set)
    explicit_day: bool = False
    exclusive: bool = False
    empty_places: set = field(default_factory=set)
    possessive_obj: bool = False
    scope_words: set = field(default_factory=set)
    approx: bool = False

    def acts_of(self, *classes, negated=None):
        return [a for a in self.acts if a.cls in classes and (negated is None or a.negated == negated)]

    def summary(self):
        return {"speaker": self.speaker, "stance": self.stance.get("stance"), "people": self.people,
                "places": sorted(self.places), "objects": sorted(self.objects),
                "times": [t.label() for t in self.times], "days": sorted(self.days),
                "acts": [{"class": a.cls, "lemma": a.lemma, "negated": a.negated, "actor": a.actor,
                          "patient": a.patient} for a in self.acts]}


def _lemma(tok):
    low = tok.lower_
    if low in IRREGULAR:
        return IRREGULAR[low]
    lem = (tok.lemma_ or low).lower()
    return lem if lem and lem != "-pron-" else low


_FRAME_CACHE = {}


def build_frame(text: str, lex: CaseLexicon, speaker: str = None, default_day: str = None) -> Frame:
    key = (id(lex), text, speaker, default_day)
    if key not in _FRAME_CACHE:
        if len(_FRAME_CACHE) > 4000:
            _FRAME_CACHE.clear()
        _FRAME_CACHE[key] = _build_frame(text, lex, speaker, default_day)
    return _FRAME_CACHE[key]


def _build_frame(text: str, lex: CaseLexicon, speaker: str = None, default_day: str = None) -> Frame:
    nlp = get_nlp()
    doc = nlp(text)
    fr = Frame(text=text, speaker=speaker)
    fr.stance = classify(text.split(".")[0] if len(text.split(".")) > 1 and classify(text)["stance"] == "statement" else text)
    # a passage is "assumption" / "absence" if any of its sentences is
    stances = [classify(s.text) for s in doc.sents if s.text.strip()]
    for st in stances:
        if st["stance"] in ("assumption", "absence_of_observation", "hearsay"):
            fr.stance = st
            break
    else:
        fr.stance = next((s for s in stances if s["stance"] == "direct_observation"), stances[0] if stances else {"stance": "statement"})
    res = resolve(text, lex, speaker)
    spans = []
    for cl in res["clusters"]:
        for m in cl["mentions"]:
            spans.append((m["start"], m["end"], cl["person"], m["kind"]))
    spans.sort()
    fr.people = sorted({s[2] for s in spans})
    low = text.lower()
    fr.places = {p.lower() for p in sorted(lex.places, key=len, reverse=True) if p.lower() in low}
    # drop places subsumed by a longer one only for display; keep both for overlap checks
    for t in doc:
        g = _group(t.lemma_ if t.lemma_ else t.text) or _group(t.text)
        if g and t.pos_ in ("NOUN", "PROPN", "") or (g and t.pos_ == "X"):
            fr.objects.add(g)
    for ph in ("loving cup", "key cabinet"):
        if ph in low:
            fr.objects.add(_group(ph))
    fr.objects.discard(None)
    # days
    days = [d for d in extract_days(text) if d in WEEKDAYS]
    fr.days = set(days) if days else ({default_day} if default_day else set())
    fr.explicit_day = bool(days)
    fr.exclusive = bool(re.search(r"\b(no one else|nobody else|no other|only I|alone)\b", low))
    fr.possessive_obj = bool(re.search(r"\b(touched|held|had|used|took)\s+(?:\w+\s+)?(?:his|her|their)\s+(?:\w+\s+)?key", low))
    fr.scope_words = {w for w in SCOPE_WORDS if re.search(r"\b%s\b" % w, low)}
    # times and interval roles
    fr.times = [t for t in extract_times(text) if t.minutes is not None]
    pts = [t for t in fr.times if t.qualifier not in ("until", "till")]
    untl = [t for t in fr.times if t.qualifier in ("until", "till")]
    if pts:
        fr.t_at = pts[0].sort_minutes if pts[0].sort_minutes is not None else pts[0].minutes
        fr.approx = pts[0].precision != "exact"
    if untl:
        fr.t_until = untl[0].sort_minutes if untl[0].sort_minutes is not None else untl[0].minutes
        fr.t_from = fr.t_at
    # stop time: the time mention right after a "stopped" token
    m = re.search(r"stopped\s+(?:at\s+)?", low)
    if m:
        after = [t for t in fr.times if t.start >= m.start()]
        if after:
            fr.stop_time = after[0].sort_minutes if after[0].sort_minutes is not None else after[0].minutes
    # empty / nobody
    if re.search(r"\b(empty|deserted|unoccupied)\b|\b(nobody|no one) (was|is) (at|in)\b", low):
        fr.empty_places = set(fr.places)

    def person_before(char_pos, limit_sent=None):
        best = None
        for s, e, key, kind in spans:
            if e <= char_pos:
                best = key
        return best

    def spans_between(char_pos, key):
        """True if the person `key` is mentioned within a few characters after char_pos (the agent right after 'by')."""
        return any(k == key and 0 <= st - char_pos <= 24 for st, e, k, kind in spans)

    def person_after(char_pos):
        for s, e, key, kind in spans:
            if s >= char_pos:
                return key
        return None

    for tok in doc:
        if tok.pos_ not in ("VERB", "AUX", "NOUN", "") and tok.lower_ not in IRREGULAR:
            continue
        lem = _lemma(tok)
        cls = LEMMA_TO_CLASS.get(lem)
        if lem == "post" and tok.pos_ == "NOUN":
            cls = "PRESENT"
        if lem == "step" and any(c.lower_ in ("down", "out") for c in tok.rights):
            cls = "MOVE_OUT"
        if lem == "get" and any(c.lower_ == "off" for c in tok.rights):
            cls = "MOVE_OUT"
        if lem == "be" and tok.pos_ == "AUX" and not any(c.dep_ in ("attr", "prep") for c in tok.children):
            continue
        if lem == "be" and any(c.lower_ in {"at", "in", "near", "by", "inside"} for c in tok.rights):
            cls = "PRESENT"
        if cls is None or cls == "ASSUME":
            continue
        neg = any(c.dep_ == "neg" or c.lower_ in ("never", "not", "n't") for c in tok.children) or \
            bool(re.search(r"\b(never|not|n't|didn't)\s*(?:\w+\s+){0,2}$", text[max(0, tok.idx - 45):tok.idx].lower()))
        passive = any(c.dep_ in ("auxpass",) for c in tok.children) or (tok.tag_ == "VBN" and any(c.lower_ == "was" for c in tok.lefts))
        actor = None
        by = [t for t in doc[tok.i + 1: tok.i + 5] if t.lower_ == "by"]
        if by and (passive or tok.tag_ == "VBN" or tok.lower_.endswith("ed") or tok.lower_ in IRREGULAR):
            cand = person_after(by[0].idx)
            if cand and spans_between(by[0].idx, cand):
                actor, passive = cand, True
        if actor is None:
            actor = person_before(tok.idx) or speaker
        patient = person_after(tok.idx + len(tok.text)) if cls == "SEE" else None
        act_objs = set()
        for c in list(tok.rights) + [x for x in tok.subtree]:
            g = _group(c.lemma_ or c.text)
            if g and c.i > tok.i:
                act_objs.add(g)
        if cls == "SEE" and passive and patient is None:
            patient, actor = actor, None          # "Mr. Black was seen at the garden door": Black is the one seen
        fr.acts.append(Act(cls, lem, neg, actor, patient, passive, act_objs))
    # elliptical negation: "... I had touched the emerald, and I did not."  => negated copy of the last act
    for sent in doc.sents:
        if re.search(r"\b(did not|didn't|never did|did none)\s*[.;]?\s*$", sent.text.strip().lower()):
            prior = [a for a in fr.acts if not a.negated and a.cls in ("TOUCH", "MOVE_OUT", "GO_TO", "PRESENT")]
            if prior:
                last = prior[-1]
                fr.acts.append(Act(last.cls, last.lemma, True, speaker or last.actor, None, False, set(last.objects)))
    return fr
