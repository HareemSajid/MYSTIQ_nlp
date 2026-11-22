"""RAG orchestration: analyst Q&A, Watson, and suspect interrogation, with Gemini generation or an offline demo mode.

Demo mode is NOT a canned chatbot: answers are built from the retrieved chunks by sentence-level semantic selection,
epistemic-stance annotation and (for suspects) retrieval of the authored interview topics. Gemini, when configured,
receives only the retrieved evidence and the same guards are applied to its output.
"""
import hashlib
import re
import time
from django.conf import settings
from nlp_engine.epistemic import classify
from nlp_engine.lexicon import lexicon_for_case_id
from nlp_engine.reasoning import explain_statement
from nlp_engine.spacy_loader import get_nlp
from . import guard, llm, prompts
from .retriever import get_retriever

NO_EVIDENCE = ("The case files do not contain anything that answers that. Try naming a person, a place or a time, "
               "or open a document and ask about it.")


def _cite_block(results):
    lines = []
    for i, r in enumerate(results, 1):
        c = r["chunk"]
        meta = ", ".join(x for x in (c["doc_type"], c["author"], c["datetime"]) if x)
        lines.append(f"[E{i}] ({c['title']}{'; ' + meta if meta else ''}) {c['text']}")
    return "\n".join(lines)


def _citations(results):
    out = []
    for i, r in enumerate(results, 1):
        c = r["chunk"]
        out.append({"id": f"E{i}", "doc_key": c["doc_key"], "title": c["title"], "kind": c["kind"],
                    "doc_type": c["doc_type"], "author": c["author"], "score": round(r["score"], 2),
                    "similarity": round(r["dense"], 2), "snippet": c["text"][:240]})
    return out


def _select_sentences(question, results, und, embedder, n=3):
    nlp = get_nlp()
    cand = []
    for ci, r in enumerate(results, 1):
        c = r["chunk"]
        for s in nlp(c["text"]).sents:
            st = s.text.strip()
            if len(st.split()) >= 4:
                cand.append((ci, st, r["score"], c))
    if not cand:
        return []
    from .preprocess import tokens as _tok
    qtok = {t for t in _tok(question) if not (t.startswith("t") and t[1:].isdigit())}
    qv = embedder.encode([question])[0]
    sv = embedder.encode([c[1] for c in cand])
    sims = sv @ qv
    scored = []
    for (ci, st, rs, c), sim in zip(cand, sims):
        bonus = 0.0
        low = st.lower()
        for p in und["people"]:
            if p in c["persons"]:
                bonus += 0.05
        if any(t["label"].lower().replace(" ", "") in low.replace(" ", "") for t in und["times"]):
            bonus += 0.05
        overlap = len(qtok & set(_tok(st))) / max(1, len(qtok))       # lexical support (lemma + synonym folded)
        scored.append((float(sim) + bonus + 0.45 * rs + 0.6 * overlap, ci, st, c))
    scored.sort(key=lambda x: -x[0])
    chosen, used_src, used = [], set(), []
    for sc, ci, st, c in scored:
        src = c["doc_key"] or c["id"]
        w = set(re.findall(r"[a-z0-9']+", st.lower()))
        if src in used_src or any(len(w & u) / max(1, min(len(w), len(u))) > 0.7 for u in used):
            continue
        chosen.append((ci, st, c))
        used.append(w)
        used_src.add(src)
        if len(chosen) >= n:
            break
    chosen.sort(key=lambda x: x[0])      # present evidence in citation order (E1, E2, ...)
    return chosen


def _demo_answer(question, retr, embedder):
    und = retr["understanding"]
    chosen = _select_sentences(question, retr["results"], und, embedder)
    parts = []
    for ci, st, c in chosen:
        stance = classify(st)
        who = c["author"] or c["title"]
        verb = "records" if c["doc_type"] in ("Register", "Record", "Schedule", "Plan", "Report", "Receipt", "Timeline") else "states"
        note = ""
        if stance["stance"] == "assumption":
            note = " (an assumption, not an observation)"
        elif stance["stance"] == "hearsay":
            note = " (hearsay, not first-hand)"
        elif stance["stance"] == "absence_of_observation":
            note = " (this only shows what they did not see)"
        label = "The case introduction says" if c["kind"] == "context" else \
            ("The timeline records" if c["kind"] == "timeline" else f"{c['title']} {verb}")
        parts.append(f"{label}: \u201c{st}\u201d{note} [E{ci}]")
    text = " ".join(p if p.endswith((".", "]")) else p + "." for p in parts)
    if und["times"] and chosen:
        t = und["times"][0]
        note = " — note the AM/PM was inferred" if t["ambiguous"] else ""
        text += f" (You asked about {t['label']}{note}.)"
    return text


def _pick(options, seed):
    h = int(hashlib.md5(seed.encode()).hexdigest(), 16)
    return options[h % len(options)]


def answer_question(case, question, doc_key=None, role="analyst", hint_max=0):
    """Analyst / Watson style grounded answer with citations. role: analyst | watson."""
    t0 = time.perf_counter()
    audiences = ("public", "watson") if role == "watson" else ("public",)
    retr = get_retriever(case.number).retrieve(question, audiences=audiences, doc_key=doc_key, hint_max=hint_max,
                                               kinds=("document", "statement", "timeline", "profile", "context", "hint"))
    from .embeddings import get_embedder
    embedder = get_retriever(case.number).embedder
    if retr["insufficient"]:
        text = NO_EVIDENCE if role == "analyst" else \
            "I am afraid the papers say nothing on that point, my friend. Perhaps re-read the statements for a name or an hour to pursue."
        return {"answer": text, "citations": [], "mode": "demo", "insufficient": True, "retrieval": _retr_meta(retr),
                "latency_ms": round((time.perf_counter() - t0) * 1000, 1)}
    results = retr["results"][:5]
    mode, fallback, text, llm_ms = "demo", None, None, 0
    if llm.gemini_available():
        system = prompts.WATSON_SYSTEM if role == "watson" else prompts.ANALYST_SYSTEM
        out, llm_ms, err = llm.generate(system, f"EVIDENCE EXCERPTS:\n{_cite_block(results)}\n\nQUESTION: {question}")
        if out:
            out = guard.clean_citations(out, len(results))
            from cases.models import CaseSolution
            culprit = case.suspects.get(key=CaseSolution.objects.get(case=case).data["culprit"])
            if guard.leaks_culprit(out, culprit) or guard.leaks_secret(out):
                fallback = "guard_blocked"
            else:
                text, mode = out, "gemini"
        else:
            fallback = err
    if text is None:
        text = _demo_answer(question, retr, embedder)
        if role == "watson":
            opener = _pick(["Quite so, my dear fellow. ", "A fair question. ", "Let us consult the papers together. ",
                            "Ah, I had wondered the same. "], question)
            closer = _pick([" Does that suggest a line of inquiry to you?", " Mark the exact wording, Holmes would say.",
                            " I would weigh who actually saw this, and who merely supposed it."], question[::-1])
            text = opener + text + closer
    analysis = None
    und = retr["understanding"]
    if "contradiction" in und["intents"] and und["people"]:
        st = case.statements.filter(suspect__key=und["people"][0]).first()
        if st:
            analysis = explain_statement(case, st.text, st.suspect.key, st.document.key if st.document else None)
    return {"answer": text, "citations": _citations(results), "mode": mode, "fallback_reason": fallback,
            "insufficient": False, "retrieval": _retr_meta(retr), "analysis": analysis, "llm_ms": llm_ms,
            "latency_ms": round((time.perf_counter() - t0) * 1000, 1)}


def _retr_meta(retr):
    return {"backend": retr["backend"], "latency_ms": retr["latency_ms"], "stages_ms": retr["stages_ms"],
            "cached": retr["cached"], "intents": retr["understanding"]["intents"],
            "times": retr["understanding"]["times"], "people": retr["understanding"]["people"],
            "results": [{"id": r["chunk"]["id"], "doc_key": r["chunk"]["doc_key"], "kind": r["chunk"]["kind"],
                         "score": round(r["score"], 3), "dense": round(r["dense"], 3), "rank": r["rank"]} for r in retr["results"]]}


# ----------------------------------------------------------------------------------------------- Suspect AI
def interrogate(case, suspect, question, presented_doc=None):
    t0 = time.perf_counter()
    audiences = ("public", f"suspect:{suspect.key}")
    retriever = get_retriever(case.number)
    query = question if not presented_doc else f"{question} {presented_doc.title}"
    retr = retriever.retrieve(query, top_k=6, audiences=audiences, suspect_key=suspect.key,
                              doc_key=presented_doc.key if presented_doc else None)
    results = retr["results"]
    # best matching authored topic for THIS suspect
    topic, best = None, 0.0
    for r in results:
        c = r["chunk"]
        if c["kind"] == "topic" and c["suspect_key"] == suspect.key and r["score"] > best:
            idx = int(c["id"].rsplit(":", 1)[1])
            if idx < len(suspect.topics):
                topic, best = suspect.topics[idx], r["score"]
    mode, fallback, text = "demo", None, None
    grounded_ok = topic is not None and (best >= 0.30)
    if llm.gemini_available() and results:
        sys_prompt = prompts.SUSPECT_SYSTEM.format(name=suspect.name, role=suspect.role, personality=suspect.personality)
        out, _, err = llm.generate(sys_prompt, f"CONTEXT:\n{_cite_block(results)}\n\nThe detective asks: {question}", max_tokens=220, temperature=0.5)
        if out:
            out = guard.clean_citations(out, 0)
            if guard.CONFESSION.search(out) or guard.leaks_secret(out):
                fallback = "guard_blocked"
            else:
                text, mode = out, "gemini"
        else:
            fallback = err
    if text is None:
        if grounded_ok:
            text = topic["a"].strip()
        else:
            own = [r for r in results if r["chunk"]["suspect_key"] == suspect.key and r["chunk"]["kind"] == "statement"]
            if own and own[0]["dense"] >= 0.25:
                text = f"I have already said what I have to say: \u201c{own[0]['chunk']['text']}\u201d I can add nothing to it."
            else:
                text = suspect.deflect or "I have nothing more to say on that."
    return {"answer": text, "mode": mode, "fallback_reason": fallback, "topic_score": round(best, 2),
            "retrieval": _retr_meta(retr), "citations": [],
            "latency_ms": round((time.perf_counter() - t0) * 1000, 1)}
