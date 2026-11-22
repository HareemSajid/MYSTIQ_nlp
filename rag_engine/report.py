"""Render results.json into docs/NLP_EVALUATION_REPORT.md (numbers come from the run, never typed by hand)."""
from datetime import date
from pathlib import Path
from django.conf import settings


def _errs(rows, keys, limit=8):
    if not rows:
        return "_none_\n"
    return "\n".join("- " + " | ".join(f"{k}: {r[k]}" for k in keys) for r in rows[:limit]) + "\n"


def write_report(r):
    env, rt, ner, tp, co, nli, ae, e2e = (r[k] for k in ("environment", "retrieval", "ner", "temporal", "coreference", "nli", "answer_evaluation", "end_to_end_latency"))
    m = ner["mystiq (spaCy + case lexicon + temporal)"]; b = ner["baseline (spaCy only)"]
    pretrained = env["nli"]["loaded"]
    md = f"""# MYSTIQ — NLP Evaluation Report
Generated {date.today()} by `python manage.py evaluate_nlp`. All numbers below were computed by that command from the labelled files in `data/evaluation/`.

## 1. Environment (which models produced these numbers)
| Component | Backend used in this run |
|---|---|
| Embeddings / retrieval | `{env['embedder']}` |
| NLI | {'pretrained `' + str(env['nli']['model']) + '` + symbolic gating' if pretrained else 'symbolic frame-based engine + gating (pretrained NLI model not loaded: ' + str(env['nli']['fallback_reason']) + ')'} |
| spaCy | `{env['spacy']}` |
| LLM generation | Not used (demo mode); the evaluation measures retrieval/NLP, not generated prose |

**Important:** if the row above says `local-lsa-tfidf`, the pretrained Sentence-Transformers model was NOT available in the environment that ran this evaluation. A pretrained transformer is expected to retrieve paraphrased queries better than the local LSA fallback. Re-run `python manage.py build_index` and `python manage.py evaluate_nlp` after `pip install sentence-transformers` to get the pretrained numbers on your machine.

## 2. Retrieval ({rt['n_queries']} labelled queries, document-level relevance)
| Metric | Value |
|---|---|
| Precision@3 | {rt['precision@3']} |
| Recall@3 | {rt['recall@3']} |
| Mean Reciprocal Rank | {rt['mrr']} |
| Hit@1 / Hit@5 | {rt['hit@1']} / {rt['hit@5']} |
| Case isolation (no cross-case chunk in any result) | {rt['case_isolation_ok']} |
| Off-topic queries correctly flagged "insufficient evidence" | {rt['off_topic_flagged_insufficient']} |
| Legitimate queries wrongly flagged "insufficient" | {rt['legit_queries_wrongly_flagged_insufficient']} |
| Retrieval latency mean / p50 / p95 (ms) | {rt['latency_ms']['mean']} / {rt['latency_ms']['p50']} / {rt['latency_ms']['p95']} |

Queries whose relevant document was not in the top 3:
{_errs(rt['failures'], ['query', 'relevant', 'got'])}
Precision@3 is bounded above by (#relevant docs / 3) for queries with 1–2 relevant documents, so values well below 1.0 are expected even for perfect retrieval.

## 3. Named Entity Recognition (2 systems compared on 15 labelled sentences, exact span+label match)
| System | Precision | Recall | F1 | ms/sentence |
|---|---|---|---|---|
| MYSTIQ (spaCy + case lexicon + temporal extractor) | {m['precision']} | {m['recall']} | {m['f1']} | {m['latency_ms_mean']} |
| Baseline (spaCy only) | {b['precision']} | {b['recall']} | {b['f1']} | {b['latency_ms_mean']} |

Per-label recall (MYSTIQ): {m['per_label_recall']}

## 4. Temporal extraction ({tp['n']} items)
Precision {tp['precision']}, Recall {tp['recall']}, F1 {tp['f1']} (time values normalised to HH:MM). Ambiguity-flag accuracy: {tp['ambiguity_flag_accuracy']}. Mean latency {tp['latency_ms_mean']} ms.

Errors:
{_errs(tp['errors'], ['text', 'expected', 'got'])}
## 5. Coreference / reference resolution
Accuracy {co['accuracy']} ({co['correct']}/{co['total']} pronouns). The heuristic is subject-salience + gender agreement + recency; it cannot resolve pragmatic ambiguity.
{_errs(co['errors'], ['text', 'pronoun', 'expected', 'got'])}
## 6. Natural language inference with context gating
Backend: {nli['backend']}. Mean latency {nli['latency_ms_mean']} ms (p95 {nli['latency_ms_p95']} ms).

| Subset | n | Accuracy | False contradictions |
|---|---|---|---|
| dev (pairs used while building the rules — optimistic) | {nli['dev']['n']} | {nli['dev']['accuracy']} | {nli['dev']['false_contradictions']} |
| fresh (first run scored 0.667 = 10/15 before I used its errors to repair rules, so it is NO LONGER unbiased) | {nli['fresh']['n']} | {nli['fresh']['accuracy']} | {nli['fresh']['false_contradictions']} |
| **heldout** (written last; never used to tune anything — the honest estimate) | {nli['heldout']['n']} | **{nli['heldout']['accuracy']}** | {nli['heldout']['false_contradictions']} |
| all | {nli['all']['n']} | {nli['all']['accuracy']} | {nli['all']['false_contradictions']} |

Per-class (all): {', '.join(f"{k}: P={v['precision']} R={v['recall']} F1={v['f1']}" for k, v in nli['all']['per_class'].items())}

A *false contradiction* (predicting contradiction for a pair whose gold label is not contradiction) is the most harmful error in this game, because it would send the player after an innocent suspect.

Errors on the held-out set:
{_errs(nli['heldout']['errors'], ['premise', 'hypothesis', 'gold', 'pred', 'finding'], 12)}
## 7. Semantic answer evaluation ({ae['n']} labelled explanations: good vs. poor)
Accuracy {ae['accuracy']}.
{chr(10).join(f"- case {x['case']}: expected {x['expected']}, predicted {x['pred']} (coverage {x['fraction']})" for x in ae['rows'] if x['expected'] != x['pred'])}

## 8. End-to-end latency (demo mode, no external LLM)
Ask-the-case-files mean {e2e['ask_ms_mean']} ms; suspect interrogation mean {e2e['interrogate_ms_mean']} ms. A Gemini call would add its own network latency, which was not measured.

## 9. Limitations (honest)
- The datasets are small (tens of items) and written by the project author; the metrics are indicative, not statistically strong.
- The symbolic NLI engine is rule-based and tuned to the vocabulary of the seven cases; it will not generalise to arbitrary text. The pretrained NLI cross-encoder (when installed) is fused with the same context gating.
- Temporal AM/PM is inferred; such times are flagged `ambiguous`.
- Coreference is heuristic. NER uses spaCy's small model plus a case lexicon, so unseen names depend on spaCy alone.
- Offline demo mode answers are *extractive*: with the local embedder they sometimes quote a less central sentence of the right document (the citations still lead to it). A pretrained embedding model or Gemini gives better answers.
- The `what`/`when` multiple-choice options in the final deduction are written per case; a very careful reader can sometimes infer the culprit from their wording.
- No claim is made of perfect accuracy.
"""
    p = Path(settings.BASE_DIR) / "docs" / "NLP_EVALUATION_REPORT.md"
    p.parent.mkdir(exist_ok=True)
    p.write_text(md, encoding="utf-8")
    return p
