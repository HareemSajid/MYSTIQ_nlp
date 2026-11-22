"""Contextual question understanding: intent, entities and time constraints of a player's question."""
import re
from .lexicon import CaseLexicon
from .ner import extract_entities
from .temporal import extract_times

INTENTS = [
    ("contradiction", r"\b(contradict|inconsisten|conflict|lie|lying|lied|doesn't match|does not match|don't match|change(d)? (his|her|your) story|mismatch|suspicious)\b"),
    ("where", r"\b(where|which room|what place)\b"),
    ("when", r"\b(when|what time|at what time|how long|what hour|before|after)\b|\bat \d"),
    ("who", r"\b(who|whom|whose)\b"),
    ("motive", r"\b(why|motive|reason|benefit|gain|debt|money|owe)\b"),
    ("access", r"\b(access|key|keys|enter|entered|locked|unlock|door)\b"),
    ("observation", r"\b(see|saw|seen|observe|notice|witness|watch|hear|heard)\b"),
    ("timeline", r"\b(timeline|sequence|order of events|chronolog)\b"),
]


def understand(question: str, lex: CaseLexicon, context: str = ""):
    q = question.strip()
    ents = extract_entities(q, lex)
    times = [t for t in extract_times(q, context) if t.minutes is not None]
    intents = [name for name, pat in INTENTS if re.search(pat, q, re.I)]
    people = []
    for e in ents:
        if e["label"] == "PERSON" and e.get("key") and e["key"] not in people:
            people.append(e["key"])
    return {"question": q, "intents": intents or ["lookup"], "primary_intent": (intents or ["lookup"])[0],
            "people": people,
            "places": [e["text"].lower() for e in ents if e["label"] == "LOCATION"],
            "objects": [e["text"].lower() for e in ents if e["label"] == "OBJECT"],
            "times": [{"text": t.text, "label": t.label(), "minutes": t.minutes, "token": t.token(),
                       "ambiguous": t.ambiguous} for t in times],
            "entities": ents}
