"""Index building: chunks -> embeddings -> FAISS. Used by `manage.py build_index`."""
import time
import numpy as np
from django.conf import settings
from cases.models import Case
from .chunking import build_case_chunks
from .embeddings import LocalSemanticEmbedder, LOCAL_NAME, preferred_backend, reset_cache
from .preprocess import tokens
from .vector_store import CaseIndex


def build_all(force_local=False, verbose=print):
    reset_cache()
    cases = list(Case.objects.prefetch_related("suspects", "documents", "statements", "hints", "timeline").order_by("number"))
    all_chunks = {c.number: [ch.to_dict() for ch in build_case_chunks(c)] for c in cases}
    emb = None if force_local else preferred_backend()
    if emb is None:
        corpus = [f"{ch['title']}. {ch['text']}" for chunks in all_chunks.values() for ch in chunks]
        emb = LocalSemanticEmbedder().fit(corpus)
        emb.save()
        verbose(f"Embedder: {LOCAL_NAME} (local LSA, dim={emb.dim}) fitted on {len(corpus)} chunks")
    else:
        verbose(f"Embedder: {emb.name} (dim={emb.dim})")
    report = []
    for c in cases:
        chunks = all_chunks[c.number]
        t0 = time.perf_counter()
        for ch in chunks:
            ch['ttokens'] = tokens(ch['title'])
            ch['tokens'] = tokens(f"{ch['title']}. {ch['text']}")
        vecs = emb.encode([f"{ch['title']}. {ch['text']}" for ch in chunks])
        CaseIndex.save(c.number, chunks, vecs, emb.name)
        report.append({"case": c.number, "chunks": len(chunks), "seconds": round(time.perf_counter() - t0, 3)})
        verbose(f"  case {c.number}: {len(chunks)} chunks indexed")
    reset_cache()
    return {"embedder": emb.name, "cases": report}
