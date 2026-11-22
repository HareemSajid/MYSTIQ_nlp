# MYSTIQ — NLP Evaluation Report
Generated 2026-11-12 by `python manage.py evaluate_nlp`. All numbers below were computed by that command from the labelled files in `data/evaluation/`.

## 1. Environment (which models produced these numbers)
| Component | Backend used in this run |
|---|---|
| Embeddings / retrieval | `local-lsa-tfidf` |
| NLI | symbolic frame-based engine + gating (pretrained NLI model not loaded: ModuleNotFoundError: No module named 'sentence_transformers') |
| spaCy | `en_core_web_sm` |
| LLM generation | Not used (demo mode); the evaluation measures retrieval/NLP, not generated prose |

**Important:** if the row above says `local-lsa-tfidf`, the pretrained Sentence-Transformers model was NOT available in the environment that ran this evaluation. A pretrained transformer is expected to retrieve paraphrased queries better than the local LSA fallback. Re-run `python manage.py build_index` and `python manage.py evaluate_nlp` after `pip install sentence-transformers` to get the pretrained numbers on your machine.

## 2. Retrieval (32 labelled queries, document-level relevance)
| Metric | Value |
|---|---|
| Precision@3 | 0.385 |
| Recall@3 | 0.859 |
| Mean Reciprocal Rank | 0.826 |
| Hit@1 / Hit@5 | 0.719 / 1 |
| Case isolation (no cross-case chunk in any result) | True |
| Off-topic queries correctly flagged "insufficient evidence" | 5/5 |
| Legitimate queries wrongly flagged "insufficient" | 0/32 |
| Retrieval latency mean / p50 / p95 (ms) | 21.3 / 20.8 / 32.3 |

Queries whose relevant document was not in the top 3:
- query: Who last held the emerald before it was locked away? | relevant: ['lord_note'] | got: ['', 'eleanor_statement', 'study_report', 'lord_note', 'message']
- query: Who kept asking where Blackwood would be on Friday? | relevant: ['diary'] | got: ['helen_statement', 'delivery_record', 'police_notice', 'diary', '']
- query: Who sat at the foot of the table? | relevant: ['seating'] | got: ['hale_statement', 'mills_statement', 'service_record', 'seating', '']

Precision@3 is bounded above by (#relevant docs / 3) for queries with 1–2 relevant documents, so values well below 1.0 are expected even for perfect retrieval.

## 3. Named Entity Recognition (2 systems compared on 15 labelled sentences, exact span+label match)
| System | Precision | Recall | F1 | ms/sentence |
|---|---|---|---|---|
| MYSTIQ (spaCy + case lexicon + temporal extractor) | 0.963 | 0.981 | 0.972 | 5.0 |
| Baseline (spaCy only) | 0.706 | 0.453 | 0.552 | 4.1 |

Per-label recall (MYSTIQ): {'DATE': '3/3', 'LOCATION': '11/11', 'OBJECT': '9/9', 'ORGANISATION': '0/1', 'OTHER': '1/1', 'PERSON': '17/17', 'TIME': '11/11'}

## 4. Temporal extraction (27 items)
Precision 1.0, Recall 1.0, F1 1.0 (time values normalised to HH:MM). Ambiguity-flag accuracy: 2/2. Mean latency 0.04 ms.

Errors:
_none_

## 5. Coreference / reference resolution
Accuracy 0.917 (11/12 pronouns). The heuristic is subject-salience + gender agreement + recency; it cannot resolve pragmatic ambiguity.
- text: Dr. Moore saw Carter in the library. He was putting away the case. | pronoun: He | expected: carter | got: moore

## 6. Natural language inference with context gating
Backend: symbolic-frames+gating. Mean latency 11.4 ms (p95 30.2 ms).

| Subset | n | Accuracy | False contradictions |
|---|---|---|---|
| dev (pairs used while building the rules — optimistic) | 13 | 1.0 | 0 |
| fresh (first run scored 0.667 = 10/15 before I used its errors to repair rules, so it is NO LONGER unbiased) | 15 | 1.0 | 0 |
| **heldout** (written last; never used to tune anything — the honest estimate) | 12 | **0.833** | 0 |
| all | 40 | 0.95 | 0 |

Per-class (all): contradiction: P=1.0 R=0.947 F1=0.973, entailment: P=1.0 R=0.5 F1=0.667, neutral: P=0.905 R=1.0 F1=0.95

A *false contradiction* (predicting contradiction for a pair whose gold label is not contradiction) is the most harmful error in this game, because it would send the player after an innocent suspect.

Errors on the held-out set:
- premise: I was in the estate office until ten. | hypothesis: Miss Grey was seen in the estate office at 9:30 PM. | gold: entailment | pred: neutral | finding: no_relation
- premise: I never set foot in the workshop. | hypothesis: Captain Finch entered the workshop at 8:20 PM. | gold: contradiction | pred: neutral | finding: no_relation

## 7. Semantic answer evaluation (14 labelled explanations: good vs. poor)
Accuracy 1.0.


## 8. End-to-end latency (demo mode, no external LLM)
Ask-the-case-files mean 130.1 ms; suspect interrogation mean 14.4 ms. A Gemini call would add its own network latency, which was not measured.

## 9. Limitations (honest)
- The datasets are small (tens of items) and written by the project author; the metrics are indicative, not statistically strong.
- The symbolic NLI engine is rule-based and tuned to the vocabulary of the seven cases; it will not generalise to arbitrary text. The pretrained NLI cross-encoder (when installed) is fused with the same context gating.
- Temporal AM/PM is inferred; such times are flagged `ambiguous`.
- Coreference is heuristic. NER uses spaCy's small model plus a case lexicon, so unseen names depend on spaCy alone.
- Offline demo mode answers are *extractive*: with the local embedder they sometimes quote a less central sentence of the right document (the citations still lead to it). A pretrained embedding model or Gemini gives better answers.
- The `what`/`when` multiple-choice options in the final deduction are written per case; a very careful reader can sometimes infer the culprit from their wording.
- No claim is made of perfect accuracy.
