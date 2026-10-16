"""Hybrid retrieval: BM25 (lexical) + dense (semantic) + reciprocal rank fusion.

Lexical search catches exact terms (IDs, names, acronyms).  Dense search
catches meaning and paraphrases.  RRF combines both ranked lists into one.
"""
from __future__ import annotations

import logging
import re
from collections import defaultdict

log = logging.getLogger(__name__)

STOP = {
    "the", "a", "an", "and", "or", "of", "to", "in", "for", "on", "with",
    "is", "are", "was", "were", "be", "by", "as", "at", "from", "that",
    "this", "it", "what", "how", "why", "when", "which", "who", "does",
    "do", "did", "not", "no", "but", "if", "so", "can", "will", "has",
    "have", "had", "been", "would", "should", "could", "may", "might",
}

_TOKEN_RE = re.compile(r"[a-z0-9+#.]+")


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in STOP and len(t) > 1]


class BM25:
    """Okapi BM25 implementation for lexical retrieval."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self._corpus: list[list[str]] = []
        self._doc_ids: list[str] = []
        self._doc_len: list[int] = []
        self._avgdl: float = 0.0
        self._df: dict[str, int] = defaultdict(int)
        self._tf: list[dict[str, int]] = []

    def add_documents(self, doc_id: str, texts: list[str]) -> None:
        for text in texts:
            tokens = tokenize(text)
            self._corpus.append(tokens)
            self._doc_ids.append(doc_id)
            self._doc_len.append(len(tokens))
            tf: dict[str, int] = defaultdict(int)
            for t in tokens:
                tf[t] += 1
            self._tf.append(tf)
            for t in set(tokens):
                self._df[t] += 1
        n = len(self._corpus)
        self._avgdl = sum(self._doc_len) / n if n else 1.0

    def search(self, query: str, k: int = 10, doc_id: str | None = None) -> list[tuple[int, float]]:
        """Return (corpus_index, score) pairs, highest first."""
        tokens = tokenize(query)
        if not tokens or not self._corpus:
            return []
        import math
        n = len(self._corpus)
        scores: list[float] = [0.0] * n
        for t in tokens:
            df = self._df.get(t, 0)
            if df == 0:
                continue
            idf = math.log((n - df + 0.5) / (df + 0.5) + 1.0)
            for i in range(n):
                if doc_id and self._doc_ids[i] != doc_id:
                    continue
                tf = self._tf[i].get(t, 0)
                if tf == 0:
                    continue
                dl = self._doc_len[i]
                score = idf * (tf * (self.k1 + 1)) / (tf + self.k1 * (1 - self.b + self.b * dl / self._avgdl))
                scores[i] += score

        ranked = [(i, s) for i, s in enumerate(scores) if s > 0]
        ranked.sort(key=lambda x: -x[1])
        return ranked[:k]

    def get_texts(self) -> list[list[str]]:
        return self._corpus


def reciprocal_rank_fusion(
    *ranked_lists: list[tuple[int, float]],
    k: int = 60,
) -> list[tuple[int, float]]:
    """Combine multiple ranked lists using RRF (Cormack et al., 2009).

    Each input is a list of (index, score) pairs.  Returns fused
    (index, rrf_score) pairs, highest first.
    """
    fused: dict[int, float] = defaultdict(float)
    for ranked in ranked_lists:
        for rank, (idx, _score) in enumerate(ranked):
            fused[idx] += 1.0 / (k + rank + 1)
    result = sorted(fused.items(), key=lambda x: -x[1])
    return result
