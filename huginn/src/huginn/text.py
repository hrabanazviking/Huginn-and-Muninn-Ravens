"""Text machinery for Huginn: tokenizing, sparse TF-IDF, embedders.

Honesty labels, kept in the open:

* ``tfidf`` scoring is **lexical** semantics — weighted word overlap.
  It is genuinely useful (it powers the local backend and the
  ancestor's ``semantic_search``) but it is not neural embedding
  similarity, and nothing here pretends otherwise.
* The ``hashing`` embedder is deterministic feature hashing: tokens
  are hashed into a fixed-dimension space with signed accumulation.
  Cosine over hashing vectors approximates lexical overlap in vector
  form — again, labelled as what it is.
* ``sentence-transformers`` is the only neural embedder, behind the
  ``embeddings`` extra.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Iterable, Sequence
from typing import Protocol

# The ancestor Huginn's stopword set — kept verbatim for fidelity.
STOPWORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "must", "shall", "can", "to", "of", "in",
    "for", "on", "with", "at", "by", "from", "as", "into", "through",
    "during", "before", "after", "above", "below", "between", "under",
    "again", "further", "then", "once", "here", "there", "when", "where",
    "why", "how",
})

_TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    """Lowercase word tokens, stopwords and 1-char tokens removed."""
    return [
        tok
        for tok in _TOKEN_RE.findall(str(text).lower())
        if len(tok) > 1 and tok not in STOPWORDS
    ]


def term_counts(tokens: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for tok in tokens:
        counts[tok] = counts.get(tok, 0) + 1
    return counts


def idf(doc_freq: int, total_docs: int) -> float:
    """Smoothed inverse document frequency, always positive."""
    if total_docs <= 0:
        return 0.0
    return math.log(1.0 + (total_docs - doc_freq + 0.5) / (doc_freq + 0.5))


def sparse_tfidf(counts: dict[str, int], df: dict[str, int], total_docs: int) -> dict[str, float]:
    """TF-IDF sparse vector for one document/query."""
    if not counts:
        return {}
    total = sum(counts.values())
    return {
        term: (count / total) * idf(df.get(term, 0), total_docs)
        for term, count in counts.items()
    }


def cosine(a: dict[str, float], b: dict[str, float]) -> float:
    """Cosine similarity of two sparse vectors, in [0, 1] for TF-IDF."""
    if not a or not b:
        return 0.0
    if len(a) > len(b):
        a, b = b, a
    dot = sum(w * b.get(term, 0.0) for term, w in a.items())
    if dot <= 0.0:
        return 0.0
    na = math.sqrt(sum(w * w for w in a.values()))
    nb = math.sqrt(sum(w * w for w in b.values()))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return min(1.0, dot / (na * nb))


class Embedder(Protocol):
    """Fixed-space text embedder."""

    name: str
    dim: int

    def embed(self, text: str) -> list[float]:
        ...


class HashingEmbedder:
    """Deterministic feature-hashing embedder (stdlib only).

    Each token is hashed (SHA-256) to a bucket and a sign; counts
    accumulate signed, the result is L2-normalized. Same text always
    gives the same vector, on any machine, forever.
    """

    name = "hashing"

    def __init__(self, dim: int = 384):
        self.dim = int(dim)

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dim
        for tok in tokenize(text):
            digest = hashlib.sha256(tok.encode("utf-8")).digest()
            bucket = int.from_bytes(digest[:4], "little") % self.dim
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[bucket] += sign
        norm = math.sqrt(sum(v * v for v in vector))
        if norm > 0.0:
            vector = [v / norm for v in vector]
        return vector


class SentenceTransformerEmbedder:
    """Neural embedder behind the ``embeddings`` extra."""

    name = "sentence-transformers"

    def __init__(self, model: str = "all-MiniLM-L6-v2"):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            from .errors import HuginnConfigurationError

            raise HuginnConfigurationError(
                "embedder='sentence-transformers' needs the 'embeddings' "
                "extra: pip install 'huginn[embeddings]'"
            ) from exc
        self._model = SentenceTransformer(model)
        self.dim = int(self._model.get_sentence_embedding_dimension())

    def embed(self, text: str) -> list[float]:
        vec = self._model.encode([text], normalize_embeddings=True)[0]
        return [float(v) for v in vec]


def dense_cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b:
        return 0.0
    # strict=False is deliberate: a stored vector written under another
    # embedder/dimension must not crash a read; the overlap is scored.
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return max(0.0, min(1.0, dot / (na * nb)))
