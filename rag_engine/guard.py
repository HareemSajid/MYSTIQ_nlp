"""Output guards: keep generated text grounded and prevent solution / secret leakage."""
import re


def _aliases(suspect):
    names = {suspect.name.lower(), suspect.name.split()[-1].lower()}
    names |= {a.lower() for a in suspect.aliases if len(a) > 3}
    return names


_ACCUSE = r"(culprit|guilty|did it|is responsible|the thief|the murderer|the one who (took|stole)|committed the|is the criminal)"


def leaks_culprit(text: str, culprit) -> bool:
    # "to show who is responsible" (the case objective) is a question, not an accusation
    low = re.sub(r"\b(show|find|establish|discover|determine|learn|decide|ask|know|prove)\s+who\s+(is|was)\s+(responsible|guilty)", " ", text.lower())
    for a in _aliases(culprit):
        for m in re.finditer(re.escape(a), low):
            window = low[max(0, m.start() - 70): m.end() + 70]
            if re.search(_ACCUSE, window):
                return True
    return False


def asks_for_solution(question: str) -> bool:
    return bool(re.search(r"\b(who (is|was) (the )?(culprit|guilty|thief|murderer|responsible)|who (did|stole|took) it|"
                          r"(tell|give) me the (answer|solution)|name the (culprit|thief)|who is behind|just tell me who|"
                          r"reveal the (culprit|solution))\b", question, re.I))


CONFESSION = re.compile(r"\b(I (confess|admit (it|that I (took|stole|did|wrote|struck|poisoned|put|carried|lured))|did it|stole it|"
                        r"am the (thief|culprit|guilty)|killed|struck him|took the (emerald|manuscript|design|cup))|it was me)\b", re.I)


def leaks_secret(text: str) -> bool:
    return "SECRET" in text or "never admit" in text.lower()


def clean_citations(text: str, n: int) -> str:
    def fix(m):
        return m.group(0) if 1 <= int(m.group(1)) <= n else ""
    return re.sub(r"\[E(\d+)\]", fix, text)
