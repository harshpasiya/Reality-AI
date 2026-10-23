"""Model loader — lazy singleton for the base LLM + LoRA adapter.

Loads Mistral-7B-v0.1 in 4-bit quantisation with the fine-tuned LoRA
adapter attached.  The (model, tokenizer) pair is cached at module level
so only the first ``get_model()`` call pays the ~30-second load cost.

Usage:
    from ai.inference.load_model import get_model

    model, tokenizer = get_model()   # first call loads; subsequent calls instant

    # After retraining the adapter:
    from ai.inference.load_model import reload_model
    reload_model()                    # clears cache; next get_model() reloads
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

if TYPE_CHECKING:
    from peft import PeftModel
    from transformers import PreTrainedModel, PreTrainedTokenizer


logger = logging.getLogger(__name__)


# =========================================================================
# Constants
# =========================================================================

BASE_MODEL: str = "mistralai/Mistral-7B-v0.1"

# Path is relative to the project root (where you run `python -m ...`).
ADAPTER_DIR: Path = Path("ai/finetune/adapters/reality-ai-lora")


# =========================================================================
# Custom exception
# =========================================================================


class AdapterNotFoundError(FileNotFoundError):
    """Raised when the LoRA adapter directory is missing.

    This usually means fine-tuning hasn't been run yet, or the adapter
    zip hasn't been unzipped into the expected location.
    """


# =========================================================================
# Module-level singleton
# =========================================================================

_cached: tuple["PreTrainedModel", "PreTrainedTokenizer"] | None = None


# =========================================================================
# Private helpers
# =========================================================================


def _detect_compute_dtype() -> torch.dtype:
    """Return bfloat16 if the GPU supports it, else float16."""
    if torch.cuda.is_available() and torch.cuda.is_bf16_supported():
        return torch.bfloat16
    return torch.float16


def _load() -> tuple["PreTrainedModel", "PreTrainedTokenizer"]:
    """Load the base model in 4-bit, attach the LoRA adapter, and return.

    This is intentionally a plain function (not cached itself); caching
    is handled by the module-level ``_cached`` variable so that
    ``reload_model()`` can clear it.
    """
    import peft  # deferred so the module can be imported even without peft installed

    # ── Validate adapter path ────────────────────────────────────────────
    adapter_path = ADAPTER_DIR.resolve()
    if not adapter_path.exists():
        raise AdapterNotFoundError(
            f"LoRA adapter directory not found: {adapter_path}\n"
            "\n"
            "This means fine-tuning has not been run yet, or the adapter\n"
            "files haven't been placed in the expected location.\n"
            "\n"
            "To fix this:\n"
            "  1. Run the Kaggle notebook (train_lora_kaggle.ipynb) to\n"
            "     train the adapter.\n"
            "  2. Download the adapter zip from the Kaggle Output tab.\n"
            "  3. Unzip into:  ai/finetune/adapters/reality-ai-lora/\n"
        )

    t0 = time.time()

    # ── Tokenizer ────────────────────────────────────────────────────────
    logger.info("Loading tokenizer: %s", BASE_MODEL)
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
        tokenizer.pad_token_id = tokenizer.eos_token_id
    tokenizer.padding_side = "right"

    # Set ChatML template — Mistral base model doesn't have one built in.
    # Matches the exact ChatML format used during LoRA fine-tuning.
    if not tokenizer.chat_template:
        tokenizer.chat_template = (
            "{% for message in messages %}"
            "{{'<|im_start|>' + message['role'] + '\n' + message['content'] + '<|im_end|>' + '\n'}}"
            "{% endfor %}"
            "{% if add_generation_prompt %}"
            "{{'<|im_start|>assistant\n'}}"
            "{% endif %}"
        )

    # ── Base model in 4-bit ──────────────────────────────────────────────
    compute_dtype = _detect_compute_dtype()

    # Map directly onto GPU 0 if CUDA is available.
    # BitsAndBytes 4-bit with double quantization fits in ~4 GB VRAM when loaded
    # directly onto the GPU, avoiding CPU offloading issues and meta-tensor bugs.
    if torch.cuda.is_available():
        device_map = {"": 0}
        logger.info("CUDA GPU detected — loading 4-bit model directly onto GPU 0.")
    else:
        device_map = "auto"
        logger.info("No CUDA GPU detected — falling back to device_map='auto'.")

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=compute_dtype,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
    )

    logger.info(
        "Loading base model: %s (4-bit, compute_dtype=%s)",
        BASE_MODEL,
        compute_dtype,
    )

    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        quantization_config=bnb_config,
        device_map=device_map,
        trust_remote_code=True,
    )

    # ── Attach LoRA adapter ──────────────────────────────────────────────
    logger.info("Attaching LoRA adapter from: %s", adapter_path)
    model = peft.PeftModel.from_pretrained(model, str(adapter_path))

    # ── Inference mode ───────────────────────────────────────────────────
    model.eval()

    elapsed = time.time() - t0
    logger.info(
        "Model loaded and ready for inference (%.1fs). "
        "Device map: %s",
        elapsed,
        getattr(model, "hf_device_map", "n/a"),
    )

    return model, tokenizer


# =========================================================================
# Public API
# =========================================================================


def get_model() -> tuple["PreTrainedModel", "PreTrainedTokenizer"]:
    """Return the (model, tokenizer) singleton.

    On the first call the model is loaded from disk (slow — ~30 s on a
    consumer GPU).  Subsequent calls return the cached reference
    instantly.
    """
    global _cached

    if _cached is not None:
        logger.debug("Returning cached model (no reload).")
        return _cached

    _cached = _load()
    return _cached


def reload_model() -> None:
    """Clear the cached singleton so the next ``get_model()`` reloads.

    Useful during development when you retrain the adapter and want to
    pick up the new weights without restarting the Python process.

    Any references other code holds to the *old* model/tokenizer will
    become stale — callers should re-call ``get_model()`` after this.
    """
    global _cached

    if _cached is not None:
        logger.info("Clearing cached model — next get_model() will reload.")
        # Help the GC reclaim GPU memory
        model, _ = _cached
        del model
        torch.cuda.empty_cache()

    _cached = None
