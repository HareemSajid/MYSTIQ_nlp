"""Semantic evaluation of the player's final deduction against the protected answer key.

Deterministic components (exact): culprit, what / when / insight choices, evidence set.
Semantic component: the free-text explanation is split into sentences and each key reasoning concept of the case is
matched with (a) embedding cosine similarity and (b) lemma/keyword coverage. A concept counts as covered when a
sentence is semantically close to it or contains enough of its key terms. The key itself is never exposed.
"""
import re
import numpy as np
from .lexicon import CaseLexicon
from .spacy_loader import get_nlp

W = {"culprit": 400, "what": 100, "when": 100, "insight": 100, "evidence": 150, "explanation": 150}
SOLVE_THRESHOLD = 600
SIM_THRESHOLD = 0.55          # embedding cosine alone
BLEND_THRESHOLD = 0.42        # 0.5*cosine + 0.5*keyword coverage


def _lemmas(text):
    return {(t.lemma_ or t.text).lower() for t in get_nlp()(text) if not (t.is_stop or t.is_punct or t.is_space)}


def _keyword_cov(sentence_low, sentence_lemmas, keywords):
    if not keywords:
        return 0.0
    hit = 0
    for k in keywords:
        k_low = k.lower()
        if k_low in sentence_low or all(w in sentence_lemmas or w in sentence_low for w in k_low.split()):
            hit += 1
    return hit / len(keywords)


def explanation_score(explanation, concepts, embedder=None):
    sents = [s.text.strip() for s in get_nlp()(explanation).sents if len(s.text.split()) >= 3] or [explanation]
    low_full = explanation.lower()
    lem_full = _lemmas(explanation)
    sims = None
    if embedder is not None and concepts:
        cv = embedder.encode([c["text"] for c in concepts])
        sv = embedder.encode(sents)
        sims = cv @ sv.T
    details, covered = [], 0
    for i, c in enumerate(concepts):
        best_sim = float(sims[i].max()) if sims is not None else 0.0
        kw = _keyword_cov(low_full, lem_full, c.get("keywords", []))
        blend = 0.5 * best_sim + 0.5 * kw
        ok = best_sim >= SIM_THRESHOLD or blend >= BLEND_THRESHOLD
        covered += ok
        details.append({"concept": c["id"], "similarity": round(best_sim, 2), "keyword_coverage": round(kw, 2),
                        "covered": bool(ok)})
    frac = covered / len(concepts) if concepts else 0.0
    return frac, details


def mentioned_suspects(explanation, suspects):
    low = explanation.lower()
    out = []
    for s in suspects:
        names = {s.name.lower(), s.name.split()[-1].lower()} | {a.lower() for a in s.aliases if len(a) > 4}
        if any(re.search(r"\b%s\b" % re.escape(n), low) for n in names):
            out.append(s.key)
    return out


def evaluate(solution: dict, suspects, submission: dict, embedder=None):
    """submission: culprit, what, when, insight, evidence (list of keys), explanation."""
    culprit_ok = submission.get("culprit") == solution["culprit"]
    opt = lambda name, key: next((o["id"] for o in solution[name] if o["correct"]), None) == submission.get(key)
    what_ok, when_ok, insight_ok = opt("what_options", "what"), opt("when_options", "when"), opt("insight_options", "insight")
    required = set(solution["required_evidence"])
    support = required | set(solution.get("related_evidence", []))
    chosen = set(submission.get("evidence", []))
    recall = len(chosen & required) / len(required) if required else 0
    precision = len(chosen & support) / len(chosen) if chosen else 0
    ev = 0.7 * recall + 0.3 * precision
    expl = (submission.get("explanation") or "").strip()
    frac, details = (explanation_score(expl, solution["concepts"], embedder) if len(expl.split()) >= 4 else (0.0, []))
    named = mentioned_suspects(expl, suspects)
    wrong_named = [k for k in named if k != solution["culprit"]]
    if solution["culprit"] not in named and frac > 0:
        frac *= 0.6    # a convincing explanation should name who it is about
    if wrong_named and solution["culprit"] not in named:
        frac *= 0.5
    points = {"culprit": W["culprit"] * culprit_ok, "what": W["what"] * what_ok, "when": W["when"] * when_ok,
              "insight": W["insight"] * insight_ok, "evidence": round(W["evidence"] * ev),
              "explanation": round(W["explanation"] * frac)}
    base = int(sum(points.values()))
    return {"culprit_ok": culprit_ok, "what_ok": what_ok, "when_ok": when_ok, "insight_ok": insight_ok,
            "evidence_recall": round(recall, 2), "evidence_precision": round(precision, 2),
            "missing_evidence": sorted(required - chosen), "irrelevant_evidence": sorted(chosen - support),
            "explanation_fraction": round(frac, 2), "explanation_details": details,
            "points": points, "base_points": base, "solved": bool(culprit_ok and base >= SOLVE_THRESHOLD)}
