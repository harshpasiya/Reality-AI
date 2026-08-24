"""Local debug fine-tuning script — validates the LoRA pipeline end-to-end.

Proves the full training loop works on the RTX 3050 (4 GB VRAM) with
Phi-3-mini before spending Kaggle GPU hours on the real Mistral-7B run.

Usage:
    python -m ai.finetune.train_lora_debug               # fresh run
    python -m ai.finetune.train_lora_debug --resume       # resume from checkpoint

The script saves ONLY the LoRA adapter weights (not the full model) to
OUTPUT_DIR.  The adapter can later be loaded with:
    peft.AutoPeftModelForCausalLM.from_pretrained(OUTPUT_DIR)
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

import torch
import yaml
from datasets import Dataset, load_dataset
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments,
)
from trl import SFTTrainer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# =========================================================================
# Configuration constants — change these, not inline values
# =========================================================================

MODEL_NAME: str = "microsoft/Phi-3-mini-4k-instruct"
DATASET_PATH: str = "ai/finetune/data/debug_dataset.jsonl"
OUTPUT_DIR: str = "ai/finetune/adapters/debug-run/"
LORA_CONFIG_PATH: str = "ai/finetune/configs/lora_config.yaml"

NUM_EPOCHS: int = 3
LEARNING_RATE: float = 2e-4
PER_DEVICE_BATCH_SIZE: int = 1
GRADIENT_ACCUMULATION_STEPS: int = 8
MAX_SEQ_LENGTH: int = 1024


# =========================================================================
# Helpers
# =========================================================================


def _load_lora_config(config_path: str) -> LoraConfig:
    """Load LoRA hyperparameters from a YAML file and return a LoraConfig.

    Only the PEFT-relevant keys (r, lora_alpha, lora_dropout,
    target_modules, task_type) are extracted; the ``training`` sub-dict
    is ignored here (consumed directly by TrainingArguments).
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"LoRA config not found: {path.resolve()}")

    with open(path, encoding="utf-8") as f:
        cfg: dict[str, Any] = yaml.safe_load(f)

    return LoraConfig(
        r=cfg["r"],
        lora_alpha=cfg["lora_alpha"],
        lora_dropout=cfg["lora_dropout"],
        target_modules=cfg["target_modules"],
        task_type=cfg["task_type"],
        bias="none",
    )


def _detect_compute_dtype() -> torch.dtype:
    """Return bfloat16 if the GPU supports it, else float16.

    RTX 3050 (Ampere) supports bfloat16, but we check at runtime to be
    safe for other environments.
    """
    if torch.cuda.is_available() and torch.cuda.is_bf16_supported():
        logger.info("GPU supports bfloat16 -- using bf16 compute dtype.")
        return torch.bfloat16
    logger.info("bfloat16 not supported -- falling back to float16.")
    return torch.float16


def _find_latest_checkpoint(output_dir: str) -> str | None:
    """Return the path to the latest checkpoint-* directory, or None."""
    out = Path(output_dir)
    if not out.exists():
        return None
    checkpoints = sorted(
        [d for d in out.iterdir() if d.is_dir() and d.name.startswith("checkpoint-")],
        key=lambda d: int(d.name.split("-")[-1]),
    )
    if checkpoints:
        return str(checkpoints[-1])
    return None


def _format_time(seconds: float) -> str:
    """Format elapsed seconds as a human-readable string."""
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}h {m}m {s}s"
    return f"{m}m {s}s"


# =========================================================================
# Main training function
# =========================================================================


def train(resume: bool = False) -> None:
    """Run the local debug fine-tuning loop."""

    # ── 0. Pre-flight checks ─────────────────────────────────────────────
    if not torch.cuda.is_available():
        logger.error(
            "CUDA is not available.  This script requires a GPU.\n"
            "  - Check that PyTorch was installed with CUDA support\n"
            "    (pip install torch --index-url https://download.pytorch.org/whl/cu121)\n"
            "  - Run `nvidia-smi` to verify your driver is working."
        )
        sys.exit(1)

    dataset_file = Path(DATASET_PATH)
    if not dataset_file.exists():
        logger.error(
            "Dataset not found at %s.\n"
            "  Generate it first:\n"
            "    python -m ai.finetune.prepare_dataset --mode debug",
            dataset_file.resolve(),
        )
        sys.exit(1)

    gpu_name = torch.cuda.get_device_name(0)
    vram_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3
    logger.info("GPU: %s (%.1f GB VRAM)", gpu_name, vram_gb)

    # ── 1. Load LoRA config from YAML ────────────────────────────────────
    lora_config = _load_lora_config(LORA_CONFIG_PATH)
    logger.info(
        "LoRA config: r=%d, alpha=%d, dropout=%.2f, targets=%s",
        lora_config.r, lora_config.lora_alpha,
        lora_config.lora_dropout, lora_config.target_modules,
    )

    # ── 2. Load tokenizer ────────────────────────────────────────────────
    logger.info("Loading tokenizer: %s", MODEL_NAME)
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
        tokenizer.pad_token_id = tokenizer.eos_token_id
    tokenizer.padding_side = "right"

    # ── 3. Load dataset and apply chat template ──────────────────────────
    logger.info("Loading dataset: %s", DATASET_PATH)
    dataset = load_dataset("json", data_files=DATASET_PATH, split="train")
    logger.info("Dataset size: %d examples", len(dataset))

    def _apply_chat_template(example: dict) -> dict:
        """Format the messages list using the tokenizer's chat template."""
        text = tokenizer.apply_chat_template(
            example["messages"],
            tokenize=False,
            add_generation_prompt=False,
        )
        return {"text": text}

    dataset = dataset.map(_apply_chat_template, remove_columns=dataset.column_names)
    logger.info("Chat template applied.  Sample (first 200 chars):\n  %s", dataset[0]["text"][:200])

    # ── 4. Load base model in 4-bit ──────────────────────────────────────
    compute_dtype = _detect_compute_dtype()
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=compute_dtype,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
    )

    logger.info("Loading model: %s (4-bit quantized)", MODEL_NAME)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
        attn_implementation="eager",  # Flash Attention not available on all GPUs
    )
    model.config.use_cache = False  # incompatible with gradient checkpointing

    # ── 5. Prepare for k-bit training and apply LoRA ─────────────────────
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    model = get_peft_model(model, lora_config)

    trainable, total = model.get_nb_trainable_parameters()
    pct = 100.0 * trainable / total if total > 0 else 0
    logger.info(
        "Trainable parameters: %s / %s (%.2f%%)",
        f"{trainable:,}", f"{total:,}", pct,
    )

    # ── 6. Training arguments ────────────────────────────────────────────
    use_bf16 = (compute_dtype == torch.bfloat16)
    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        num_train_epochs=NUM_EPOCHS,
        per_device_train_batch_size=PER_DEVICE_BATCH_SIZE,
        gradient_accumulation_steps=GRADIENT_ACCUMULATION_STEPS,
        learning_rate=LEARNING_RATE,
        warmup_ratio=0.05,
        logging_steps=5,
        save_strategy="epoch",
        gradient_checkpointing=True,
        optim="paged_adamw_8bit",
        fp16=not use_bf16,
        bf16=use_bf16,
        max_grad_norm=0.3,
        report_to="none",           # no wandb/tensorboard for debug
        dataloader_pin_memory=False,  # saves a bit of VRAM
    )

    # ── 7. Check for resume checkpoint ───────────────────────────────────
    resume_from = None
    if resume:
        resume_from = _find_latest_checkpoint(OUTPUT_DIR)
        if resume_from:
            logger.info("Resuming from checkpoint: %s", resume_from)
        else:
            logger.warning("--resume passed but no checkpoint found. Starting fresh.")

    # ── 8. Create trainer ────────────────────────────────────────────────
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        args=training_args,
        max_seq_length=MAX_SEQ_LENGTH,
        dataset_text_field="text",
        packing=False,
    )

    # ── 9. Train ─────────────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("Starting training (%d epochs, effective batch=%d)",
                NUM_EPOCHS, PER_DEVICE_BATCH_SIZE * GRADIENT_ACCUMULATION_STEPS)
    logger.info("=" * 60)

    t0 = time.time()

    try:
        result = trainer.train(resume_from_checkpoint=resume_from)
    except torch.cuda.OutOfMemoryError:
        logger.error(
            "\n"
            "  !! CUDA Out of Memory !!\n"
            "\n"
            "  The model + optimizer + activations don't fit in %.1f GB VRAM.\n"
            "  Try one or more of these fixes:\n"
            "\n"
            "  1. Reduce PER_DEVICE_BATCH_SIZE (currently %d)\n"
            "  2. Increase GRADIENT_ACCUMULATION_STEPS to compensate\n"
            "  3. Reduce MAX_SEQ_LENGTH (currently %d)\n"
            "  4. Close other GPU-using applications (browsers, etc.)\n"
            "\n"
            "  Current settings: batch=%d x grad_accum=%d = effective %d\n",
            vram_gb,
            PER_DEVICE_BATCH_SIZE,
            MAX_SEQ_LENGTH,
            PER_DEVICE_BATCH_SIZE,
            GRADIENT_ACCUMULATION_STEPS,
            PER_DEVICE_BATCH_SIZE * GRADIENT_ACCUMULATION_STEPS,
        )
        sys.exit(1)

    elapsed = time.time() - t0

    # ── 10. Save adapter and report ──────────────────────────────────────
    logger.info("Saving adapter weights to %s", OUTPUT_DIR)
    model.save_pretrained(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)

    final_loss = result.training_loss
    logger.info("=" * 60)
    logger.info("  Training complete!")
    logger.info("  Final loss:    %.4f", final_loss)
    logger.info("  Total time:    %s", _format_time(elapsed))
    logger.info("  Adapter saved: %s", Path(OUTPUT_DIR).resolve())
    logger.info("  Trainable:     %s params (%.2f%%)", f"{trainable:,}", pct)
    logger.info("=" * 60)


# =========================================================================
# CLI
# =========================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Debug LoRA fine-tuning on Phi-3-mini (local GPU).",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume training from the latest checkpoint in OUTPUT_DIR.",
    )
    args = parser.parse_args()
    train(resume=args.resume)
