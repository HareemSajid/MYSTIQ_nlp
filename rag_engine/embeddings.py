"""Embedding backends.

1. SentenceTransformerEmbedder  - pretrained `sentence-transformers/all-MiniLM-L6-v2` (384-d). Preferred.
2. LocalSemanticEmbedder        - offline fallback: lemmatised + synonym-folded + time-normalised TF-IDF (word 1-2 grams)
                                  followed by LSA (TruncatedSVD). It captures paraphrase through synonym folding and
                                  latent co-occurrence, but is much weaker than a pretrained transformer; evaluation
                                  reports state which backend produced each number.
`get_embedder(name)` returns the embedder recorded in an index so queries always use the same space as the documents.
"""
import logging
from pathlib import Path
import numpy as np
from django.conf import settings

log = logging.getLogger(__name__)
LOCAL_NAME = "local-lsa-tfidf"


class SentenceTransformerEmbedder:
    def __init__(self, model_name):
        from sentence_transformers import SentenceTransformer
        self.name = model_name
        self.model = SentenceTransformer(model_name)
        self.dim = self.model.get_sentence_embedding_dimension()

    def encode(self, texts):
        from nlp_engine.temporal import annotate_times
        return np.asarray(self.model.encode([annotate_times(t) for t in texts], normalize_embeddings=True,
                                            show_progress_bar=False), dtype="float32")


class LocalSemanticEmbedder:
    def __init__(self):
        self.name = LOCAL_NAME
        self.vec, self.svd, self.dim = None, None, 0

    @staticmethod
    def path():
        return Path(settings.MYSTIQ["VECTOR_DIR"]) / "local_embedder.joblib"

    def fit(self, texts):
        from sklearn.decomposition import TruncatedSVD
        from sklearn.feature_extraction.text import TfidfVectorizer
        from .preprocess import prep
        prepped = [prep(t) for t in texts]
        self.vec = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=1, token_pattern=r"(?u)\b\w+\b")
        X = self.vec.fit_transform(prepped)
        k = max(8, min(160, X.shape[0] - 1, X.shape[1] - 1))
        self.svd = TruncatedSVD(n_components=k, random_state=7)
        self.svd.fit(X)
        self.dim = k
        return self

    def save(self):
        import joblib
        self.path().parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"vec": self.vec, "svd": self.svd, "dim": self.dim}, self.path())

    @classmethod
    def load(cls):
        import joblib
        obj = joblib.load(cls.path())
        e = cls()
        e.vec, e.svd, e.dim = obj["vec"], obj["svd"], obj["dim"]
        return e

    def encode(self, texts):
        from .preprocess import prep
        X = self.vec.transform([prep(t) for t in texts])
        Z = self.svd.transform(X)
        # concatenate a damped copy of the (L2-normalised) sparse TF-IDF space via random projection would add noise;
        # the LSA vector alone is normalised and used for cosine search.
        n = np.linalg.norm(Z, axis=1, keepdims=True)
        n[n == 0] = 1.0
        return (Z / n).astype("float32")


_cache = {}


def preferred_backend():
    """Try the pretrained model first (unless NLP_BACKEND=local)."""
    cfg = settings.MYSTIQ
    if cfg["NLP_BACKEND"] != "local":
        try:
            return SentenceTransformerEmbedder(cfg["EMBEDDING_MODEL"])
        except Exception as exc:
            if cfg["NLP_BACKEND"] == "transformers":
                raise
            log.warning("Sentence-Transformers unavailable (%s: %s); using local embedder", type(exc).__name__, str(exc)[:120])
    return None


def get_embedder(name=None):
    key = name or "preferred"
    if key in _cache:
        return _cache[key]
    emb = None
    if name in (None, "preferred"):
        emb = preferred_backend()
        if emb is None:
            emb = LocalSemanticEmbedder.load()
    elif name == LOCAL_NAME:
        emb = LocalSemanticEmbedder.load()
    else:
        emb = SentenceTransformerEmbedder(name)
    _cache[key] = emb
    _cache[emb.name] = emb
    return emb


def reset_cache():
    _cache.clear()
