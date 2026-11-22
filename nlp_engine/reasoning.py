"""Explainable evidence reasoning (why is this statement suspicious?).

 1 retrieve related statements/records   4 identify the relationship (contradiction / not comparable / consistent)
 2 compare entities, time, place, day    5 explain in plain language
 3 run NLI with context gating           6 return the source documents
"""
import re
import time
from .epistemic import classify
from .lexicon import lexicon_for_case_id
from .nli import get_engine
from .spacy_loader import get_nlp
from .temporal import extract_times

INFORMATIVE = {"different_day", "absence_of_observation", "assumption_not_evidence", "literal_vs_implied",
               "model_contradiction_gated"}
TITLE = {"contradiction": "Contradiction", "entailment": "Consistent", "neutral": "Not a contradiction"}


def _sentences(text):
    return [s.text.strip() for s in get_nlp()(text).sents if len(s.text.split()) >= 4]


def _overlap(a, b):
    wa, wb = set(re.findall(r"\w+", a.lower())), set(re.findall(r"\w+", b.lower()))
    return len(wa & wb) / max(1, min(len(wa), len(wb)))


def explain_statement(case, statement_text, speaker_key=None, source_doc_key=None, top_k=14, max_pairs=45):
    from rag_engine.retriever import get_retriever
    t0 = time.perf_counter()
    lex = lexicon_for_case_id(case.pk)
    retr = get_retriever(case.number).retrieve(statement_text, top_k=top_k, audiences=("public",),
                                               kinds=("document", "statement", "timeline"), use_cache=False)
    engine = get_engine()
    lex_frame = None
    from .frames import build_frame, _group
    fr = build_frame(statement_text, lex, speaker_key, lex.incident_day)
    pool = list(retr["results"])
    # structural candidates: documents/statements sharing an object group with the statement but missed by retrieval
    have = {r["chunk"]["id"] for r in pool}
    extra = []
    for c in get_retriever(case.number).chunks:
        if c["id"] in have or c["audience"] != "public" or c["kind"] not in ("document", "statement"):
            continue
        words = set(re.findall(r"[a-z]+", c["text"].lower()))
        if fr.objects & {_group(w) for w in words if _group(w)}:
            extra.append({"chunk": c, "score": 0.0})
    pool += extra[:8]
    seen, comps, pairs, best_by_key = set(), [], 0, {}
    for r in pool:
        c = r["chunk"]
        if c["kind"] not in ("document", "statement", "timeline"):
            continue
        if source_doc_key and c["doc_key"] == source_doc_key and c["kind"] in ("document", "statement"):
            continue
        # single-speaker statements are compared as a whole passage; registers/reports line by line
        premises = [c["text"]] if c["kind"] == "statement" else _sentences(c["text"])
        for sent in premises:
            if _overlap(sent, statement_text) > 0.8 or sent in seen or pairs >= max_pairs:
                continue
            seen.add(sent)
            pairs += 1
            ps = c["suspect_key"] if c["doc_type"] in ("Statement",) else None
            res = engine.compare(sent, statement_text, lex, ps, speaker_key)
            if res.label == "neutral" and (res.finding not in INFORMATIVE or not res.comparable.get("same_people")):
                continue
            if res.label == "entailment" and c["doc_type"] != "Statement":
                continue
            key = (c["doc_key"], res.label, res.finding)
            entry = {"premise": sent if len(sent) < 400 else sent[:400] + "…", "doc_key": c["doc_key"], "title": c["title"],
                     "doc_type": c["doc_type"], "author": c["author"], "retrieval_score": round(r["score"], 2), **res.to_dict()}
            if key in best_by_key:
                if entry["confidence"] > best_by_key[key]["confidence"]:
                    comps[comps.index(best_by_key[key])] = entry
                    best_by_key[key] = entry
                continue
            best_by_key[key] = entry
            comps.append(entry)
    order = {"contradiction": 0, "neutral": 1, "entailment": 2}
    comps.sort(key=lambda x: (order[x["label"]], -x["confidence"]))
    comps = comps[:6]
    stance = classify(statement_text)
    times = [t.to_dict() for t in extract_times(statement_text)]
    from .leakage import detect_leaks
    leak = detect_leaks(case, statement_text, speaker_key)
    summary = _summarise(statement_text, stance, comps)
    if leak["flagged"]:
        summary = ("Possible implicit knowledge: " + leak["explanation"] +
                   " If the police withheld the letter's contents and nobody else was told, how did the speaker know? ") + summary
    return {"statement": statement_text, "stance": stance, "times": times, "leakage": leak, "comparisons": comps, "summary": summary,
            "nli_backend": comps[0]["backend"] if comps else get_engine().compare("a", "b", lex).backend,
            "latency_ms": round((time.perf_counter() - t0) * 1000, 1)}


def _summarise(text, stance, comps):
    parts = []
    contra = [c for c in comps if c["label"] == "contradiction"]
    if contra:
        c = contra[0]
        parts.append(f"This statement conflicts with {c['title']} ({c['doc_type']}). {c['rationale'][0]}")
        if len(contra) > 1:
            parts.append(f"{len(contra) - 1} further conflicting source(s) are listed below.")
    else:
        notes = [c for c in comps if c["label"] == "neutral"]
        if notes:
            parts.append("No genuine contradiction was established. " + notes[0]["rationale"][0])
        else:
            parts.append("No related statement or record contradicts or supports this one in a comparable way.")
    if stance["stance"] in ("assumption", "hearsay", "absence_of_observation"):
        parts.append("Note on the speaker's basis: " + stance["explanation"])
    return " ".join(parts)
