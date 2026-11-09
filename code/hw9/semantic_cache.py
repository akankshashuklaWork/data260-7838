"""Semantic response cache: query embeddings in a Redis vector index, matched by cosine similarity."""

from __future__ import annotations

import time
from typing import Any

import numpy as np
import redis
from redis.commands.search.field import NumericField, TagField, TextField, VectorField
from redis.commands.search.index_definition import IndexDefinition, IndexType
from redis.commands.search.query import Query

from .config import DEFAULT_THRESHOLD, EMBED_DIM, EMBED_MODEL, PREFIX, REDIS_HOST, REDIS_PORT

INDEX_NAME = f"{PREFIX}_cache_idx"
KEY_PREFIX = f"{PREFIX}:cache:"


class SemanticCache:
    def __init__(self, threshold: float = DEFAULT_THRESHOLD, client: redis.Redis | None = None):
        self.threshold = threshold
        # Binary-safe client: embeddings are stored as raw float32 bytes.
        self.client = client or redis.Redis(host=REDIS_HOST, port=REDIS_PORT)
        self.client.ping()
        self._model = None
        self.ensure_index()

    # ---- embeddings -----------------------------------------------------------------------
    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(EMBED_MODEL)
        return self._model

    def embed(self, text: str) -> np.ndarray:
        """Unit-length vector, so cosine similarity is the dot product."""
        return self.model.encode([text], normalize_embeddings=True)[0].astype(np.float32)

    # ---- index ----------------------------------------------------------------------------
    def ensure_index(self) -> None:
        try:
            self.client.ft(INDEX_NAME).info()
            return
        except redis.ResponseError:
            pass
        schema = (
            TextField("query"),
            TextField("answer"),
            TagField("data_version"),
            TagField("dependency"),
            NumericField("created_at"),
            VectorField(
                "embedding",
                "FLAT",
                {"TYPE": "FLOAT32", "DIM": EMBED_DIM, "DISTANCE_METRIC": "COSINE"},
            ),
        )
        self.client.ft(INDEX_NAME).create_index(
            schema, definition=IndexDefinition(prefix=[KEY_PREFIX], index_type=IndexType.HASH)
        )

    def clear(self) -> int:
        """Remove every cache entry (keys with my prefix only)."""
        keys = list(self.client.scan_iter(match=f"{KEY_PREFIX}*", count=500))
        if keys:
            self.client.delete(*keys)
        return len(keys)

    def count(self) -> int:
        return sum(1 for _ in self.client.scan_iter(match=f"{KEY_PREFIX}*", count=500))

    # ---- lookup and store -----------------------------------------------------------------
    def nearest(self, vector: np.ndarray) -> dict[str, Any] | None:
        """Best cached neighbour (cosine similarity, higher is closer) or None when empty."""
        query = (
            Query("*=>[KNN 1 @embedding $vec AS dist]")
            .sort_by("dist")
            .return_fields("query", "answer", "data_version", "dependency", "dist")
            .dialect(2)
        )
        result = self.client.ft(INDEX_NAME).search(query, query_params={"vec": vector.tobytes()})
        if not result.docs:
            return None
        doc = result.docs[0]
        return {
            "key": doc.id,
            "query": doc.query,
            "answer": doc.answer,
            "data_version": doc.data_version,
            "dependency": doc.dependency,
            "similarity": max(0.0, min(1.0, 1.0 - float(doc.dist))),  # COSINE distance = 1 - cos
        }

    def lookup(
        self, vector: np.ndarray, threshold: float | None = None
    ) -> tuple[dict | None, float]:
        """Return (entry_or_None, best_similarity); a hit needs similarity >= threshold."""
        limit = self.threshold if threshold is None else threshold
        best = self.nearest(vector)
        if best is None:
            return None, 0.0
        return (best if best["similarity"] >= limit else None), best["similarity"]

    def put(
        self, query: str, vector: np.ndarray, answer: str, data_version: str, dependency: str
    ) -> str:
        key = f"{KEY_PREFIX}{abs(hash((query, time.time_ns()))) % 10**12:012d}"
        self.client.hset(
            key,
            mapping={
                "query": query,
                "answer": answer,
                "data_version": data_version,
                "dependency": dependency,
                "created_at": time.time(),
                "embedding": vector.tobytes(),
            },
        )
        return key

    def delete(self, key: str) -> None:
        self.client.delete(key)
