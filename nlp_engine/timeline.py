"""Timeline construction by temporal information extraction over the case documents.

Every line of every document that carries a time expression becomes a candidate event. Events are tagged as
`record` (registers, schedules, reports) or `claim` (statements, diaries, letters), grouped by the day they refer to,
and ambiguous / approximate / AM-PM-inferred times are flagged rather than silently trusted.
"""
import re
from .spacy_loader import get_nlp
from .temporal import extract_times, extract_days, minutes_label, WEEKDAYS

CLAIM_TYPES = {"Statement", "Diary", "Letter", "Note", "Telegram"}
_DAY_HEADING = re.compile(r"^\s*(mon|tue|wed|thu|fri|sat|sun)[a-z]*\.?,?\s+\d{1,2}", re.I)
_LEAD = re.compile(r"^\s*((?:(?:mon|tue|wed|thu|fri|sat|sun)[a-z]*\.?\s+\d{1,2}\s+[A-Za-z]+\.?\s*[—–-]+\s*)?\d{1,2}[:.]\d{2}\s*(?:[AP]M)?\s*[—–-]+\s*)", re.I)
_ABBR = {"mon": "monday", "tue": "tuesday", "wed": "wednesday", "thu": "thursday", "fri": "friday",
         "sat": "saturday", "sun": "sunday"}


def _clean(line):
    line = _LEAD.sub("", line.strip())
    line = re.sub(r"\s+", " ", line)
    return line[:220] + ("…" if len(line) > 220 else "")


def build_events(documents):
    """documents: iterable of objects with .key .doc_type .content .title. Returns list of event dicts."""
    nlp = get_nlp()
    events = []
    for doc in documents:
        day = ""
        etype = "claim" if doc.doc_type in CLAIM_TYPES else "record"
        for raw in doc.content.splitlines():
            line = raw.strip()
            if not line:
                continue
            if _DAY_HEADING.match(line) and not extract_times(line):
                day = _ABBR[line[:3].lower()]
                continue
            for sent in nlp(line).sents:
                st = sent.text.strip()
                if not st:
                    continue
                ctx = ""   # sentence-level cues only; document-wide cues mislead (mixed AM/PM documents)
                mentions = [m for m in extract_times(st, ctx) if m.minutes is not None]
                if not mentions:
                    continue
                m = mentions[0]
                days = [d for d in extract_days(st) if d in WEEKDAYS]
                lead = re.match(r"^\s*(mon|tue|wed|thu|fri|sat|sun)[a-z]*\.?,?\s+\d{1,2}", st, re.I)
                if lead and not days:
                    days = [_ABBR[lead.group(1).lower()]]
                day_label = days[0] if days else day
                note = m.note
                if m.precision != "exact":
                    note = (note + "; " if note else "") + f"{m.precision} time ('{m.qualifier or 'about'}')"
                events.append({
                    "doc_key": doc.key, "sort_minutes": m.sort_minutes if m.sort_minutes is not None else m.minutes,
                    "time_label": m.label(), "text": _clean(st), "event_type": etype,
                    "day_label": day_label, "precision": m.precision,
                    "ambiguous": bool(m.ambiguous and m.meridiem_inferred and not m.note.startswith("midnight")),
                    "note": note[:200]})
    # deduplicate near-identical events (same time and same text)
    seen, out = set(), []
    for e in sorted(events, key=lambda e: (e["day_label"] != "", e["day_label"], e["sort_minutes"])):
        k = (e["day_label"], e["sort_minutes"], e["text"][:60])
        if k in seen:
            continue
        seen.add(k)
        out.append(e)
    return out


def rebuild_timeline(case):
    from cases.models import TimelineEvent
    docs = list(case.documents.all())
    by_key = {d.key: d for d in docs}
    case.timeline.all().delete()
    rows = []
    for e in build_events(docs):
        rows.append(TimelineEvent(case=case, sort_minutes=e["sort_minutes"], time_label=e["time_label"],
                                  text=e["text"], source=by_key[e["doc_key"]], event_type=e["event_type"],
                                  day_label=e["day_label"], precision=e["precision"], ambiguous=e["ambiguous"],
                                  note=e["note"]))
    TimelineEvent.objects.bulk_create(rows)
    return len(rows)
