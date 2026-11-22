"""NLP evaluation harness. Computes REAL metrics on the labelled datasets in data/evaluation/ (nothing is hard-coded)."""
import json
import statistics
import time
from pathlib import Path
from django.conf import settings
from cases.models import Case, CaseSolution
from nlp_engine import answer_eval
from nlp_engine.lexicon import CaseLexicon
from nlp_engine.coref import resolve
from nlp_engine.ner import extract_entities
from nlp_engine.nli import backend_info, get_engine
from nlp_engine.spacy_loader import model_name
from nlp_engine.temporal import extract_times
from .retriever import get_retriever


def _load(name):
    return json.loads((Path(settings.MYSTIQ["EVAL_DIR"]) / name).read_text(encoding="utf-8"))


def _prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return {"precision": round(p, 3), "recall": round(r, 3), "f1": round(f, 3), "tp": tp, "fp": fp, "fn": fn}


def _pct(vals, q):
    s = sorted(vals)
    return round(s[min(len(s) - 1, int(q * len(s)))], 1) if s else 0.0


def eval_retrieval(k=3):
    data = _load("retrieval.json")
    p_at, r_at, rr, hit1, hit5, lat, isolation_ok = [], [], [], [], [], [], True
    failures = []
    for item in data["queries"]:
        ret = get_retriever(item["case"])
        out = ret.retrieve(item["query"], top_k=5, use_cache=False)
        lat.append(out["latency_ms"])
        docs = [r["chunk"]["doc_key"] for r in out["results"]]
        isolation_ok &= all(r["chunk"]["case_number"] == item["case"] for r in out["results"])
        rel = set(item["relevant"])
        topk = docs[:k]
        p_at.append(sum(d in rel for d in topk) / k)
        r_at.append(len(rel & set(topk)) / len(rel))
        first = next((i for i, d in enumerate(docs, 1) if d in rel), None)
        rr.append(1 / first if first else 0.0)
        hit1.append(bool(first == 1))
        hit5.append(first is not None)
        if first is None or first > 3:
            failures.append({"query": item["query"], "relevant": sorted(rel), "got": docs[:5]})
    legit_flagged = sum(get_retriever(i["case"]).retrieve(i["query"], use_cache=False)["insufficient"] for i in data["queries"])
    insufficient = [get_retriever(o["case"]).retrieve(o["query"], use_cache=False)["insufficient"] for o in data["off_topic"]]
    return {"n_queries": len(data["queries"]), f"precision@{k}": round(statistics.mean(p_at), 3),
            f"recall@{k}": round(statistics.mean(r_at), 3), "mrr": round(statistics.mean(rr), 3),
            "hit@1": round(statistics.mean(hit1), 3), "hit@5": round(statistics.mean(hit5), 3),
            "case_isolation_ok": isolation_ok, "off_topic_flagged_insufficient": f"{sum(insufficient)}/{len(insufficient)}",
            "legit_queries_wrongly_flagged_insufficient": f"{legit_flagged}/{len(data['queries'])}",
            "latency_ms": {"mean": round(statistics.mean(lat), 1), "p50": _pct(lat, .5), "p95": _pct(lat, .95)},
            "failures": failures, "embedder": get_retriever(1).embedder.name}


def eval_ner():
    data = _load("ner.json")
    cases = {c.number: CaseLexicon.from_case(c) for c in Case.objects.prefetch_related("suspects")}
    res = {}
    for mode in ("mystiq (spaCy + case lexicon + temporal)", "baseline (spaCy only)"):
        tp = fp = fn = 0
        lat = []
        per = {}
        for it in data:
            lex = cases[it["case"]] if mode.startswith("mystiq") else None
            t0 = time.perf_counter()
            ents = extract_entities(it["text"], lex)
            lat.append((time.perf_counter() - t0) * 1000)
            pred = {(e["text"].lower(), e["label"]) for e in ents}
            gold = {(t.lower(), l) for t, l in it["entities"]}
            tp += len(pred & gold); fp += len(pred - gold); fn += len(gold - pred)
            for _, l in gold:
                per.setdefault(l, [0, 0])
                per[l][1] += 1
            for g in gold & pred:
                per[g[1]][0] += 1
        res[mode] = {**_prf(tp, fp, fn), "latency_ms_mean": round(statistics.mean(lat), 1),
                     "per_label_recall": {k: f"{v[0]}/{v[1]}" for k, v in sorted(per.items())}}
    return res


def eval_temporal():
    data = _load("temporal.json")
    tp = fp = fn = 0
    amb_ok = amb_n = 0
    lat, wrong = [], []
    for it in data:
        t0 = time.perf_counter()
        ms = [t for t in extract_times(it["text"], it.get("context", "")) if t.minutes is not None]
        lat.append((time.perf_counter() - t0) * 1000)
        pred = {f"{t.minutes // 60:02d}:{t.minutes % 60:02d}" for t in ms}
        gold = set(it["expected"])
        tp += len(pred & gold); fp += len(pred - gold); fn += len(gold - pred)
        if pred != gold:
            wrong.append({"text": it["text"], "expected": sorted(gold), "got": sorted(pred)})
        if it.get("ambiguous") is not None:
            amb_n += 1
            amb_ok += bool(ms and ms[0].ambiguous == it["ambiguous"])
    return {**_prf(tp, fp, fn), "ambiguity_flag_accuracy": f"{amb_ok}/{amb_n}", "n": len(data),
            "latency_ms_mean": round(statistics.mean(lat), 2), "errors": wrong}


def eval_coref():
    data = _load("coref.json")
    cases = {c.number: CaseLexicon.from_case(c) for c in Case.objects.prefetch_related("suspects")}
    ok = total = 0
    wrong = []
    for it in data:
        out = resolve(it["text"], cases[it["case"]], it["speaker"])
        got = {}
        for r in out["resolved_pronouns"]:
            got[r["text"]] = r["person"]
        for pron, person in it["expect"]:
            total += 1
            if got.get(pron) == person:
                ok += 1
            else:
                wrong.append({"text": it["text"], "pronoun": pron, "expected": person, "got": got.get(pron)})
    return {"accuracy": round(ok / total, 3), "correct": ok, "total": total, "errors": wrong}


def eval_nli():
    data = _load("nli.json")
    cases = {c.number: CaseLexicon.from_case(c) for c in Case.objects.prefetch_related("suspects")}
    eng = get_engine()
    out, lat = {}, []
    labels = ["contradiction", "entailment", "neutral"]
    for subset in ("dev", "fresh", "heldout", "all"):
        rows = [d for d in data if subset == "all" or d["set"] == subset]
        conf = {g: {p: 0 for p in labels} for g in labels}
        wrong = []
        for d in rows:
            t0 = time.perf_counter()
            r = eng.compare(d["premise"], d["hypothesis"], cases[d["case"]], d["premise_speaker"], d["hypothesis_speaker"])
            lat.append((time.perf_counter() - t0) * 1000)
            conf[d["gold"]][r.label] += 1
            if r.label != d["gold"]:
                wrong.append({"premise": d["premise"][:80], "hypothesis": d["hypothesis"][:80], "gold": d["gold"], "pred": r.label, "finding": r.finding})
        acc = sum(conf[l][l] for l in labels) / len(rows)
        per = {}
        for l in labels:
            tp = conf[l][l]; fp = sum(conf[g][l] for g in labels if g != l); fn = sum(conf[l][p] for p in labels if p != l)
            per[l] = _prf(tp, fp, fn)
        # a false contradiction is the worst error in this game
        fc = sum(conf[g]["contradiction"] for g in labels if g != "contradiction")
        out[subset] = {"n": len(rows), "accuracy": round(acc, 3), "per_class": per, "confusion_gold_by_pred": conf,
                       "false_contradictions": fc, "errors": wrong}
    out["backend"] = get_engine().compare("a", "b", cases[1]).backend
    out["latency_ms_mean"] = round(statistics.mean(lat), 1)
    out["latency_ms_p95"] = _pct(lat, .95)
    return out


def eval_answers():
    data = _load("answer_eval.json")
    ok = 0
    rows = []
    for it in data:
        case = Case.objects.get(number=it["case"])
        sol = CaseSolution.objects.get(case=case).data
        emb = get_retriever(case.number).embedder
        frac, _ = answer_eval.explanation_score(it["explanation"], sol["concepts"], emb)
        sus = list(case.suspects.all())
        named = answer_eval.mentioned_suspects(it["explanation"], sus)
        if sol["culprit"] not in named and frac > 0:
            frac *= .6
        pred = "good" if frac >= .66 else "poor" if frac <= .34 else "partial"
        ok += pred == it["expected"]
        rows.append({"case": it["case"], "expected": it["expected"], "pred": pred, "fraction": round(frac, 2)})
    return {"accuracy": round(ok / len(data), 3), "n": len(data), "rows": rows}


def eval_end_to_end():
    """Latency of full service calls (retrieval + generation) in demo mode."""
    from . import generation
    c = Case.objects.get(number=1)
    s = c.suspects.get(key="whitmore")
    ask, sus = [], []
    for q in ["Who was in the hall at half past eight?", "Who took the spare key?", "When did dinner start?"]:
        generation.answer_question(c, q)          # warm-up / caches
        t0 = time.perf_counter(); generation.answer_question(c, q + " "); ask.append((time.perf_counter() - t0) * 1000)
    for q in ["Where were you at 8:30 PM?", "Who has the keys?", "Do you have debts?"]:
        t0 = time.perf_counter(); generation.interrogate(c, s, q); sus.append((time.perf_counter() - t0) * 1000)
    return {"ask_ms_mean": round(statistics.mean(ask), 1), "interrogate_ms_mean": round(statistics.mean(sus), 1)}


def run_all():
    t0 = time.time()
    res = {"environment": {"embedder": get_retriever(1).embedder.name, "nli": backend_info(), "spacy": model_name(),
                           "gemini_used": False},
           "retrieval": eval_retrieval(), "ner": eval_ner(), "temporal": eval_temporal(), "coreference": eval_coref(),
           "nli": eval_nli(), "answer_evaluation": eval_answers(), "end_to_end_latency": eval_end_to_end()}
    res["runtime_seconds"] = round(time.time() - t0, 1)
    return res
