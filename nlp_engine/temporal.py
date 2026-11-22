"""Temporal information extraction and normalisation.

Handles: 9:20 PM, 9.20, 9 PM, "nine twenty", "twenty past eight", "half past nine", "a quarter to ten",
"five minutes to midnight", "nine o'clock", "at ten", "midnight", "noon", and weekday / date references.
Each mention is normalised to minutes from midnight, with a precision and an ambiguity flag so that
vague or incomplete references ("shortly before", bare "ten") never produce false certainty.
"""
import re
from dataclasses import dataclass, asdict, field
from typing import Optional

UNITS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
         "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
         "eighteen": 18, "nineteen": 19}
TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50}
_NUM = r"(?:(?:twenty|thirty|forty|fifty)(?:[- ](?:one|two|three|four|five|six|seven|eight|nine))?|%s)" % "|".join(UNITS)
_NUMQ = r"(?:a quarter|quarter|half|%s)" % _NUM
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
          "november", "december"]


def word_to_int(w):
    w = w.lower().strip().replace("-", " ")
    if w in UNITS:
        return UNITS[w]
    parts = w.split()
    if parts and parts[0] in TENS:
        return TENS[parts[0]] + (UNITS.get(parts[1], 0) if len(parts) > 1 else 0)
    return None


@dataclass
class TimeMention:
    text: str
    start: int
    end: int
    minutes: Optional[int]          # 0..1439 (None if unresolvable)
    kind: str = "clock"             # clock | word | relative | day
    precision: str = "exact"        # exact | approximate | vague
    ambiguous: bool = False
    meridiem_inferred: bool = False
    qualifier: str = ""             # about | before | after | until | from
    note: str = ""
    sort_minutes: Optional[int] = None

    def label(self):
        if self.minutes is None:
            return self.text
        h, m = divmod(self.minutes, 60)
        suffix = "AM" if h < 12 else "PM"
        h12 = h % 12 or 12
        return f"{h12}:{m:02d} {suffix}"

    def token(self):
        return "t%04d" % (self.minutes // 60 * 100 + self.minutes % 60) if self.minutes is not None else ""

    def to_dict(self):
        d = asdict(self)
        d["label"] = self.label()
        return d


_RE_CLOCK = re.compile(r"\b(\d{1,2})[:.](\d{2})\s*(a\.?m\.?|p\.?m\.?)?(?![\d])", re.I)
_RE_HOUR_AMPM = re.compile(r"\b(\d{1,2})\s*(a\.?m\.?|p\.?m\.?)(?=\W|$)", re.I)
_RE_PAST = re.compile(r"\b(%s)(?:\s+minutes)?\s+(past|to)\s+(%s)\b" % (_NUMQ, _NUM), re.I)
_RE_OCLOCK = re.compile(r"\b(%s)\s+o'?clock\b" % _NUM, re.I)
_RE_WORDPAIR = re.compile(r"\b(%s)\s+(%s)\b" % (_NUM, r"(?:twenty|thirty|forty|fifty)(?:[- ](?:one|two|three|four|five|six|seven|eight|nine))?|ten|fifteen|five|(?:one|two|three|four|five|six|seven|eight|nine)"), re.I)
_RE_BARE = re.compile(r"\b(at|until|till|by|before|after|about|towards|strike|strikes|struck|striking)\s+(%s)\b(?!\s+(?:pounds|guineas|minutes|years|days|degrees|men|people|shillings|tons|ton|feet|of|per|hundred|thousand))" % _NUM, re.I)
_RE_SPECIAL = re.compile(r"\b(midnight|noon|first light)\b", re.I)
_RE_DAY = re.compile(r"\b(%s)\b" % "|".join(w.capitalize() for w in WEEKDAYS))
_RE_DATE = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(%s)(?:\s+(\d{4}))?\b" % "|".join(m.capitalize() for m in MONTHS))
_RE_QUAL = re.compile(r"(about|around|approximately|roughly|shortly before|shortly after|just before|just after|"
                      r"before|after|until|till|from|at about|towards)\s*$", re.I)
_MORNING = re.compile(r"\b(morning|dawn|first light|breakfast|a\.m\.|am)\b", re.I)
_EVENING = re.compile(r"\b(evening|night|dinner|supper|p\.m\.|pm|toast|lecture|theatre|tonight)\b", re.I)
_AFTERNOON = re.compile(r"\b(afternoon)\b", re.I)


def _meridiem(hour, mer, ctx):
    """Return (hour24, inferred, ambiguous). `ctx` is (sentence_text, fallback_context)."""
    sent, fallback = ctx
    if mer:
        pm = mer.lower().startswith("p")
        if hour == 12:
            return (12 if pm else 0), False, False
        return (hour + 12 if pm else hour), False, False
    if hour > 12:
        return hour, False, False
    for c in (sent, fallback):
        if _MORNING.search(c):
            return (0 if hour == 12 else hour), True, False
        if _EVENING.search(c) or _AFTERNOON.search(c):
            return (12 if hour == 12 else hour + 12), True, False
    # No cue: bare hours are assumed PM in these evening-set cases but flagged ambiguous.
    if 7 <= hour <= 11 or hour in (12,):
        return (hour + 12 if hour != 12 else 12), True, True
    return hour + 12, True, True


def extract_times(text: str, context: str = "") -> list:
    """Extract all clock-time mentions from `text`. `context` (e.g. the sentence/document) guides AM/PM inference."""
    ctx = (text, context)
    found, taken = [], []

    def free(s, e):
        return all(e <= a or s >= b for a, b in taken)

    def add(m, minutes, kind, precision="exact", amb=False, inf=False, note=""):
        s, e = m.start(), m.end()
        if text[s:e].endswith(".") and not re.search(r"[ap]\.m\.$", text[s:e], re.I):
            e -= 1          # a sentence-final full stop is not part of "7:46 PM."
        if not free(s, e):
            return
        qual = ""
        q = _RE_QUAL.search(text[max(0, s - 22):s])
        if q:
            qual = q.group(1).lower()
        if qual in ("about", "around", "approximately", "roughly", "at about", "towards") and precision == "exact":
            precision = "approximate"
        if qual in ("shortly before", "shortly after", "just before", "just after"):
            precision = "approximate"
        mm = TimeMention(text[s:e], s, e, minutes % 1440 if minutes is not None else None, kind, precision, amb, inf,
                         qual, note)
        if minutes is not None:
            sm = minutes
            if (minutes < 5 * 60 and not inf) or "midnight" in text[s:e].lower() and False:
                sm = minutes + 1440
            mm.sort_minutes = sm
        found.append(mm)
        taken.append((s, e))

    for m in _RE_CLOCK.finditer(text):
        h, mi = int(m.group(1)), int(m.group(2))
        if h > 24 or mi > 59:
            continue
        h24, inf, amb = _meridiem(h, m.group(3), ctx)
        add(m, h24 * 60 + mi, "clock", amb=amb, inf=inf, note="AM/PM inferred from context" if inf else "")
    for m in _RE_HOUR_AMPM.finditer(text):
        h = int(m.group(1))
        if h > 12:
            continue
        h24, inf, amb = _meridiem(h, m.group(2), ctx)
        add(m, h24 * 60, "clock")
    for m in _RE_PAST.finditer(text):
        qty, rel, hr = m.group(1).lower(), m.group(2).lower(), word_to_int(m.group(3))
        if hr is None or hr > 12:
            continue
        mins = 15 if qty in ("a quarter", "quarter") else 30 if qty == "half" else word_to_int(qty)
        if mins is None or (qty == "half" and rel == "to"):
            continue
        h24, inf, amb = _meridiem(hr, None, ctx)
        if rel == "past":
            total = h24 * 60 + mins
        else:
            total = h24 * 60 - mins
        add(m, total, "word", amb=amb, inf=inf, note="AM/PM inferred from context" if inf else "")
    for m in re.finditer(r"\b(%s)(?:\s+minutes)?\s+(past|to)\s+(midnight|noon)\b" % _NUMQ, text, re.I):
        qty = m.group(1).lower()
        mins = 15 if qty in ("a quarter", "quarter") else 30 if qty == "half" else word_to_int(qty)
        base = 0 if m.group(3).lower() == "midnight" else 720
        if mins is not None:
            add(m, base + (mins if m.group(2).lower() == "past" else -mins), "word")
            if base == 0:
                found[-1].sort_minutes = 1440 + (mins if m.group(2).lower() == "past" else -mins)
    for m in _RE_OCLOCK.finditer(text):
        hr = word_to_int(m.group(1))
        if hr and hr <= 12:
            h24, inf, amb = _meridiem(hr, None, ctx)
            add(m, h24 * 60, "word", amb=amb, inf=inf, note="AM/PM inferred from context" if inf else "")
    for m in _RE_WORDPAIR.finditer(text):
        # "nine twenty", "ten forty-five" -- only when a clock-like hour word comes first
        hr, mi = word_to_int(m.group(1)), word_to_int(m.group(2))
        if hr and mi is not None and 1 <= hr <= 12 and 10 <= mi <= 59 and not re.search(r"(past|to)\s*$", text[:m.start()], re.I):
            h24, inf, amb = _meridiem(hr, None, ctx)
            add(m, h24 * 60 + mi, "word", amb=amb, inf=inf, note="AM/PM inferred from context" if inf else "")
    for m in _RE_SPECIAL.finditer(text):
        w = m.group(1).lower()
        if w == "midnight":
            n_before = len(found)
            add(m, 0, "word", note="midnight")
            if len(found) > n_before:
                found[-1].sort_minutes = 1440
        elif w == "noon":
            add(m, 720, "word")
        else:
            add(m, 6 * 60, "relative", precision="vague", amb=True, note="'first light' is only approximately dawn")
    for m in _RE_BARE.finditer(text):
        hr = word_to_int(m.group(2))
        if not hr or hr > 12:
            continue
        s, e = m.start(2), m.end(2)
        if not free(s, e):
            continue
        h24, inf, amb = _meridiem(hr, None, ctx)

        class _M:  # span proxy limited to the number word itself
            def __init__(self): self._s, self._e = s, e
            def start(self): return self._s
            def end(self): return self._e
        add(_M(), h24 * 60, "word", amb=True, inf=True, note="bare hour; AM/PM and exact time inferred from context")
        found[-1].qualifier = m.group(1).lower() if found[-1].qualifier == "" else found[-1].qualifier
    found.sort(key=lambda t: t.start)
    return found


def extract_days(text: str) -> list:
    """Weekday names and dates mentioned in the text, lower-cased weekday names plus raw date strings."""
    days = [m.group(1).lower() for m in _RE_DAY.finditer(text)]
    dates = [m.group(0) for m in _RE_DATE.finditer(text)]
    return days + dates


def annotate_times(text: str, mentions=None):
    """Append canonical time tokens (t2120) after each time expression, for embedding/BM25 indexing."""
    mentions = mentions if mentions is not None else extract_times(text)
    out, last = [], 0
    for m in mentions:
        if m.minutes is None:
            continue
        out.append(text[last:m.end])
        out.append(" " + m.token())
        last = m.end
    out.append(text[last:])
    return "".join(out)


def minutes_label(minutes):
    return TimeMention("", 0, 0, minutes % 1440).label()
