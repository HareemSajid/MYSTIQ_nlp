"""Case lexicon: people, aliases, places and objects of one case, used by NER, coreference and frame extraction."""
import re
from dataclasses import dataclass, field
from functools import lru_cache

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


@dataclass
class Person:
    key: str
    name: str
    gender: str            # m | f | ?
    role: str
    aliases: list
    is_suspect: bool = False


@dataclass
class CaseLexicon:
    people: list = field(default_factory=list)
    places: list = field(default_factory=list)
    objects: list = field(default_factory=list)
    incident_day: str = ""        # weekday the main events occur on (from the case setting)

    @classmethod
    def from_parts(cls, suspects, others, places, objects, setting=""):
        people = []
        for s in suspects:
            names = [s["name"]] + list(s.get("aliases", []))
            people.append(Person(s["key"], s["name"], s.get("gender", "?"), s.get("role", ""),
                                 _expand(names, s["name"]), True))
        for o in others:
            people.append(Person(slug(o["name"]), o["name"], o.get("gender", "?"), o.get("role", ""),
                                 _expand([o["name"]] + list(o.get("aliases", [])), o["name"]), False))
        days = re.findall(r"(%s)" % "|".join(w.capitalize() for w in WEEKDAYS), setting or "")
        # a single named weekday = the incident day; several (multi-day case) = no default day assumed
        return cls(people, list(places), list(objects), days[0].lower() if len(set(days)) == 1 else "")

    @classmethod
    def from_case(cls, case):
        sus = [{"key": s.key, "name": s.name, "gender": s.gender, "role": s.role, "aliases": s.aliases}
               for s in case.suspects.all()]
        return cls.from_parts(sus, case.others, case.places, case.case_objects, case.setting)

    def person_by_key(self, key):
        return next((p for p in self.people if p.key == key), None)

    def person_for_text(self, text):
        t = text.lower().strip(" .,;:")
        best, best_len = None, 0
        for p in self.people:
            for a in p.aliases:
                if a == t and len(a) > best_len:
                    best, best_len = p, len(a)
        return best

    def all_alias_patterns(self):
        """(alias_lower, person_key) pairs, longest first."""
        pairs = [(a, p.key) for p in self.people for a in p.aliases]
        return sorted(set(pairs), key=lambda x: -len(x[0]))


_TITLES = re.compile(r"^(mr|mrs|miss|dr|sir|lady|lord|captain|inspector|colonel)\.?\s+", re.I)


def _expand(names, full):
    out = set()
    for n in names:
        n = n.strip()
        if not n:
            continue
        out.add(n.lower())
        stripped = _TITLES.sub("", n)
        if stripped != n:
            out.add(stripped.lower())
    parts = full.split()
    if len(parts) >= 2:
        out.add(parts[-1].lower())
        out.add(parts[0].lower().rstrip("."))
        if parts[0].lower().rstrip(".") in {"mr", "mrs", "dr", "sir", "lady", "lord", "captain"}:
            out.add(f"{parts[0].lower().rstrip('.')}. {parts[-1].lower()}")
            out.add(f"{parts[0].lower().rstrip('.')} {parts[-1].lower()}")
    return sorted(a for a in out if len(a) > 1)


@lru_cache(maxsize=32)
def lexicon_for_case_id(case_id):
    from cases.models import Case
    return CaseLexicon.from_case(Case.objects.prefetch_related("suspects").get(pk=case_id))


def clear_lexicon_cache():
    lexicon_for_case_id.cache_clear()
