from django import template
from django.template.loader import render_to_string
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from game import portraits
from game.themes import DOC_KIND, ROMAN, THEMES

register = template.Library()

INSTRUMENTS = [
    ("retrieval", "Case Search", "Semantic retrieval", "Finds evidence by meaning, not keywords."),
    ("nli", "Contradiction Scales", "Natural-language inference", "Weighs two statements: contradict, support or neither."),
    ("ner", "Entity Markers", "Named-entity recognition", "Colours the people, places, objects and times in a text."),
    ("time", "Chronometer", "Temporal extraction", "Turns every time phrase into a timeline entry."),
    ("coref", "Red Thread", "Coreference resolution", "Follows 'he', 'she', 'the passenger' back to a real person."),
    ("stance", "Witness Lens", "Epistemic stance", "Seen it, heard it, or only assumed it?"),
    ("leakage", "Keyhole", "Information-leakage detection", "Spots details that only a private source could supply."),
    ("eval", "Verdict Seal", "Semantic answer evaluation", "Checks your reasoning by meaning, not wording."),
]


@register.simple_tag
def portrait(suspect, size=120):
    return mark_safe(portraits.build(suspect, int(size)))


@register.simple_tag
def case_art(number):
    return mark_safe(render_to_string(f"game/art/cover_{int(number)}.html"))


@register.simple_tag
def hero_art():
    return mark_safe(render_to_string("game/art/hero.html"))


@register.simple_tag
def icon(name, cls=""):
    return format_html('<svg class="ic {}" aria-hidden="true"><use href="#i-{}"/></svg>', cls, name)


@register.simple_tag
def instrument_chip(key):
    for k, name, tech, _ in INSTRUMENTS:
        if k == key:
            return format_html('<span class="ins-chip" data-ins="{}">{}<b>{}</b></span>', k, icon(k), name)
    return ""


@register.simple_tag
def instruments():
    return INSTRUMENTS


@register.filter
def theme(number):
    return THEMES.get(int(number or 0), {})


@register.filter
def roman(number):
    return ROMAN.get(int(number or 0), str(number))


@register.filter
def pips(level, total=5):
    """Difficulty text -> filled pips."""
    n = {"easy": 1, "medium": 2, "medium-hard": 3, "hard": 4, "very hard": 5}.get(str(level).lower(), 2)
    return mark_safe("".join(f'<i class="pip{" on" if i < n else ""}"></i>' for i in range(int(total))))


@register.filter
def dockind(doc_type):
    return DOC_KIND.get(str(doc_type).lower(), "note")


@register.filter
def docicon(doc_type):
    return {"letter": "letter", "telegram": "telegram", "register": "ledger", "diary": "diary", "newspaper": "newspaper", "plan": "plan",
            "receipt": "receipt", "schedule": "schedule"}.get(str(doc_type).lower(), "file")


@register.filter
def stanceicon(stance):
    return {"direct_observation": "eye", "hearsay": "ear", "assumption": "thought", "absence_of_observation": "void", "denial": "denial"}.get(stance, "thought")


@register.filter
def mmss(seconds):
    seconds = int(seconds or 0)
    return f"{seconds // 60}:{seconds % 60:02d}"


@register.filter
def get_item(d, key):
    return d.get(key) if d else None


@register.filter
def nice(value):
    return str(value).replace("_", " ").capitalize()
