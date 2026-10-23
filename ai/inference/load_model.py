"""Model loader — lazy, thread-safe singleton for the Qwen3 NLU model + LoRA adapter.

The model only does query understanding (sentence -> JSON filters, see
ai/nlu/query_parser.py); it never writes chat replies. It is optional at
runtime: when there is no CUDA GPU or no adapter, ``is_model_available()``
returns False / ``get_model()`` raises ``ModelUnavailableError``, and the
caller falls back to the rules parser. A missing GPU must never take down
the backend.

Usage:
    from ai.inference.load_model import get_model, is_model_available

    if is_model_available():
        model, tokenizer = get_model()   # first call loads (~10-30 s); later calls are free
"""

from __future__ import annotations

import importlib.util
import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from transformers import PreTrainedModel, PreTrainedTokenizerBase

logger = logging.getLogger(__name__)


# =========================================================================
# Constants
# =========================================================================

BASE_MODEL: str = "Qwen/Qwen3-4B-Instruct-2507"

# Resolved relative to this file, not the working directory, so it works no
# matter where the backend process is started from.
ADAPTER_DIR: Path = Path(__file__).resolve().parents[1] / "finetune" / "adapters" / "qwen3-nlu-lora"

# Set to "1" to allow loading on CPU. Off by default: the 4B model on CPU needs
# ~8 GB+ RAM and takes seconds per query, which is too slow for chat.
ALLOW_CPU_ENV: str = "NLU_ALLOW_CPU_MODEL"


# =========================================================================
# Custom exception
# =========================================================================


class ModelUnavailableError(RuntimeError):
    """The NLU model can't be used here (no GPU, no adapter, or load failed).

    Callers should catch this and fall back to rules-based parsing.
    """


# =========================================================================
# Module-level singleton
# =========================================================================

_cached: tuple["PreTrainedModel", "PreTrainedTokenizerBase"] | None = None
_lock = threading.Lock()


def _cpu_allowed() -> bool:
    return os.getenv(ALLOW_CPU_ENV, "").strip() == "1"


def _unavailable_reason(adapter_dir: Path) -> str | None:
    """Why the model can't be loaded, or None if it can. Loads no weights."""
    for pkg in ("torch", "transformers", "peft"):
        if importlib.util.find_spec(pkg) is None:
            return f"Python package '{pkg}' is not installed."
    if not (adapter_dir / "adapter_config.json").is_file():
        return (
            f"LoRA adapter not found at {adapter_dir}. "
            "Run ai/finetune/train_lora_qwen3_kaggle.ipynb on Kaggle, download "
            "qwen3-nlu-lora.zip from the Output tab and unzip it there "
            "(adapter_config.json must sit directly in that folder)."
        )
    import torch  # already loaded by the embedding model in practice, so cheap

    if not torch.cuda.is_available() and not _cpu_allowed():
        return (
            "No CUDA GPU available, so the NLU model is skipped and rules-based "
            f"parsing is used. Set {ALLOW_CPU_ENV}=1 to force a (slow) CPU load."
        )
    return None


def _adapter_base_model(adapter_dir: Path) -> str | None:
    try:
        config = json.loads((adapter_dir / "adapter_config.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return config.get("base_model_name_or_path")


def _dtype_kwarg(dtype: Any) -> dict[str, Any]:
    """transformers >= 4.56 renamed from_pretrained(torch_dtype=) to dtype=."""
    import transformers

    major, minor = (int(x) for x in transformers.__version__.split(".")[:2])
    return {"dtype": dtype} if (major, minor) >= (4, 56) else {"torch_dtype": dtype}


def _load(adapter_dir: Path) -> tuple["PreTrainedModel", "PreTrainedTokenizerBase"]:
    """Load the base model (4-bit on GPU), attach the adapter, return (model, tokenizer)."""
    reason = _unavailable_reason(adapter_dir)
    if reason:
        raise ModelUnavailableError(reason)

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    base = _adapter_base_model(adapter_dir)
    if base is None:
        base = BASE_MODEL
    elif base != BASE_MODEL:
        # An adapter only works on the base it was trained on — refuse rather
        # than silently produce garbage (e.g. a 1.7B debug adapter on the 4B).
        raise ModelUnavailableError(
            f"Adapter at {adapter_dir} was trained on {base}, but BASE_MODEL is {BASE_MODEL}."
        )

    t0 = time.time()
    # The adapter folder carries the tokenizer saved at training time, so the
    # chat template is byte-identical to the one the model was trained with.
    tokenizer = AutoTokenizer.from_pretrained(str(adapter_dir))
    tokenizer.padding_side = "right"
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    if torch.cuda.is_available():
        compute_dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
        model = AutoModelForCausalLM.from_pretrained(
            base,
            quantization_config=BitsAndBytesConfig(
                load_in_4bit=True, bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=compute_dtype),
            device_map={"": 0},
            **_dtype_kwarg(compute_dtype),
        )
    else:
        logger.warning("Loading %s on CPU (%s=1) — expect several seconds per query.",
                       base, ALLOW_CPU_ENV)
        model = AutoModelForCausalLM.from_pretrained(base, **_dtype_kwarg(torch.float32))

    model = PeftModel.from_pretrained(model, str(adapter_dir))
    model.eval()

    gpu_gb = torch.cuda.memory_allocated() / 1024**3 if torch.cuda.is_available() else 0.0
    logger.info("NLU model %s + adapter loaded in %.1fs (GPU memory %.2f GB).",
                base, time.time() - t0, gpu_gb)
    return model, tokenizer


# =========================================================================
# Public API
# =========================================================================


def is_model_available() -> bool:
    """True if get_model() can be expected to work. Loads no weights."""
    if _cached is not None:
        return True
    return _unavailable_reason(ADAPTER_DIR) is None


def get_model() -> tuple["PreTrainedModel", "PreTrainedTokenizerBase"]:
    """Return the (model, tokenizer) singleton, loading it on first call.

    Thread-safe: concurrent first calls from the backend's worker threads load
    the model once.

    Raises:
        ModelUnavailableError: No GPU (and CPU not allowed), no adapter, a
            base/adapter mismatch, or the load itself failed (download, out of
            memory, library version problems).
    """
    global _cached
    if _cached is not None:
        logger.debug("Returning cached NLU model.")
        return _cached
    with _lock:
        if _cached is None:
            try:
                _cached = _load(ADAPTER_DIR)
            except ModelUnavailableError:
                raise
            except Exception as exc:
                raise ModelUnavailableError(f"Loading the NLU model failed: {exc}") from exc
    return _cached


def reload_model() -> None:
    """Clear the singleton so the next get_model() reloads (e.g. after retraining).

    Any references other code holds to the old model become stale.
    """
    global _cached
    with _lock:
        if _cached is None:
            return
        logger.info("Clearing cached NLU model — next get_model() will reload.")
        _cached = None
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass
