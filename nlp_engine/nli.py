"""Natural Language Inference with context gating.

Backends
  * `transformers`: a pretrained NLI cross-encoder (default cross-encoder/nli-MiniLM2-L6-H768) loaded through
    sentence-transformers when available.
  * `symbolic`: a frame-based inference engine (actor / predicate / place / time / negation / stance rules).

Both are always fused with *comparability gating*: a contradiction is only declared when the two statements concern the
same person, the same day and the same event window. Statements that merely differ in wording, that refer to different
days, that are assumptions, or that report a failure to observe never yield a contradiction.
"""
import logging
import re
import time
from dataclasses import dataclass, field
from django.conf import settings
from .frames import Frame, build_frame, places_overlap
from .lexicon import CaseLexicon

log = logging.getLogger(__name__)
TOL = 15  # minutes of tolerance when comparing approximate times


@dataclass
class NLIResult:
    label: str                    # entailment | contradiction | neutral
    confidence: float
    finding: str                  # machine-readable reason
    rationale: list = field(default_factory=list)
    backend: str = "symbolic"
    model_probs: dict = None
    comparable: dict = field(default_factory=dict)
    latency_ms: float = 0.0

    def to_dict(self):
        return {"label": self.label, "confidence": round(self.confidence, 2), "finding": self.finding,
                "rationale": self.rationale, "backend": self.backend, "model_probs": self.model_probs,
                "comparable": self.comparable, "latency_ms": round(self.latency_ms, 2)}


# ---------------------------------------------------------------- transformer backend
class _ModelNLI:
    def __init__(self):
        self.model, self.name, self.error = None, None, None
        backend = settings.MYSTIQ["NLP_BACKEND"]
        if backend == "local":
            self.error = "NLP_BACKEND=local"
            return
        try:
            from sentence_transformers import CrossEncoder
            self.name = settings.MYSTIQ["NLI_MODEL"]
            self.model = CrossEncoder(self.name)
        except Exception as exc:
            self.error = f"{type(exc).__name__}: {exc}"[:200]
            self.model = None

    def predict(self, premise, hypothesis):
        import numpy as np
        logits = self.model.predict([(premise, hypothesis)])[0]
        e = np.exp(logits - np.max(logits))
        p = e / e.sum()
        # label order of the cross-encoder/nli-* family: contradiction, entailment, neutral
        probs = {"contradiction": float(p[0]), "entailment": float(p[1]), "neutral": float(p[2])}
        return max(probs, key=probs.get), probs


_model_nli = None


def get_model_nli():
    global _model_nli
    if _model_nli is None:
        _model_nli = _ModelNLI()
    return _model_nli


def backend_info():
    m = get_model_nli()
    return {"model": m.name if m.model else None, "loaded": m.model is not None, "fallback_reason": m.error}


# ---------------------------------------------------------------- symbolic rules
def _in_window(t, lo, hi, tol=TOL):
    if t is None:
        return None
    lo = lo if lo is not None else -10**6
    hi = hi if hi is not None else 10**6
    return lo - tol <= t <= hi + tol


def _same_actor(a, b):
    return a is not None and a == b


def _day_gate(P: Frame, H: Frame):
    if P.days and H.days and P.days.isdisjoint(H.days):
        return f"Different days: one statement refers to {', '.join(sorted(P.days)).title()}, the other to {', '.join(sorted(H.days)).title()}."
    return None


def _rules(P: Frame, H: Frame, lex: CaseLexicon):
    """Return (label, finding, rationale) or None. Applied in both directions by compare()."""
    names = lambda k: (lex.person_by_key(k).name if k and lex.person_by_key(k) else (k or "someone"))
    # 0. literal-but-misleading scope: "I never touched HIS key" vs "a second/spare key was cut"
    if any(n.negated and n.cls == "TOUCH" for n in P.acts) and P.possessive_obj and \
            H.scope_words & {"second", "spare", "duplicate", "another"} and "key" in (P.objects & H.objects | P.objects):
        return ("neutral", "literal_vs_implied",
                ["The denial is limited to 'his' key, while the other document concerns a different (second/spare) key. "
                 "The statement can be literally true yet misleading."])
    # 1. negated vs affirmed act by the same actor
    for n in P.acts:
        if not n.negated or n.cls not in ("TOUCH", "MOVE_OUT", "GO_TO", "PRESENT"):
            continue
        for a in H.acts:
            same_family = a.cls == n.cls or {a.cls, n.cls} <= {"GO_TO", "PRESENT"}
            if a.negated or not same_family or not _same_actor(n.actor, a.actor):
                continue
            # scope check: the denial is about 'his key' while the other says 'second/spare key'
            if n.cls == "TOUCH" and P.possessive_obj and H.scope_words & {"second", "spare", "duplicate", "another"}:
                return ("neutral", "literal_vs_implied",
                        ["The denial is limited to 'his' key, while the other document concerns a different (second/spare) key. "
                         "The statement can be literally true yet misleading."])
            if n.cls == "TOUCH" and not (P.objects & H.objects or n.objects & a.objects):
                continue
            if n.cls in ("GO_TO", "PRESENT") and not (P.places and H.places and any(places_overlap(x, y) for x in P.places for y in H.places)):
                continue
            universal = " never " in f" {P.text.lower()} "
            if not universal and P.t_at and H.t_at and abs(P.t_at - H.t_at) > 60 and n.cls != "MOVE_OUT":
                continue
            return ("contradiction", "denial_vs_record",
                    [f"One statement denies that {names(n.actor)} did this ('{n.lemma}'), while the other says {names(a.actor)} did "
                     f"({a.lemma}), about the same {'object' if n.cls == 'TOUCH' else 'place/action'}."])
    # 2. presence over an interval vs 'the place was empty'
    for pres in (a for a in P.acts if a.cls == "PRESENT" and not a.negated):
        if H.empty_places and P.places:
            for hp in H.empty_places:
                for pp in P.places:
                    if places_overlap(hp, pp):
                        t = H.t_at
                        inside = _in_window(t, P.t_from if P.t_from is not None else P.t_at,
                                            P.t_until if P.t_until is not None else P.t_at, TOL)
                        if inside:
                            return ("contradiction", "presence_vs_empty",
                                    [f"{names(pres.actor)} claims to have been in the {pp} for the whole interval, but the other "
                                     f"witness found the {hp} empty at a time inside that interval."])
    # 3. departure vs later sighting (same day, same person)
    for dep in (a for a in P.acts if a.cls == "MOVE_OUT" and not a.negated):
        for see in (a for a in H.acts if a.cls == "SEE" and not a.negated):
            if see.patient and _same_actor(dep.actor or P.speaker, see.patient) and P.t_at and H.t_at:
                if H.t_at > P.t_at + 4:
                    return ("contradiction", "left_then_seen",
                            [f"{names(see.patient)} says they left at one time, but another witness reports seeing them "
                             f"later, in the same setting, on the same day."])
    # 3b. claimed presence at one place vs. being seen at a different place within the claimed interval
    for pres in (a for a in P.acts if a.cls == "PRESENT" and not a.negated):
        for see in (a for a in H.acts if a.cls == "SEE" and not a.negated and a.patient):
            if see.patient == (pres.actor or P.speaker) and P.places and H.places and \
                    not any(places_overlap(x, y) for x in P.places for y in H.places) and H.t_at is not None and \
                    _in_window(H.t_at, P.t_from if P.t_from is not None else P.t_at, P.t_until if P.t_until is not None else P.t_at, 0):
                return ("contradiction", "location_conflict",
                        [f"{names(see.patient)} claims to be in one place for the whole interval, but another witness saw them "
                         f"somewhere else at a time inside it."])
    # 4. a stopped clock cannot strike / be heard to strike
    clk = lambda t: (re.search(r"\b(tower|stable|hall|church|pantry|grandfather|mantel|regulator|station)\s+clock\b", t.lower()) or [None, ""])[1]
    different_clock = clk(P.text) and clk(H.text) and clk(P.text) != clk(H.text) and \
        True
    if P.stop_time is not None and not different_clock:
        for h in H.acts:
            if h.cls in ("STRIKE", "HEAR") and not h.negated and H.t_at is not None and "clock" in (H.objects | h.objects):
                if H.t_at > P.stop_time:
                    return ("contradiction", "stopped_clock",
                            ["The clock record shows it had stopped before the time at which the witness claims to have "
                             "heard it strike; a stopped clock cannot strike."])
    # 5. conflicting identification of a single event
    for x in (a for a in P.acts if a.cls == "CARRY" and not a.negated):
        for y in (a for a in H.acts if a.cls == "CARRY" and not a.negated):
            witness_like = (P.speaker or H.speaker) and (P.times or P.speaker) and (H.times or H.speaker)
            if x.actor and y.actor and x.actor != y.actor and (P.objects & H.objects) and witness_like:
                return ("contradiction", "conflicting_identification",
                        [f"The two accounts name different people ({names(x.actor)} and {names(y.actor)}) as the one who carried "
                         "the same object in the same event."])
    # 6. assumption vs exclusive direct testimony
    if P.stance.get("stance") == "assumption" and H.exclusive:
        for a in P.acts:
            if a.cls == "TOUCH" and a.actor and a.actor != H.speaker and (P.objects & H.objects):
                return ("contradiction", "assumption_refuted",
                        ["An assumption is refuted by direct testimony: the author of the memorandum held the object throughout "
                         "and says no one else handled it."])
    # 7. impossible return of a key to a locked cabinet while the keeper is away
    for a in H.acts:
        if a.cls == "TOUCH" and a.lemma in ("return",) and not a.negated and "key" in (H.objects | P.objects) and H.t_at is not None:
            if P.t_at is not None and P.t_at <= H.t_at and "cabinet" in P.objects and "locked" in P.text.lower():
                return ("contradiction", "impossible_return",
                        ["The key cabinet was locked, and its keeper had left, before the time of the claimed return; "
                         "nobody was in a position to receive it."])
    return None


def _comparability(P: Frame, H: Frame):
    return {"same_people": bool(set(P.people) & set(H.people)),
            "same_place": bool(P.places & H.places) or not (P.places and H.places),
            "same_day": not (P.days and H.days and P.days.isdisjoint(H.days)),
            "time_overlap": (P.t_at is None or H.t_at is None or abs(P.t_at - H.t_at) <= 180)}


def _absence_applies(P, H):
    """'I did not see X do Y' only matters if the other text reports X doing something."""
    a, b = (H, P) if H.stance.get("stance") == "absence_of_observation" else (P, H)
    others = set(a.people) - {a.speaker}
    return bool(others & set(b.people)) and any(not x.negated for x in b.acts)


class NLIEngine:
    def compare(self, premise: str, hypothesis: str, lex: CaseLexicon, premise_speaker=None, hypothesis_speaker=None,
                default_day=None) -> NLIResult:
        t0 = time.perf_counter()
        default_day = default_day or lex.incident_day
        P = build_frame(premise, lex, premise_speaker, default_day)
        H = build_frame(hypothesis, lex, hypothesis_speaker, default_day)
        comp = _comparability(P, H)
        rationale, label, finding, conf = [], "neutral", "no_relation", 0.5
        # --- gates
        gate = _day_gate(P, H)
        model, probs = None, None
        mm = get_model_nli()
        if mm.model is not None:
            try:
                model, probs = mm.predict(premise, hypothesis)
            except Exception as exc:
                log.warning("NLI model failed: %s", exc)
        backend = f"transformers:{mm.name}+gating" if probs else "symbolic-frames+gating"
        if gate:
            res = NLIResult("neutral", 0.85, "different_day", [gate + " They do not describe the same event, so there is no contradiction."],
                            backend, probs, comp)
        elif (H.stance.get("stance") == "absence_of_observation" or P.stance.get("stance") == "absence_of_observation") and \
                _absence_applies(P, H):
            who = H if H.stance.get("stance") == "absence_of_observation" else P
            res = NLIResult("neutral", 0.8, "absence_of_observation",
                            ["One speaker only says they did not see it happen. Not seeing something is not evidence that it did not "
                             "happen (they may simply have been looking elsewhere), so this is not a contradiction."], backend, probs, comp)
        else:
            r = _rules(P, H, lex) or _rules(H, P, lex)
            if r:
                label, finding, why = r
                conf = 0.9 if label == "contradiction" else 0.7
                # an assumption that merely conflicts with a denial is not evidence of anything
                stances = {P.stance.get("stance"), H.stance.get("stance")}
                if "assumption" in stances and finding == "denial_vs_record":
                    label, finding, conf = "neutral", "assumption_not_evidence", 0.75
                    why = ["One statement is an assumption ('%s'), not an observation, so it cannot establish that the denial is false."
                           % (P.stance if P.stance.get("stance") == "assumption" else H.stance).get("markers", [""])[0]]
                res = NLIResult(label, conf, finding, why, backend, probs, comp)
            elif probs:
                ml = model
                if ml == "contradiction" and not (comp["same_people"] and comp["same_place"] and comp["time_overlap"]):
                    res = NLIResult("neutral", 0.6, "model_contradiction_gated",
                                    ["The pretrained NLI model suggested a contradiction, but the statements do not clearly concern the same "
                                     "person, place and time, so MYSTIQ withholds the verdict."], backend, probs, comp)
                else:
                    res = NLIResult(ml, probs[ml], "model", [f"Pretrained NLI model: {ml} ({probs[ml]:.2f})."], backend, probs, comp)
            else:
                shared = (set(P.people) & set(H.people)) and (P.objects & H.objects or P.places & H.places)
                same_acts = {a.cls for a in P.acts if not a.negated} & {a.cls for a in H.acts if not a.negated}
                same_time = P.t_at is not None and P.t_at == H.t_at
                if (shared and same_acts) or (set(P.people) & set(H.people) and same_acts and same_time):
                    res = NLIResult("entailment", 0.6, "same_proposition", ["Both statements assert the same kind of event by the same person."], backend, probs, comp)
                else:
                    res = NLIResult("neutral", 0.55, "no_relation", ["No shared event structure was found; the statements neither support nor oppose each other."], backend, probs, comp)
        res.latency_ms = (time.perf_counter() - t0) * 1000
        return res


_engine = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = NLIEngine()
    return _engine
