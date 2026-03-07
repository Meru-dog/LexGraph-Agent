"""embedding_client — multilingual-e5-large embeddings for JP and English text."""

from typing import List
import os

MODEL_NAME = "intfloat/multilingual-e5-large"
EMBEDDING_DIM = 1024


class EmbeddingClient:
    """Sentence transformer wrapper for multilingual-e5-large.

    Phase 0: stub returning zero vectors.
    Phase 3: load model once on startup and batch-encode.
    """

    def __init__(self):
        self._model = None

    def _load_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(MODEL_NAME)
        return self._model

    def embed(self, texts: List[str], prefix: str = "passage") -> List[List[float]]:
        """Embed a list of texts. Prefix: 'query' for queries, 'passage' for chunks."""
        # TODO Phase 3: use real model
        # model = self._load_model()
        # prefixed = [f"{prefix}: {t}" for t in texts]
        # embeddings = model.encode(prefixed, normalize_embeddings=True, batch_size=32)
        # return embeddings.tolist()
        return [[0.0] * EMBEDDING_DIM for _ in texts]

    def embed_query(self, query: str) -> List[float]:
        return self.embed([query], prefix="query")[0]


embedding_client = EmbeddingClient()
