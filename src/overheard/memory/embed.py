"""Embeddings for retrieval, behind a Protocol. The demo's only provider is the mock, which still has to capture
similarity (or retrieval returns noise and the learning demo fails): hashed bag-of-words. Tokenise, drop stop words,
hash each word and each pair of adjacent words into a fixed number of buckets, weight by inverse document frequency
(from the corpus it's fitted on), normalise. Deterministic, standard library only; similar wording gives similar
vectors. A real provider can come later behind the same Protocol."""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from typing import Protocol

Vector = dict[int, float]   # sparse: bucket -> weight, unit length

STOP = frozenset("""a about am an and are as at be been but by can could did do does for from get got had has have
he her hi him his how i i'm if in is it it's its just me my no not now of on or our please she so that the their them
then there they this to um uh us was we well were what when which who why will with would yes you your yeah okay
hello thank thanks call calling""".split())
BUCKETS = 1 << 12


class EmbeddingProvider(Protocol):
    def embed(self, text: str) -> Vector: ...


def tokens(text: str) -> list[str]:
    """Words (stop words dropped), adjacent pairs, and any "type:..." label as it is."""
    low = text.lower()
    labels = re.findall(r"type:[a-z0-9-]+", low)
    words = [w for w in re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", re.sub(r"type:[a-z0-9-]+", " ", low))
             if w not in STOP and len(w) > 1]
    return labels + words + [f"{a}_{b}" for a, b in zip(words, words[1:], strict=False)]


def bucket(tok: str) -> int:
    return int.from_bytes(hashlib.blake2b(tok.encode(), digest_size=4).digest(), "big") % BUCKETS


class MockEmbeddingProvider:
    def __init__(self, corpus: list[str] = ()):
        df = Counter(b for t in corpus for b in {bucket(x) for x in tokens(t)})
        n = max(1, len(corpus))
        self.idf = {b: math.log((1 + n) / (1 + c)) + 1 for b, c in df.items()}
        self.default_idf = math.log(1 + n) + 1

    def embed(self, text: str) -> Vector:
        toks = tokens(text)
        tf = Counter(bucket(t) for t in toks)
        labels = {bucket(t) for t in toks if t.startswith("type:")}   # a label weighs fully, however common
        v = {b: c * (self.default_idf if b in labels else self.idf.get(b, self.default_idf)) for b, c in tf.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return {b: round(x / norm, 5) for b, x in v.items()}


def cosine(a: Vector, b: Vector) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(x * b.get(k, 0.0) for k, x in a.items())
