"""Sentence-transformers wrapper providing a single consistent embedding interface for the AI/RAG track.

All modules that need to embed text (embed_listings, retriever, etc.) should import
EmbeddingModel from here rather than calling sentence_transformers directly.  This
keeps the model loaded once, the normalisation strategy consistent, and the return
type predictable (plain Python list[float]) for downstream database code.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

import torch
from sentence_transformers import SentenceTransformer

# Suppress the Windows symlink warning from huggingface_hub — caching still
# works correctly on Windows without symlinks, just with slightly more disk use.
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

if TYPE_CHECKING:
    pass  # reserved for future type-only imports

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class EmbeddingModelLoadError(Exception):
    """Raised when the underlying SentenceTransformer model fails to load.

    The original exception is always chained via ``raise ... from e`` so the
    full cause is available for debugging without any information being lost.
    """


# ---------------------------------------------------------------------------
# Embedding model
# ---------------------------------------------------------------------------


class EmbeddingModel:
    """A thin, consistent wrapper around a sentence-transformers model.

    Loads the model once at construction time and exposes two public methods
    (``embed`` and ``embed_batch``) that always return plain Python
    ``list[float]`` values with L2-normalised vectors — making cosine
    similarity correct by default in pgvector (``<=>`` operator).

    The resolved embedding dimension is logged at INFO level on load so that
    Person 2 can confirm the pgvector column size without reading source code.

    Attributes:
        model_name: The sentence-transformers model identifier used to load.
        device: The resolved torch device string (``"cuda"`` or ``"cpu"``).
        embedding_dim: The vector dimension produced by this model instance.

    Example::

        model = EmbeddingModel()
        vector = model.embed("3BHK flat near Bopal, Ahmedabad")
        vectors = model.embed_batch(["flat in Bopal", "house in Thaltej"])
    """

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        device: str | None = None,
    ) -> None:
        """Initialise and load the embedding model.

        Args:
            model_name: A sentence-transformers model name or local path.
                Defaults to ``"all-MiniLM-L6-v2"`` (384-dimensional, fast,
                broadly accurate for semantic similarity tasks).
            device: Torch device to run inference on.  Pass ``None`` (default)
                to auto-detect: ``"cuda"`` if a CUDA-capable GPU is available,
                otherwise ``"cpu"``.

        Raises:
            EmbeddingModelLoadError: If the model cannot be downloaded or
                initialised.  The original exception is chained.
        """
        resolved_device: str = device or ("cuda" if torch.cuda.is_available() else "cpu")

        try:
            self._model: SentenceTransformer = SentenceTransformer(
                model_name, device=resolved_device
            )
        except Exception as e:
            raise EmbeddingModelLoadError(
                f"Failed to load embedding model '{model_name}' on device '{resolved_device}'. "
                f"Ensure the model name is correct and you have network access (or a local cache). "
                f"Original error: {e}"
            ) from e

        self.model_name: str = model_name
        self.device: str = resolved_device
        # get_embedding_dimension() is the current API name;
        # get_sentence_embedding_dimension() was renamed and emits a FutureWarning.
        self.embedding_dim: int = self._model.get_embedding_dimension()

        logger.info(
            "Loaded embedding model '%s', dimension=%d, device=%s",
            self.model_name,
            self.embedding_dim,
            self.device,
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def embed(self, text: str) -> list[float]:
        """Embed a single piece of text into a normalised float vector.

        The vector is L2-normalised (``normalize_embeddings=True``) so that
        cosine similarity is equivalent to a dot product — required for
        pgvector's ``<=>`` cosine-distance operator to work correctly.

        Args:
            text: The text to embed.  Must be a non-empty string after
                stripping leading/trailing whitespace.

        Returns:
            A ``list[float]`` of length ``self.embedding_dim``.  A plain
            Python list is returned (not a numpy array) so it can be passed
            directly to SQLAlchemy / psycopg2 without conversion.

        Raises:
            ValueError: If ``text`` is empty or contains only whitespace.
        """
        if not isinstance(text, str) or not text.strip():
            raise ValueError(
                "embed() requires a non-empty string. "
                f"Received: {text!r}"
            )

        vector = self._model.encode(
            text,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        return vector.tolist()

    def embed_batch(
        self,
        texts: list[str],
        batch_size: int = 32,
    ) -> list[list[float]]:
        """Embed a list of texts in batches, preserving input order.

        **Caller responsibility:** every string in ``texts`` must be a
        non-empty string after stripping whitespace.  If any element is empty
        or whitespace-only, a ``ValueError`` is raised immediately (before any
        GPU work is done).  This is intentionally strict — silent filtering
        would cause the returned list to have a different length than the
        input, breaking index alignment in ``embed_listings``.

        An empty input list is handled as a special case: the model is never
        called and an empty list is returned immediately.

        Args:
            texts: A list of strings to embed.  Each must be non-empty after
                stripping whitespace.
            batch_size: Number of texts to encode per forward pass.  Defaults
                to 32.  Increase for throughput on GPU; decrease if you hit
                OOM errors on large inputs.

        Returns:
            A ``list[list[float]]`` of length ``len(texts)``, where each
            inner list has length ``self.embedding_dim``.  Order is preserved.

        Raises:
            ValueError: If any element of ``texts`` is empty or
                whitespace-only.  The error message includes the index of the
                offending element so the caller can fix the data.
        """
        if not texts:
            return []

        for idx, text in enumerate(texts):
            if not isinstance(text, str) or not text.strip():
                raise ValueError(
                    f"embed_batch() requires all elements to be non-empty strings. "
                    f"Element at index {idx} is invalid: {text!r}. "
                    f"Filter or clean your input before calling this method."
                )

        show_progress = len(texts) > 100
        vectors = self._model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=show_progress,
            convert_to_numpy=True,
        )
        return [v.tolist() for v in vectors]


# ---------------------------------------------------------------------------
# Module-level convenience constant
# ---------------------------------------------------------------------------
# Instantiating a full model here would be expensive and would fail in
# environments without network access.  Instead, EMBEDDING_DIM is set to the
# well-known dimension for the default model so Person 2 can import it as a
# constant for the pgvector column definition without triggering a model load.
# If a non-default model is used, read EmbeddingModel(...).embedding_dim at
# runtime instead of relying on this constant.

EMBEDDING_DIM: int = 384  # all-MiniLM-L6-v2 output dimension
"""The vector dimension produced by the default embedding model (all-MiniLM-L6-v2).

Person 2 should use this value for the pgvector column:

    from pgvector.sqlalchemy import Vector
    from ai.embeddings.embedding_model import EMBEDDING_DIM

    embedding = Column(Vector(EMBEDDING_DIM))

If the embedding model is changed, update this constant *and* run an Alembic
migration to update the column dimension before re-embedding listings.
"""
