"""Shared text preprocessing for indexing and querying: time normalisation tokens, lemmatisation, synonym folding."""
import re
from functools import lru_cache
from nlp_engine.spacy_loader import get_nlp
from nlp_engine.temporal import annotate_times

# Synonym groups: every member is folded to the first token. These are domain (detective-narrative) paraphrase classes
# that let the local embedder match "was Blake still around the library after nine" to "I observed Mr. Blake near the
# library entrance at nine twenty".
SYNONYMS = [
    ["see", "observe", "notice", "spot", "glimpse", "witness", "watch", "view", "sight", "look"],
    ["leave", "depart", "exit", "go", "quit", "withdraw", "alight", "step"],
    ["enter", "arrive", "come", "return", "go"],
    ["near", "by", "beside", "close", "around", "next", "outside"],
    ["inside", "within", "in"],
    ["steal", "take", "remove", "snatch", "pilfer", "rob", "disappear", "vanish", "missing", "gone", "lose"],
    ["lock", "bolt", "fasten", "secure", "latch"],
    ["say", "state", "tell", "claim", "declare", "assert", "report", "assume", "suppose", "think", "believe"],
    ["letter", "note", "message", "telegram", "memorandum", "correspondence"],
    ["evidence", "clue", "document", "record", "register", "log", "ledger"],
    ["suspect", "culprit", "thief", "criminal", "guilty", "responsible"],
    ["owe", "debt", "money", "financial", "pound", "payment", "creditor"],
    ["quarrel", "disagree", "dispute", "argue", "disagreement", "angry", "grudge"],
    ["library", "reading room"],
    ["servant", "caretaker", "butler", "footman", "maid", "housekeeper"],
    ["room", "chamber", "study", "office", "workshop"],
    ["clock", "watch", "timepiece", "regulator"],
    ["key", "keys", "spare"],
    ["alone", "unaccompanied", "solitary"],
    ["motive", "reason", "why", "benefit", "gain"],
]
_FOLD = {}
for g in SYNONYMS:
    for w in g:
        _FOLD.setdefault(w, g[0])

_STOP = set("a an the and or of to in on at is was were be been being am are it its this that these those i me my we our you your "
            "he him his she her they them their do does did have has had with for from as by not no but if so than then there "
            "which who whom what when where how can could would should will shall may might must".split())
_NUMTOK = re.compile(r"^t\d{4}$")


def tokens(text: str):
    """Lemmatised, synonym-folded content tokens (time tokens like t2120 kept)."""
    text = annotate_times(text)
    doc = get_nlp()(text)
    out = []
    for t in doc:
        w = t.text.lower()
        if _NUMTOK.match(w):
            out.append(w)
            continue
        if t.is_punct or t.is_space:
            continue
        lem = (t.lemma_ or w).lower()
        if lem in _STOP or w in _STOP:
            continue
        lem = _FOLD.get(lem, _FOLD.get(w, lem))
        if len(lem) > 1:
            out.append(lem)
    return out


@lru_cache(maxsize=4096)
def prep(text: str) -> str:
    return " ".join(tokens(text))
