"""Load the YAML case files into the database (idempotent)."""
import yaml
from pathlib import Path
from django.conf import settings
from django.db import transaction
from .models import Case, CaseSolution, EvidenceDocument, Hint, Statement, Suspect


def reflow(text: str) -> str:
    """Undo hard line-wraps inside paragraphs (authoring artefact) but keep register/list lines separate."""
    lines, out = text.split("\n"), []
    for ln in lines:
        prev = out[-1] if out else None
        if (prev is not None and ln.strip() and len(prev) >= 70 and prev[-1] not in '.:;!?"\u201d)' and
                not ln.lstrip()[0].isdigit()):
            out[-1] = prev.rstrip() + " " + ln.strip()
        else:
            out.append(ln)
    return "\n".join(out)


def case_files():
    return sorted(Path(settings.MYSTIQ["CASES_DIR"]).glob("case*.yaml"))


@transaction.atomic
def load_case_file(path):
    d = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    case, _ = Case.objects.update_or_create(number=d["number"], defaults=dict(
        slug=d["slug"], title=d["title"], difficulty=d["difficulty"], setting=d["setting"],
        summary=d["summary"].strip(), introduction=d["introduction"].strip(), objective=d["objective"].strip(),
        places=d.get("places", []), case_objects=d.get("objects", []), others=d.get("others", [])))
    CaseSolution.objects.update_or_create(case=case, defaults={"data": d["solution"]})
    keep = []
    for i, s in enumerate(d["suspects"]):
        obj, _ = Suspect.objects.update_or_create(case=case, key=s["key"], defaults=dict(
            name=s["name"], role=s["role"], gender=s.get("gender", "m"), age=s.get("age", 40),
            aliases=s.get("aliases", []), background=s["background"].strip(), motive=s["motive"].strip(),
            relationship=s["relationship"].strip(), whereabouts=s["whereabouts"].strip(),
            personality=s["personality"].strip(), private_knowledge=s["private_knowledge"].strip(),
            does_not_know=s.get("does_not_know", "").strip(), deflect=s.get("deflect", "").strip(),
            topics=s.get("topics", []), order=i))
        keep.append(obj.key)
    case.suspects.exclude(key__in=keep).delete()
    sus = {s.key: s for s in case.suspects.all()}
    keep = []
    for i, dd in enumerate(d["documents"]):
        EvidenceDocument.objects.update_or_create(case=case, key=dd["key"], defaults=dict(
            title=dd["title"], doc_type=dd["doc_type"], datetime_text=dd["datetime"], author=dd["author"],
            suspect=sus.get(dd.get("suspect")), content=reflow(dd["content"].strip()), order=i))
        keep.append(dd["key"])
    case.documents.exclude(key__in=keep).delete()
    docs = {x.key: x for x in case.documents.all()}
    case.statements.all().delete()
    for i, st in enumerate(d["statements"]):
        Statement.objects.create(case=case, suspect=sus[st["suspect"]], document=docs.get(st.get("doc")),
                                 text=st["text"].strip(), order=i)
    case.hints.all().delete()
    for i, h in enumerate(d["hints"], 1):
        Hint.objects.create(case=case, order=i, text=h.strip())
    return case


def load_all(with_timeline=True):
    from nlp_engine.lexicon import clear_lexicon_cache
    from nlp_engine.timeline import rebuild_timeline
    cases = [load_case_file(p) for p in case_files()]
    clear_lexicon_cache()
    if with_timeline:
        for c in cases:
            rebuild_timeline(c)
    return cases
