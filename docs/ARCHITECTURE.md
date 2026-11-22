# MYSTIQ — Architecture

```
Browser (Django templates + vanilla JS)
   │  fetch JSON (CSRF)                         ┌────────────────────────────────────────────┐
   ▼                                            │ nlp_engine (pure NLP, no Django views)     │
game/ (views, services, models) ───────────────►│ temporal · ner · coref · epistemic · frames│
   │  scoring, unlocking, deduction (no LLM)    │ nli (model + symbolic + gating) · leakage  │
   │                                            │ reasoning (explainable evidence) · answer_eval
   ▼                                            └───────────────▲────────────────────────────┘
rag_engine/                                                     │ uses
   chunking → embeddings → vector_store (FAISS/case) ─ retriever (dense+BM25+rerank+filters)
   generation (analyst / Watson / suspect) → llm (Gemini REST) | demo generator → guard (leak/secret/citation checks)
   evaluation + report                               cases/ (YAML loader, models, protected CaseSolution)
```

## Data model (Django ORM, SQLite; PostgreSQL-compatible)
`accounts.Profile` · `cases.Case, Suspect, EvidenceDocument, Statement, TimelineEvent, Hint, CaseSolution` ·
`game.PlayerProgress, HintUsage, Interrogation, InterrogationMessage, WatsonMessage, FinalDeduction, Score, RetrievedEvidenceLog`.
Unique constraints: (case,key) for suspects/documents, (user,case) for progress/score, (user,hint), (case,hint order).
`CaseSolution` is never serialised, never indexed, never registered in the admin and is only read by server-side evaluation.

## RAG pipeline (per query)
1. **Understand** the question (`nlp_engine.question`): intent, entities (case lexicon + spaCy), time expressions normalised to minutes.
2. **Embed** the query with the same embedder recorded in the index (Sentence-Transformers `all-MiniLM-L6-v2` if available, else the local lemma/synonym/time-token LSA embedder).
3. **Dense search** in the case's own FAISS `IndexFlatIP` (one physical index per case ⇒ no cross-case leakage).
4. **BM25** over lemmatised, synonym-folded tokens that also contain canonical time tokens (`t2120` for "nine twenty" and "9:20 PM").
5. **Metadata filters**: `audience` (`public` / `watson` / `suspect:<key>`), `kind`, hint release (`hint_order ≤ released`).
6. **Fusion** 0.6·dense + 0.4·BM25-normalised, then **reranking** by entity match, time match, document focus (+ optional cross-encoder via `MYSTIQ_RERANK_MODEL`).
7. **Near-duplicate suppression**, top-k with similarity scores, **insufficient-evidence** decision.
8. **Generate**: Gemini (only the retrieved excerpts, citation rules) or the offline demo generator (sentence-level semantic selection + stance annotation). Output **guards** reject culprit leaks, secret text and invalid citations and fall back to the grounded demo answer.

Chunks: sentence-aware windows (~70 words, 1-sentence overlap), metadata = case, kind, doc, suspect, author, date, audience, persons, time minutes.
Precomputed: embeddings, FAISS indexes, BM25 tokens (stored in `vector_store/`). Retrieval results are cached in-process (LRU-style, 512 entries).

## NLP components
| Requirement | Implementation |
|---|---|
| Semantic search | Sentence-Transformers (preferred) / local LSA fallback + BM25 hybrid |
| NLI | `cross-encoder/nli-MiniLM2-L6-H768` if installed **and** a frame-based symbolic engine; always fused with *comparability gating* (same person, day, place, time window) |
| NER | spaCy `en_core_web_sm` + case lexicon (PhraseMatcher) + temporal extractor; labels PERSON, LOCATION, DATE, TIME, ORGANISATION, OBJECT, OTHER |
| Temporal | regex/word-number grammar → minutes, precision, ambiguity & AM/PM-inference flags; auto timeline by day, record vs claim |
| Coreference | spaCy dependency parse + roster: gender agreement, recency, subject salience, role aliases ("the stout gentleman"), first person → speaker |
| Epistemic stance | observation / assumption / hearsay / denial / absence-of-observation |
| Implicit knowledge | `leakage.py`: details found only in private sources and absent from every public source |
| Literal vs implied | scope rule in NLI (e.g. "never touched *his* key" vs "a *second* key") |
| Explainable reasoning | `reasoning.explain_statement`: retrieve → frame → NLI → explanation + source documents |
| Answer evaluation | deterministic key (culprit, choices, evidence set) + semantic concept coverage (embedding cosine blended with lemma/keyword coverage) |

## Security & integrity
Server-side evaluation only; deduction page sends option ids and text, never the `correct` flag; case/endpoint access control by unlock state;
CSRF on all POSTs; Django password hashing and validators; API errors are JSON; no secrets in the repository (`.env` is git-ignored).

## Performance
No LLM call for navigation, hints, scoring or unlocking. Typical retrieval ≈ 15–30 ms; `evaluate_nlp` measures retrieval, NER, temporal, NLI and end-to-end latency (see `docs/NLP_EVALUATION_REPORT.md`).
