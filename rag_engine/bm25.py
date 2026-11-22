import math
from collections import Counter


class BM25:
    def __init__(self, docs_tokens, k1=1.5, b=0.75):
        self.docs = docs_tokens
        self.k1, self.b = k1, b
        self.N = len(docs_tokens)
        self.avgdl = sum(len(d) for d in docs_tokens) / max(1, self.N)
        df = Counter()
        for d in docs_tokens:
            df.update(set(d))
        self.idf = {t: math.log(1 + (self.N - n + 0.5) / (n + 0.5)) for t, n in df.items()}
        self.tf = [Counter(d) for d in docs_tokens]

    def scores(self, query_tokens):
        out = []
        for i, tf in enumerate(self.tf):
            dl = len(self.docs[i]) or 1
            s = 0.0
            for t in query_tokens:
                if t in tf:
                    f = tf[t]
                    s += self.idf.get(t, 0) * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
            out.append(s)
        return out
