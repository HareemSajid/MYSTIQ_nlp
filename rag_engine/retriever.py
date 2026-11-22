"""Hybrid, case-isolated retriever: dense (FAISS) + lexical (BM25) fusion, metadata filters, entity/time-aware reranking.

Pipeline (per query)
  1 understand question (intent, entities, time expressions)      7 normalise + fuse dense and BM25 scores
  2 embed query (same embedder as the index)                      8 rerank (entity / time / document-focus signals,
  3 FAISS exhaustive inner-product search inside THIS case             optional cross-encoder)
  4 BM25 over lemmatised, synonym-folded, time-annotated tokens   9 top-k with similarity scores
  5 metadata filters: audience, kind, suspect, hint release      10 insufficient-evidence decision
  6 (case isolation: one physical index per case)
"""
import time
from django.conf import settings
from nlp_engine.lexicon import lexicon_for_case_id
from nlp_engine.question import understand
from .bm25 import BM25
from .embeddings import get_embedder
from .preprocess import tokens
from .vector_store import CaseIndex

_retrievers = {}
_cache = {}
_CACHE_MAX = 512


class CaseRetriever:
    def __init__(self, case_number):
        if not CaseIndex.exists(case_number):
            raise RuntimeError(f"No vector index for case {case_number}. Run: python manage.py build_index")
        self.case_number = case_number
        self.index = CaseIndex.load(case_number)
        self.embedder = get_embedder(self.index.embedder_name)
        self.chunks = self.index.chunks
        self.bm25 = BM25([c.get("tokens") or tokens(f"{c['title']}. {c['text']}") for c in self.chunks])
        self._title_tokens = [set(c.get("ttokens") or tokens(c["title"])) for c in self.chunks]
        self._reranker = None
        self._case_id = None

    # -- helpers
    def _lex(self):
        if self._case_id is None:
            from cases.models import Case
            self._case_id = Case.objects.get(number=self.case_number).pk
        return lexicon_for_case_id(self._case_id)

    def _allowed(self, c, audiences, kinds, suspect_key, hint_max):
        aud = c["audience"]
        if aud == "watson":
            if "watson" not in audiences or c["hint_order"] > hint_max:
                return False
        elif aud not in audiences:
            return False
        if kinds and c["kind"] not in kinds:
            return False
        return True

    def _cross_encoder(self):
        name = settings.MYSTIQ["RERANK_MODEL"]
        if not name:
            return None
        if self._reranker is None:
            try:
                from sentence_transformers import CrossEncoder
                self._reranker = CrossEncoder(name)
            except Exception:
                self._reranker = False
        return self._reranker or None

    # -- main entry
    def retrieve(self, query, top_k=None, audiences=("public",), kinds=None, suspect_key=None, doc_key=None,
                 hint_max=0, use_cache=True, mode="hybrid"):
        if mode not in ("hybrid", "dense", "bm25"):
            raise ValueError(f"unknown retrieval mode {mode!r}")
        top_k = top_k or settings.MYSTIQ["TOP_K"]
        key = (self.case_number, query.strip().lower(), top_k, tuple(sorted(audiences)), tuple(sorted(kinds or ())),
               suspect_key, doc_key, hint_max, mode)
        if use_cache and key in _cache:
            out = dict(_cache[key])
            out["cached"] = True
            return out
        t0 = time.perf_counter()
        und = understand(query, self._lex())
        t_understand = time.perf_counter()
        qvec = self.embedder.encode([query])[0]
        dense = self.index.search_all(qvec)
        t_dense = time.perf_counter()
        qtok = tokens(query)
        qtok += [t["token"] for t in und["times"] if t["token"]]
        bm = self.bm25.scores(qtok)
        bm_max = max(bm) if bm else 0.0
        t_bm = time.perf_counter()
        cand = []
        qset = {t for t in qtok if not t.startswith("t") or not t[1:].isdigit()}
        for i, c in enumerate(self.chunks):
            if not self._allowed(c, audiences, kinds, suspect_key, hint_max):
                continue
            d = float(max(0.0, dense[i]))
            b = float(bm[i] / bm_max) if bm_max > 0 else 0.0
            fused = {"hybrid": 0.6 * d + 0.4 * b, "dense": d, "bm25": b}[mode]
            bonus = 0.0
            if mode != "hybrid":      # ablation modes: pure single-signal ranking, no heuristic bonuses
                cand.append({"chunk": c, "dense": d, "bm25": float(bm[i]), "bm25_norm": b, "fused": fused, "score": fused})
                continue
            hits = len(set(und["people"]) & (set(c["persons"]) | ({c["suspect_key"]} if c["suspect_key"] else set())))
            bonus += min(0.12, 0.06 * hits)
            for t in und["times"]:
                if t["minutes"] in c["times"]:
                    bonus += 0.08
                    break
                if any(abs(t["minutes"] - m) <= 10 for m in c["times"]):
                    bonus += 0.04
                    break
            title_hits = len(qset & self._title_tokens[i])         # query names the document ("the threatening letter")
            if c["kind"] in ("document", "statement") and title_hits:
                bonus += min(0.3, 0.12 * title_hits)
            if doc_key and c["doc_key"] == doc_key:
                bonus += 0.10
            if c["kind"] in ("statement", "document"):
                bonus += 0.02
            cand.append({"chunk": c, "dense": d, "bm25": float(bm[i]), "bm25_norm": b, "fused": fused,
                         "score": fused + bonus})
        cand.sort(key=lambda r: -r["score"])
        pool = cand[:max(top_k * 3, 12)]
        ce = self._cross_encoder()
        if ce and pool:
            scores = ce.predict([(query, r["chunk"]["text"]) for r in pool])
            for r, s in zip(pool, scores):
                r["rerank"] = float(s)
                r["score"] = 0.5 * r["score"] + 0.5 * float(1 / (1 + pow(2.71828, -s)))
            pool.sort(key=lambda r: -r["score"])
        t_rr = time.perf_counter()
        top = _dedupe(pool, top_k)
        for rank, r in enumerate(top, 1):
            r["rank"] = rank
        cfg = settings.MYSTIQ
        insufficient = (not top) or (top[0]["dense"] < cfg["MIN_SCORE"] and top[0]["bm25"] < 2.0)
        # the offline LSA embedder produces spurious dense similarity for unrelated text; require some lexical support
        if top and self.embedder.name == "local-lsa-tfidf" and max(r["bm25"] for r in top) == 0:
            insufficient = True
        out = {"results": top, "insufficient": insufficient, "understanding": und, "backend": self.embedder.name,
               "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
               "stages_ms": {"understand": round((t_understand - t0) * 1000, 2), "dense": round((t_dense - t_understand) * 1000, 2),
                             "bm25": round((t_bm - t_dense) * 1000, 2), "rerank": round((t_rr - t_bm) * 1000, 2)},
               "cached": False, "mode": mode}
        if use_cache:
            if len(_cache) >= _CACHE_MAX:
                _cache.pop(next(iter(_cache)))
            _cache[key] = out
        return out


def _words(text):
    import re
    return set(re.findall(r"[a-z0-9']+", text.lower()))


def _dedupe(pool, k, thresh=0.8):
    """Keep the best-ranked of near-duplicate chunks (e.g. a statement, its sentence and its timeline entry)."""
    out, seen = [], []
    for r in pool:
        w = _words(r["chunk"]["text"])
        if any(len(w & v) / max(1, min(len(w), len(v))) > thresh for v in seen):
            continue
        seen.append(w)
        out.append(r)
        if len(out) >= k:
            break
    return out


def get_retriever(case_number):
    if case_number not in _retrievers:
        _retrievers[case_number] = CaseRetriever(case_number)
    return _retrievers[case_number]


def reset_retrievers():
    _retrievers.clear()
    _cache.clear()
