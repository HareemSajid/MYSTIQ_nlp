"""Epistemic stance of a sentence: did the speaker directly observe it, assume it, or only hear it?

This is what separates "I saw Richard return the emerald" (observation) from "I assumed Richard had returned the
emerald" (assumption) -- the central NLP challenge of the first case.
"""
import re

OBSERVE = re.compile(r"\bI\s+(?:\w+\s+)?(saw|observed|noticed|watched|heard|spotted|witnessed|found|viewed|looked at|"
                     r"stood|called|noted)\b", re.I)
ASSUME = re.compile(r"\b(I\s+(?:\w+\s+)?(assumed|supposed|presumed|thought|believed|imagined|guessed|took it|reckoned|"
                    r"fancied|understood)|must have|probably|presumably|perhaps|surely|I\s+think|it seems|seemed to|"
                    r"I\s+took\s+(?:it|him|her|them)\s+to\s+be)\b", re.I)
HEARSAY = re.compile(r"\b(told me|I was told|\w+\s+says\s+that|they say|I\s+heard\s+that|\w+\s+said\s+that|"
                     r"according to|so\s+\w+\s+says|servants say|Pym says)\b", re.I)
ACTION = re.compile(r"\bI\s+(?:\w+\s+){0,2}(left|went|took|stayed|remained|sat|typed|wrote|arrived|entered|locked|"
                    r"closed|lit|played|spent|returned|called|came|joined|was|did|never|have|issued|carried)\b", re.I)
DENIAL = re.compile(r"\b(never|did not|didn't|no one|nobody|none|not once|cannot|can't|nothing)\b", re.I)
ABSENCE_OBS = re.compile(r"\bI\s+(?:did not|didn't|never|could not)\s+(?:\w+\s+){0,1}(see|notice|hear|observe)\b|"
                         r"\bI\s+(?:heard|saw|noticed|observed)\s+(?:nothing|no\s+one|nobody)\b", re.I)


def classify(sentence: str):
    s = sentence.strip()
    markers = []
    if ABSENCE_OBS.search(s):
        return {"stance": "absence_of_observation", "certainty": "weak", "markers": [ABSENCE_OBS.search(s).group(0)],
                "explanation": "The speaker says they did not see/hear something. That shows what they failed to "
                               "observe, not that it did not happen."}
    m = ASSUME.search(s)
    if m:
        return {"stance": "assumption", "certainty": "weak", "markers": [m.group(0)],
                "explanation": "Marked as a supposition ('%s'). It is not evidence of what actually happened." % m.group(0)}
    m = HEARSAY.search(s)
    # "told me nothing" / "never told me" is a denial about what was disclosed, not reported speech
    if m and re.search(r"\b(never|not|didn't|did not)\s+(?:\w+\s+)?told\s+me|told\s+me\s+(nothing|no|not)\b", s, re.I):
        m = None
    if m:
        return {"stance": "hearsay", "certainty": "weak", "markers": [m.group(0)],
                "explanation": "Reported second-hand ('%s'); the speaker did not observe it themselves." % m.group(0)}
    m = OBSERVE.search(s)
    if m:
        return {"stance": "direct_observation", "certainty": "strong", "markers": [m.group(0)],
                "explanation": "First-hand perception ('%s')." % m.group(0)}
    m = ACTION.search(s)
    if m:
        d = DENIAL.search(s)
        return {"stance": "own_account" + ("_denial" if d else ""), "certainty": "medium",
                "markers": [m.group(0)] + ([d.group(0)] if d else []),
                "explanation": "The speaker's own account of their actions%s; it can be checked against records."
                               % (" (a denial)" if d else "")}
    if DENIAL.search(s):
        return {"stance": "denial", "certainty": "medium", "markers": [DENIAL.search(s).group(0)],
                "explanation": "A denial; test it against the documents."}
    return {"stance": "statement", "certainty": "medium", "markers": [], "explanation": "A plain statement of fact."}


def classify_text(text):
    from .spacy_loader import get_nlp
    return [{"sentence": s.text.strip(), **classify(s.text)} for s in get_nlp()(text).sents if s.text.strip()]
