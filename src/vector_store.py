"""Thin wrapper around zvec for semantic memory search.

Embeds text with sentence-transformers (all-MiniLM-L6-v2, ~80MB, CPU only)
and stores vectors in a local zvec collection.  Falls back gracefully if
zvec or sentence-transformers aren't installed or incompatible with the CPU.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from typing import Any

log = logging.getLogger(__name__)

# Lazy-loaded at runtime so the rest of the app works without these deps.
_zvec: Any = None
_SentenceTransformer: Any = None


def _probe_zvec() -> bool:
    """Check if zvec can be imported without crashing (e.g. SIGILL on old CPUs)."""
    try:
        result = subprocess.run(
            [sys.executable, "-c", "import zvec"],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except Exception:
        return False


def _import_deps() -> bool:
    """Try to import zvec and sentence_transformers; return True on success."""
    global _zvec, _SentenceTransformer  # noqa: PLW0603
    if _zvec is not None:
        return True

    # Probe zvec in a subprocess first to avoid SIGILL crash in this process
    if not _probe_zvec():
        return False

    try:
        import zvec as _zvec_mod
        from sentence_transformers import SentenceTransformer as _ST

        _zvec = _zvec_mod
        _SentenceTransformer = _ST
        return True
    except ImportError:
        return False


class VectorStore:
    """CPU-only semantic vector store backed by zvec.

    Parameters
    ----------
    path : str
        Directory for the zvec collection (will be created).
    model_name : str
        HuggingFace model id for the embedding model.
    device : str
        Torch device for embeddings (should stay "cpu" to preserve GPU for LLMs).
    """

    VECTOR_DIM = 384  # all-MiniLM-L6-v2 output dimension
    VECTOR_FIELD = "embedding"

    def __init__(
        self,
        path: str = "~/.local/share/talking-llm/vectors",
        model_name: str = "all-MiniLM-L6-v2",
        device: str = "cpu",
    ):
        self._path = os.path.expanduser(path)
        self._model_name = model_name
        self._device = device
        self._model: Any = None  # lazy SentenceTransformer
        self._collection: Any = None
        self._available = _import_deps()

        if self._available:
            try:
                self._open_or_create()
            except Exception as e:
                log.warning("Failed to open vector store: %s", e)
                self._available = False
        else:
            log.warning(
                "zvec or sentence-transformers not available; "
                "semantic search disabled (falling back to substring)"
            )

    @property
    def available(self) -> bool:
        return self._available and self._collection is not None

    # -- Public API --

    def add(self, doc_id: str, text: str, metadata: dict[str, str] | None = None) -> None:
        """Embed *text* and store it under *doc_id*."""
        if not self.available:
            return
        vec = self._embed(text)
        fields = {"text": text}
        if metadata:
            fields.update(metadata)
        doc = _zvec.Doc(id=doc_id, vectors={self.VECTOR_FIELD: vec}, fields=fields)
        try:
            self._collection.insert(doc)
        except Exception:
            # If doc already exists, delete and re-insert (upsert)
            try:
                self._collection.delete(ids=doc_id)
                self._collection.insert(doc)
            except Exception as e:
                log.warning("vector store insert failed for %s: %s", doc_id, e)

    def search(self, query_text: str, limit: int = 5) -> list[dict]:
        """Return up to *limit* results sorted by semantic similarity.

        Each result is ``{"id": str, "text": str, "score": float, **fields}``.
        """
        if not self.available:
            return []
        vec = self._embed(query_text)
        query = _zvec.VectorQuery(field_name=self.VECTOR_FIELD, vector=vec)
        try:
            results = self._collection.query(vectors=query, topk=limit)
        except Exception as e:
            log.warning("vector search failed: %s", e)
            return []

        out: list[dict] = []
        for doc in results:
            entry: dict[str, Any] = {
                "id": doc.id,
                "score": doc.score,
            }
            if doc.fields:
                entry.update(doc.fields)
            out.append(entry)
        return out

    def delete(self, doc_id: str) -> None:
        """Remove a document by id."""
        if not self.available:
            return
        try:
            self._collection.delete(ids=doc_id)
        except Exception as e:
            log.debug("vector store delete for %s: %s", doc_id, e)

    # -- Internal --

    def _open_or_create(self) -> None:
        """Open the zvec collection, creating it if it doesn't exist."""
        os.makedirs(self._path, exist_ok=True)
        try:
            self._collection = _zvec.open(path=self._path)
            log.info("Opened existing vector store at %s", self._path)
        except Exception:
            # Collection doesn't exist yet — create it
            schema = _zvec.CollectionSchema(
                name="memories",
                fields=[
                    _zvec.FieldSchema(
                        name="text",
                        data_type=_zvec.DataType.STRING,
                        nullable=True,
                    ),
                    _zvec.FieldSchema(
                        name="key",
                        data_type=_zvec.DataType.STRING,
                        nullable=True,
                    ),
                    _zvec.FieldSchema(
                        name="category",
                        data_type=_zvec.DataType.STRING,
                        nullable=True,
                    ),
                    _zvec.FieldSchema(
                        name="source",
                        data_type=_zvec.DataType.STRING,
                        nullable=True,
                    ),
                ],
                vectors=[
                    _zvec.VectorSchema(
                        name=self.VECTOR_FIELD,
                        data_type=_zvec.DataType.VECTOR_FP32,
                        dimension=self.VECTOR_DIM,
                        index_param=_zvec.HnswIndexParam(
                            metric_type=_zvec.MetricType.COSINE,
                        ),
                    ),
                ],
            )
            self._collection = _zvec.create_and_open(path=self._path, schema=schema)
            log.info("Created new vector store at %s", self._path)

    def _embed(self, text: str) -> list[float]:
        """Embed a single string using the sentence-transformer model (lazy-loaded)."""
        if self._model is None:
            log.info("Loading embedding model %s on %s...", self._model_name, self._device)
            self._model = _SentenceTransformer(self._model_name, device=self._device)
        return self._model.encode(text, normalize_embeddings=True).tolist()
