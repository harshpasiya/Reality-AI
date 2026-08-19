"""Pytest tests for ai.embeddings.embedding_model.

Run from the repo root:
    pytest ai/embeddings/_test_embedding_model.py -v

These tests use the real model (all-MiniLM-L6-v2) so they require network
access on first run (model is cached locally by sentence-transformers after
that).  They do NOT require a GPU — CPU inference is fast enough for a 384-dim
model on small inputs.
"""

from __future__ import annotations

import math
import pytest

from ai.embeddings.embedding_model import (
    EMBEDDING_DIM,
    EmbeddingModel,
    EmbeddingModelLoadError,
)


# ---------------------------------------------------------------------------
# Shared fixture — load the model once per test session for speed
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def model() -> EmbeddingModel:
    """A single EmbeddingModel instance shared across the entire test session."""
    return EmbeddingModel()  # uses default all-MiniLM-L6-v2


# ---------------------------------------------------------------------------
# 1. Embedding dimension matches EMBEDDING_DIM constant
# ---------------------------------------------------------------------------


def test_embedding_dim_matches_constant(model: EmbeddingModel) -> None:
    """The model's reported dimension must equal the module constant.

    Person 2 imports EMBEDDING_DIM to define the pgvector column.  If the
    constant drifts from the real model output, every INSERT would fail.
    """
    assert model.embedding_dim == EMBEDDING_DIM, (
        f"model.embedding_dim={model.embedding_dim} does not match "
        f"EMBEDDING_DIM={EMBEDDING_DIM}. Update the constant."
    )


# ---------------------------------------------------------------------------
# 2. embed() returns a vector of the expected length
# ---------------------------------------------------------------------------


def test_embed_returns_correct_length(model: EmbeddingModel) -> None:
    """embed() output length must equal EMBEDDING_DIM."""
    vector = model.embed("3BHK flat near Bopal, Ahmedabad")
    assert len(vector) == EMBEDDING_DIM


# ---------------------------------------------------------------------------
# 3. embed() returns plain Python floats, not numpy scalars
# ---------------------------------------------------------------------------


def test_embed_returns_list_of_python_floats(model: EmbeddingModel) -> None:
    """Each element of the returned vector must be a plain Python float.

    SQLAlchemy / psycopg2 do not accept numpy scalars directly.
    """
    vector = model.embed("test property listing")
    assert isinstance(vector, list), "embed() must return a list"
    assert all(isinstance(v, float) for v in vector), (
        "All elements must be plain Python floats, not numpy scalars"
    )


# ---------------------------------------------------------------------------
# 4. embed() and embed_batch() produce identical vectors for the same text
# ---------------------------------------------------------------------------


def test_embed_and_embed_batch_consistency(model: EmbeddingModel) -> None:
    """Single-item embed() and embed_batch() must return the same vector.

    If they diverge it means one code path is missing normalisation or uses a
    different encode configuration, which would corrupt cosine-similarity
    results in pgvector.
    """
    text = "Spacious 2BHK apartment with parking, near Satellite, Ahmedabad"
    single = model.embed(text)
    batch = model.embed_batch([text])[0]

    assert len(single) == len(batch), "Vector lengths differ between embed and embed_batch"

    for i, (a, b) in enumerate(zip(single, batch)):
        assert math.isclose(a, b, rel_tol=1e-5), (
            f"Dimension {i} differs: embed={a}, embed_batch={b}"
        )


# ---------------------------------------------------------------------------
# 5. embed() raises ValueError on empty string
# ---------------------------------------------------------------------------


def test_embed_raises_on_empty_string(model: EmbeddingModel) -> None:
    """embed('') must raise ValueError, not silently produce a zero vector."""
    with pytest.raises(ValueError, match="non-empty string"):
        model.embed("")


# ---------------------------------------------------------------------------
# 6. embed() raises ValueError on whitespace-only string
# ---------------------------------------------------------------------------


def test_embed_raises_on_whitespace_only(model: EmbeddingModel) -> None:
    """embed('   ') must raise ValueError — whitespace strips to empty."""
    with pytest.raises(ValueError, match="non-empty string"):
        model.embed("   ")


# ---------------------------------------------------------------------------
# 7. embed_batch() returns empty list for empty input — no model call
# ---------------------------------------------------------------------------


def test_embed_batch_empty_input_returns_empty_list(model: EmbeddingModel) -> None:
    """embed_batch([]) must return [] immediately without calling the model."""
    result = model.embed_batch([])
    assert result == [], f"Expected [], got {result!r}"


# ---------------------------------------------------------------------------
# 8. embed_batch() raises ValueError on empty string element
# ---------------------------------------------------------------------------


def test_embed_batch_raises_on_empty_element(model: EmbeddingModel) -> None:
    """embed_batch() must raise ValueError if any element is empty/whitespace."""
    with pytest.raises(ValueError, match="index 1"):
        model.embed_batch(["valid listing text", "   ", "another valid text"])


# ---------------------------------------------------------------------------
# 9. Very long string doesn't crash — tokenizer truncates silently
# ---------------------------------------------------------------------------


def test_embed_very_long_string_does_not_crash(model: EmbeddingModel) -> None:
    """A 2000-word input must not raise — the tokenizer truncates to its max.

    sentence-transformers truncates at the model's max_seq_length (typically
    256 or 512 tokens) rather than erroring.  We verify this behaviour holds
    and that a vector of the correct dimension is returned.
    """
    long_text = "spacious flat near school " * 2000  # ~10 000 words
    vector = model.embed(long_text)
    assert len(vector) == EMBEDDING_DIM, (
        f"Long-string embed returned wrong dimension: {len(vector)}"
    )
    assert all(isinstance(v, float) for v in vector)


# ---------------------------------------------------------------------------
# 10. embed_batch() output length matches input length
# ---------------------------------------------------------------------------


def test_embed_batch_output_length_matches_input(model: EmbeddingModel) -> None:
    """embed_batch() must return exactly one vector per input text."""
    texts = [
        "1BHK near BRTS, Ahmedabad",
        "Villa with garden in Shilaj",
        "Commercial plot in Sanand GIDC",
    ]
    result = model.embed_batch(texts)
    assert len(result) == len(texts), (
        f"Expected {len(texts)} vectors, got {len(result)}"
    )
    for i, vec in enumerate(result):
        assert len(vec) == EMBEDDING_DIM, (
            f"Vector {i} has wrong dimension: {len(vec)}"
        )


# ---------------------------------------------------------------------------
# 11. Loading a non-existent model raises EmbeddingModelLoadError
# ---------------------------------------------------------------------------


def test_load_invalid_model_raises_custom_exception() -> None:
    """EmbeddingModelLoadError must be raised (not a raw HF exception) on bad model name."""
    with pytest.raises(EmbeddingModelLoadError):
        EmbeddingModel(model_name="this-model-does-not-exist-reality-ai-test")
