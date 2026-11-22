import json
import time
from collections import OrderedDict

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from cases.models import Case, CaseSolution, EvidenceDocument, Suspect
from nlp_engine import ner as ner_mod
from nlp_engine.coref import resolve as coref_resolve
from nlp_engine.epistemic import classify
from nlp_engine.lexicon import lexicon_for_case_id
from nlp_engine.nli import backend_info, get_engine
from nlp_engine.reasoning import explain_statement
from nlp_engine.temporal import extract_times
from rag_engine import generation, guard
from rag_engine.embeddings import LOCAL_NAME
from rag_engine.llm import gemini_available
from rag_engine.retriever import get_retriever

from . import services
from .models import (FinalDeduction, Interrogation, InterrogationMessage, RetrievedEvidenceLog, Score, WatsonMessage)


# ---------------------------------------------------------------- helpers
def _case_or_404(user, number, need_unlocked=True):
    case = get_object_or_404(Case, number=number)
    if need_unlocked and not services.is_unlocked(user, case):
        raise PermissionError
    return case


def _json(request):
    try:
        return json.loads(request.body.decode() or "{}")
    except Exception:
        return {}


def _log(user, case, purpose, query, meta):
    r = meta.get("retrieval") or {}
    RetrievedEvidenceLog.objects.create(
        user=user, case=case, purpose=purpose, query=query[:1000], results=r.get("results", []),
        top_k=len(r.get("results", [])), backend=r.get("backend", ""), latency_ms=int(r.get("latency_ms", 0)))


def _api(view):
    """Login + unlock protection + JSON errors for the API endpoints."""
    def wrapped(request, number, *a, **kw):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "login_required"}, status=401)
        try:
            case = _case_or_404(request.user, number)
        except PermissionError:
            return JsonResponse({"error": "case_locked"}, status=403)
        try:
            return view(request, case, *a, **kw)
        except RuntimeError as exc:           # e.g. missing vector index
            return JsonResponse({"error": str(exc)}, status=503)
    wrapped.__name__ = view.__name__
    return wrapped


# ---------------------------------------------------------------- public pages
def landing(request):
    return render(request, "game/landing.html", {"case_count": Case.objects.count()})


def how_to_play(request):
    return render(request, "game/how_to_play.html")


# ---------------------------------------------------------------- dashboard / intro
@login_required
def dashboard(request):
    summary = services.player_summary(request.user)
    return render(request, "game/dashboard.html", {"cards": services.case_cards(request.user), "summary": summary})


@login_required
def case_intro(request, number):
    case = get_object_or_404(Case, number=number)
    if not services.is_unlocked(request.user, case):
        return render(request, "game/locked.html", {"case": case}, status=403)
    prog = services.progress_for(request.user, case)
    return render(request, "game/case_intro.html", {"case": case, "suspects": case.suspects.all(), "progress": prog,
                                                    "doc_count": case.documents.count()})


@login_required
@require_POST
def case_start(request, number):
    case = get_object_or_404(Case, number=number)
    if not services.is_unlocked(request.user, case):
        return HttpResponseForbidden("Case locked")
    services.start_case(request.user, case)
    return redirect("investigation", number=number)


# ---------------------------------------------------------------- investigation room
@login_required
def investigation(request, number):
    case = get_object_or_404(Case, number=number)
    if not services.is_unlocked(request.user, case):
        return render(request, "game/locked.html", {"case": case}, status=403)
    prog = services.start_case(request.user, case)
    docs = list(case.documents.select_related("suspect"))
    statements = []
    for st in case.statements.select_related("suspect", "document"):
        stance = classify(st.text)
        statements.append({"obj": st, "stance": stance})
    timeline = OrderedDict()
    for e in case.timeline.select_related("source"):
        timeline.setdefault(e.day_label.title() if e.day_label else "Day of the incident", []).append(e)
    watson = list(WatsonMessage.objects.filter(user=request.user, case=case))
    histories = {}
    for it in Interrogation.objects.filter(user=request.user, case=case).prefetch_related("messages"):
        histories[it.suspect.key] = list(it.messages.all())
    used = services.hints_released(request.user, case)
    ctx = {"case": case, "suspects": case.suspects.all(), "documents": docs, "statements": statements,
           "timeline": timeline, "watson": watson, "histories": histories, "progress": prog,
           "important": set(prog.important_docs), "hints_used": used, "hints_total": case.hints.count(),
           "hint_texts": [h.text for h in case.hints.all()[:used]],
           "elapsed": services.elapsed_seconds(prog), "gemini": gemini_available()}
    return render(request, "game/investigation.html", ctx)


@login_required
def evidence_view(request, number, key):
    case = get_object_or_404(Case, number=number)
    if not services.is_unlocked(request.user, case):
        return render(request, "game/locked.html", {"case": case}, status=403)
    doc = get_object_or_404(EvidenceDocument, case=case, key=key)
    prog = services.progress_for(request.user, case)
    return render(request, "game/evidence.html", {
        "case": case, "doc": doc, "important": key in prog.important_docs,
        "all_docs": case.documents.all(), "suspects": case.suspects.all()})


@login_required
def suspect_view(request, number, key):
    case = get_object_or_404(Case, number=number)
    if not services.is_unlocked(request.user, case):
        return render(request, "game/locked.html", {"case": case}, status=403)
    s = get_object_or_404(Suspect, case=case, key=key)
    stmts = [{"obj": st, "stance": classify(st.text)} for st in s.statements.select_related("document")]
    return render(request, "game/suspect.html", {"case": case, "s": s, "statements": stmts,
                                                 "documents": s.documents.all(),
                                                 "mentioned": case.documents.exclude(suspect=s)[:0]})


# ---------------------------------------------------------------- deduction / results / report
@login_required
def deduction(request, number):
    case = get_object_or_404(Case, number=number)
    if not services.is_unlocked(request.user, case):
        return render(request, "game/locked.html", {"case": case}, status=403)
    sol = CaseSolution.objects.get(case=case).data
    strip = lambda opts: [{"id": o["id"], "text": o["text"]} for o in opts]       # never send `correct`
    if request.method == "POST":
        data = {"culprit": request.POST.get("culprit", ""), "what": request.POST.get("what", ""),
                "when": request.POST.get("when", ""), "insight": request.POST.get("insight", ""),
                "evidence": request.POST.getlist("evidence"), "explanation": request.POST.get("explanation", "")}
        valid_docs = set(case.documents.values_list("key", flat=True))
        data["evidence"] = [k for k in data["evidence"] if k in valid_docs]
        fd, ev = services.submit_deduction(request.user, case, data)
        if ev["solved"]:
            return redirect("results", number=number)
        prog = services.progress_for(request.user, case)
        return render(request, "game/deduction.html", {
            "case": case, "suspects": case.suspects.all(), "documents": case.documents.all(),
            "what_options": strip(sol["what_options"]), "when_options": strip(sol["when_options"]),
            "insight_options": strip(sol["insight_options"]), "failed": True, "posted": data,
            "feedback": _soft_feedback(ev), "attempts": prog.attempts})
    prog = services.progress_for(request.user, case)
    return render(request, "game/deduction.html", {
        "case": case, "suspects": case.suspects.all(), "documents": case.documents.all(),
        "what_options": strip(sol["what_options"]), "when_options": strip(sol["when_options"]),
        "insight_options": strip(sol["insight_options"]), "posted": {}, "attempts": prog.attempts})


def _soft_feedback(ev):
    """After a failed attempt: tell the player how they did, without leaking the answer key."""
    fb = []
    fb.append("Your accusation is not yet supported by the evidence." if not ev["culprit_ok"]
              else "Your suspect stands, but the case is not yet proven.")
    if not ev["what_ok"] or not ev["when_ok"]:
        fb.append("Your reconstruction of what happened or when is off.")
    if ev["missing_evidence"]:
        fb.append(f"You have not cited {len(ev['missing_evidence'])} essential document(s).")
    if not ev["insight_ok"]:
        fb.append("The contradiction or hidden meaning you picked does not expose the truth.")
    if ev["explanation_fraction"] < 0.6:
        fb.append("Your written reasoning leaves key links in the chain unexplained.")
    return fb


@login_required
def results(request, number):
    case = get_object_or_404(Case, number=number)
    if not services.can_view_results(request.user, case):
        return redirect("investigation", number=number)
    prog = services.progress_for(request.user, case)
    sol = CaseSolution.objects.get(case=case).data
    culprit = case.suspects.get(key=sol["culprit"])
    docs = {d.key: d for d in case.documents.all()}
    last = FinalDeduction.objects.filter(user=request.user, case=case, correct=True).first() or \
        FinalDeduction.objects.filter(user=request.user, case=case).first()
    ev = last.evaluation if last else None
    mistakes = []
    if ev:
        if not ev["culprit_ok"]:
            mistakes.append("You accused the wrong person.")
        if not ev["what_ok"]:
            mistakes.append("Your reconstruction of what happened was incorrect.")
        if not ev["when_ok"]:
            mistakes.append("You placed the incident at the wrong time.")
        if not ev["insight_ok"]:
            mistakes.append("You did not identify the key contradiction or hidden meaning.")
        if ev["missing_evidence"]:
            mistakes.append("Essential evidence you missed: " + ", ".join(docs[k].title for k in ev["missing_evidence"] if k in docs))
        if ev["irrelevant_evidence"]:
            mistakes.append("Evidence you cited that does not support the conclusion: " +
                            ", ".join(docs[k].title for k in ev["irrelevant_evidence"] if k in docs))
    score = Score.objects.filter(user=request.user, case=case).first()
    nxt = Case.objects.filter(number=case.number + 1).first()
    return render(request, "game/results.html", {
        "case": case, "solved": prog.solved, "culprit": culprit, "solution": sol,
        "required": [docs[k] for k in sol["required_evidence"] if k in docs],
        "related": [docs[k] for k in sol.get("related_evidence", []) if k in docs],
        "mistakes": mistakes, "evaluation": ev, "score": score, "progress": prog, "next_case": nxt,
        "time_taken": prog.seconds_spent, "hints": prog.hints_used, "attempts": prog.attempts})


@login_required
@require_POST
def reveal(request, number):
    case = get_object_or_404(Case, number=number)
    if not services.is_unlocked(request.user, case):
        return HttpResponseForbidden()
    services.reveal_case(request.user, case)
    return redirect("results", number=number)


@login_required
def final_report(request):
    summary = services.player_summary(request.user)
    return render(request, "game/report.html", {"summary": summary, "text": services.performance_text(summary),
                                                "cards": services.case_cards(request.user)})


# ---------------------------------------------------------------- JSON APIs
@_api
@require_POST
def api_ask(request, case):
    d = _json(request)
    q = (d.get("question") or "").strip()[:500]
    if len(q) < 3:
        return JsonResponse({"error": "Ask a question of at least a few words."}, status=400)
    doc_key = d.get("doc_key") or None
    out = generation.answer_question(case, q, doc_key=doc_key, role="analyst")
    _log(request.user, case, "ask", q, out)
    WatsonMessage.objects.create(user=request.user, case=case, role="player", kind="ask", text=q)
    return JsonResponse(out)


@_api
@require_POST
def api_watson(request, case):
    d = _json(request)
    q = (d.get("question") or "").strip()[:500]
    if len(q) < 3:
        return JsonResponse({"error": "Tell Watson what is troubling you."}, status=400)
    used = services.hints_released(request.user, case)
    WatsonMessage.objects.create(user=request.user, case=case, role="player", kind="chat", text=q)
    if guard.asks_for_solution(q):
        text = ("My dear fellow, I would be a poor companion if I simply named the culprit. Let me instead offer a hint. "
                "Ask me to help with the next hint, or tell me which document puzzles you.")
        out = {"answer": text, "citations": [], "mode": "demo", "insufficient": False, "refused": True}
    else:
        out = generation.answer_question(case, q, role="watson", hint_max=used)
        _log(request.user, case, "watson", q, out)
    WatsonMessage.objects.create(user=request.user, case=case, role="watson", kind="chat", text=out["answer"])
    out["hints_used"] = used
    return JsonResponse(out)


@_api
@require_POST
def api_hint(request, case):
    h = services.release_hint(request.user, case)
    used = services.hints_released(request.user, case)
    if h is None:
        return JsonResponse({"error": "no_more_hints", "message": "Dr. Watson has no further hints for this case.",
                             "hints_used": used}, status=409)
    related = get_retriever(case.number).retrieve(h.text, top_k=2, audiences=("public",), kinds=("document", "statement"))
    refs = [{"doc_key": r["chunk"]["doc_key"], "title": r["chunk"]["title"]} for r in related["results"] if r["chunk"]["doc_key"]]
    WatsonMessage.objects.create(user=request.user, case=case, role="watson", kind="hint", text=h.text)
    return JsonResponse({"order": h.order, "text": h.text, "hints_used": used, "hints_total": case.hints.count(),
                         "penalty": services.HINT_PENALTY, "look_at": refs[:2]})


@_api
@require_POST
def api_interrogate(request, case):
    d = _json(request)
    suspect = get_object_or_404(Suspect, case=case, key=d.get("suspect", ""))
    q = (d.get("question") or "").strip()[:400]
    if len(q) < 3:
        return JsonResponse({"error": "Put a question to the suspect."}, status=400)
    presented = None
    if d.get("present"):
        presented = EvidenceDocument.objects.filter(case=case, key=d["present"]).first()
    out = generation.interrogate(case, suspect, q, presented)
    it, _ = Interrogation.objects.get_or_create(user=request.user, case=case, suspect=suspect)
    InterrogationMessage.objects.create(interrogation=it, role="player",
                                        text=q + (f" [presents: {presented.title}]" if presented else ""))
    InterrogationMessage.objects.create(interrogation=it, role="suspect", text=out["answer"], mode=out["mode"],
                                        latency_ms=int(out["latency_ms"]))
    _log(request.user, case, "suspect", q, out)
    out.pop("retrieval", None) if not request.user.is_staff else None
    return JsonResponse(out)


@_api
@require_POST
def api_explain(request, case):
    d = _json(request)
    st = None
    if d.get("statement_id"):
        st = case.statements.filter(pk=d["statement_id"]).select_related("suspect", "document").first()
    if st is None:
        return JsonResponse({"error": "Unknown statement."}, status=404)
    out = explain_statement(case, st.text, st.suspect.key, st.document.key if st.document else None)
    out["suspect"] = st.suspect.name
    return JsonResponse(out)


@_api
@require_POST
def api_compare(request, case):
    """Compare two statements (NLI with context gating)."""
    d = _json(request)
    a = case.statements.filter(pk=d.get("a")).select_related("suspect").first()
    b = case.statements.filter(pk=d.get("b")).select_related("suspect").first()
    if not a or not b or a.pk == b.pk:
        return JsonResponse({"error": "Choose two different statements."}, status=400)
    lex = lexicon_for_case_id(case.pk)
    res = get_engine().compare(a.text, b.text, lex, a.suspect.key, b.suspect.key)
    out = res.to_dict()
    out.update({"a": {"suspect": a.suspect.name, "text": a.text}, "b": {"suspect": b.suspect.name, "text": b.text}})
    return JsonResponse(out)


@_api
def api_evidence_analysis(request, case, key):
    doc = get_object_or_404(EvidenceDocument, case=case, key=key)
    t0 = time.perf_counter()
    lex = lexicon_for_case_id(case.pk)
    speaker = doc.suspect.key if doc.suspect and doc.doc_type == "Statement" else None
    t1 = time.perf_counter()
    ents = ner_mod.extract_entities(doc.content, lex)
    t2 = time.perf_counter()
    times = [t.to_dict() for t in extract_times(doc.content)]
    t3 = time.perf_counter()
    co = coref_resolve(doc.content, lex, speaker)
    t4 = time.perf_counter()
    sents = [{"sentence": s["sentence"], "stance": s["stance"], "certainty": s["certainty"]}
             for s in __import__("nlp_engine.epistemic", fromlist=["classify_text"]).classify_text(doc.content)
             if s["stance"] not in ("statement",)]
    return JsonResponse({
        "highlighted": ner_mod.highlight_html(doc.content, ents), "entity_summary": ner_mod.entity_summary(ents),
        "times": times, "coreference": {"clusters": [{"name": c["name"], "mentions": [m["text"] for m in c["mentions"]]}
                                                      for c in co["clusters"]],
                                          "resolved": [{"pronoun": r["text"], "refers_to": r.get("antecedent") or "speaker",
                                                        "person": r["person"], "confidence": r["confidence"]}
                                                       for r in co["resolved_pronouns"] if r["kind"] == "pronoun"]},
        "stances": sents,
        "latency_ms": {"ner": round((t2 - t1) * 1000, 1), "temporal": round((t3 - t2) * 1000, 1),
                       "coreference": round((t4 - t3) * 1000, 1), "total": round((time.perf_counter() - t0) * 1000, 1)}})


@_api
@require_POST
def api_important(request, case):
    d = _json(request)
    key = d.get("doc_key")
    if not case.documents.filter(key=key).exists():
        return JsonResponse({"error": "Unknown document."}, status=404)
    p = services.progress_for(request.user, case)
    imp = list(p.important_docs)
    on = key not in imp
    imp = imp + [key] if on else [k for k in imp if k != key]
    p.important_docs = imp
    p.save(update_fields=["important_docs"])
    return JsonResponse({"important": on, "count": len(imp)})


@_api
@require_POST
def api_notebook(request, case):
    d = _json(request)
    p = services.progress_for(request.user, case)
    p.notebook = (d.get("text") or "")[:8000]
    p.save(update_fields=["notebook"])
    return JsonResponse({"saved": True})


def api_status(request):
    """Which NLP backends are active (transparent about fallbacks)."""
    from rag_engine.embeddings import get_embedder
    from nlp_engine.spacy_loader import model_name
    info = {"nli": backend_info(), "spacy": model_name(), "gemini": gemini_available()}
    try:
        info["embedder"] = get_embedder("preferred").name
    except Exception:
        info["embedder"] = "unavailable (run build_index)"
    return JsonResponse(info)
