"""Per-case vector index (FAISS, inner product on L2-normalised vectors) with a JSON sidecar for chunk metadata.

One physical index per case guarantees case isolation; metadata filters (audience, kind, suspect, hint_order) are then
applied inside the case. The index is prebuilt (`manage.py build_index`) and loaded lazily into memory.
"""
import json
import time
from pathlib import Path
import numpy as np
from django.conf import settings

try:
    import faiss
except Exception:  # pragma: no cover
    faiss = None


def _dir():
    d = Path(settings.MYSTIQ["VECTOR_DIR"])
    d.mkdir(parents=True, exist_ok=True)
    return d


class CaseIndex:
    def __init__(self, case_number, chunks, vectors, embedder_name):
        self.case_number = case_number
        self.chunks = chunks            # list[dict]
        self.vectors = vectors          # np.ndarray (n, d)
        self.embedder_name = embedder_name
        self.index = None
        if faiss is not None:
            self.index = faiss.IndexFlatIP(vectors.shape[1])
            self.index.add(vectors)

    def search_all(self, qvec):
        """Cosine similarity of the query against every chunk of this case (FAISS exhaustive inner-product search)."""
        n = len(self.chunks)
        if self.index is not None:
            sims, ids = self.index.search(qvec.reshape(1, -1).astype("float32"), n)
            full = np.zeros(n, dtype="float32")
            full[ids[0]] = sims[0]
            return full
        return (self.vectors @ qvec.reshape(-1)).astype("float32")

    @staticmethod
    def save(case_number, chunks, vectors, embedder_name):
        d = _dir()
        if faiss is not None:
            idx = faiss.IndexFlatIP(vectors.shape[1])
            idx.add(vectors.astype("float32"))
            faiss.write_index(idx, str(d / f"case_{case_number}.faiss"))
        np.save(d / f"case_{case_number}.npy", vectors.astype("float32"))
        (d / f"case_{case_number}.json").write_text(json.dumps(
            {"embedder": embedder_name, "case_number": case_number, "built": time.strftime("%Y-%m-%d %H:%M:%S"),
             "chunks": chunks}, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def exists(case_number):
        d = _dir()
        return (d / f"case_{case_number}.json").exists() and (d / f"case_{case_number}.npy").exists()

    @classmethod
    def load(cls, case_number):
        d = _dir()
        meta = json.loads((d / f"case_{case_number}.json").read_text(encoding="utf-8"))
        vecs = np.load(d / f"case_{case_number}.npy")
        return cls(case_number, meta["chunks"], vecs, meta["embedder"])
