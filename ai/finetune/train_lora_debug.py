"""Local debug LoRA run for the Qwen3 NLU adapter (RTX 3050, 4 GB VRAM).

Goal: prove the whole pipeline works — data -> chat template -> 4-bit model
-> LoRA -> training -> adapter save -> JSON generation — on the local GPU
before spending Kaggle hours on the real Qwen3-4B run. The adapter produced
here is a smoke-test artefact, not the one that ships.

Usage (from repo root):
    python -m ai.finetune.prepare_extraction_dataset      # writes the data first
    python -m ai.finetune.train_lora_debug --dry-run      # tokenizer only: lengths + masking check
    python -m ai.finetune.train_lora_debug                # full debug run

Design notes:
  - Loss is computed on the assistant's JSON only. Every example starts with
    the same ~150-token system prompt; training on it would mostly teach the
    model to memorise that prompt. Examples are tokenized here with prompt
    tokens masked to -100, and TRL's own dataset preparation is skipped
    (dataset_kwargs={"skip_prepare_dataset": True}) — which also sidesteps
    most of TRL's argument churn between versions.
  - The model's own chat template is used unchanged (never overridden), with
    enable_thinking=False when the template supports it, so training text is
    byte-identical to what ai/nlu/query_parser.py will send at inference.
"""

from __future__ import annotations

import argparse
import dataclasses
import os
import inspect
import json
import math
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch
import yaml

# Caching works on Windows without symlinks; the warning is noise.
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

REPO_ROOT = Path(__file__).resolve().parents[2]
FINETUNE_DIR = Path(__file__).resolve().parent

# =========================================================================
# Configuration
# =========================================================================

MODEL_NAME: str = "Qwen/Qwen3-1.7B"
DATA: Path = FINETUNE_DIR / "data" / "debug_train.jsonl"
VAL_DATA: Path = FINETUNE_DIR / "data" / "val.jsonl"
OUTPUT_DIR: Path = FINETUNE_DIR / "adapters" / "debug-qwen3"
SCRATCH_DIR: Path = FINETUNE_DIR / "adapters" / "_scratch-debug"
LORA_CONFIG_PATH: Path = FINETUNE_DIR / "configs" / "lora_config_local.yaml"

EPOCHS: int = 2
LR: float = 2e-4
BATCH: int = 1
GRAD_ACCUM: int = 8           # effective batch size 8
LOG_EVERY: int = 5
SANITY_QUERIES: int = 5
MAX_NEW_TOKENS: int = 160     # the JSON is ~60-90 tokens; 160 leaves headroom
MAX_ADAPTER_MB: int = 500


# =========================================================================
# Helpers shared with the Kaggle notebook (inlined there — keep in sync)
# =========================================================================


def print_versions() -> None:
    import importlib
    for name in ("torch", "transformers", "peft", "trl", "bitsandbytes", "accelerate", "datasets"):
        try:
            print(f"  {name:<13} {importlib.import_module(name).__version__}")
        except Exception as exc:  # noqa: BLE001 - report, don't crash
            print(f"  {name:<13} NOT AVAILABLE ({exc})")


def template_kwargs(tokenizer) -> dict[str, Any]:
    """enable_thinking=False for templates that support it (Qwen3 hybrid models)."""
    return {"enable_thinking": False} if "enable_thinking" in (tokenizer.chat_template or "") else {}


def dtype_kwarg(dtype: torch.dtype) -> dict[str, Any]:
    """transformers >= 4.56 renamed from_pretrained(torch_dtype=) to dtype=."""
    import transformers
    major, minor = (int(x) for x in transformers.__version__.split(".")[:2])
    return {"dtype": dtype} if (major, minor) >= (4, 56) else {"torch_dtype": dtype}


def tokenize_example(example: dict, tokenizer, kwargs: dict[str, Any]) -> dict[str, list[int]]:
    """input_ids / attention_mask / labels with the prompt masked to -100."""
    messages = example["messages"]
    prompt = tokenizer.apply_chat_template(
        messages[:-1], tokenize=False, add_generation_prompt=True, **kwargs)
    full = tokenizer.apply_chat_template(messages, tokenize=False, **kwargs)
    if not full.startswith(prompt):
        raise ValueError(
            "Chat template renders the prompt differently with and without the "
            "assistant turn, so the loss mask can't be placed.\n"
            f"PROMPT: {prompt!r}\nFULL:   {full!r}")
    prompt_ids = tokenizer(prompt, add_special_tokens=False)["input_ids"]
    full_ids = tokenizer(full, add_special_tokens=False)["input_ids"]
    if full_ids[:len(prompt_ids)] != prompt_ids:
        raise ValueError("Tokenization of the prompt changes when the answer is appended.")
    labels = [-100] * len(prompt_ids) + full_ids[len(prompt_ids):]
    return {"input_ids": full_ids, "attention_mask": [1] * len(full_ids), "labels": labels}


def measure_max_len(lengths: list[int]) -> int:
    """95th percentile, rounded up to a multiple of 64, clamped to 256-512."""
    p95 = float(np.percentile(lengths, 95))
    return int(min(512, max(256, math.ceil(p95 / 64) * 64)))


def build_trainer(model, tokenizer, train_ds, output_dir: str, max_len: int, *,
                  epochs: float, lr: float, batch: int, grad_accum: int, bf16: bool,
                  max_steps: int = -1, callbacks: list | None = None):
    """SFTTrainer built by inspecting the installed TRL's signatures.

    Newer TRL renamed max_seq_length -> max_length and tokenizer ->
    processing_class; only arguments that exist in this version are passed.
    """
    from transformers import DataCollatorForSeq2Seq
    from trl import SFTConfig, SFTTrainer

    wanted: dict[str, Any] = {
        "output_dir": output_dir,
        "num_train_epochs": epochs,
        "max_steps": max_steps,
        "learning_rate": lr,
        "per_device_train_batch_size": batch,
        "gradient_accumulation_steps": grad_accum,
        "lr_scheduler_type": "cosine",
        "warmup_ratio": 0.05,
        "logging_steps": LOG_EVERY,
        "save_strategy": "no",
        "report_to": "none",
        "optim": "paged_adamw_8bit",
        "gradient_checkpointing": True,
        "gradient_checkpointing_kwargs": {"use_reentrant": False},
        "fp16": not bf16,
        "bf16": bf16,
        "dataset_kwargs": {"skip_prepare_dataset": True},
        "remove_unused_columns": False,
        "max_length": max_len,
        "max_seq_length": max_len,
    }
    fields = {f.name for f in dataclasses.fields(SFTConfig)}
    dropped = [k for k in wanted if k not in fields]
    if "max_length" in fields:
        wanted.pop("max_seq_length", None)
    config = SFTConfig(**{k: v for k, v in wanted.items() if k in fields})
    dropped = [k for k in dropped if k not in ("max_length", "max_seq_length")]
    if dropped:
        print(f"  [info] this TRL version has no SFTConfig field(s): {dropped}")

    trainer_kwargs: dict[str, Any] = {
        "model": model,
        "args": config,
        "train_dataset": train_ds,
        "data_collator": DataCollatorForSeq2Seq(tokenizer, padding=True, label_pad_token_id=-100),
        "callbacks": callbacks or [],
    }
    params = inspect.signature(SFTTrainer.__init__).parameters
    trainer_kwargs["processing_class" if "processing_class" in params else "tokenizer"] = tokenizer
    return SFTTrainer(**trainer_kwargs)


def make_callbacks():
    """NaN/inf stop + loss and GPU-memory logging."""
    from transformers import TrainerCallback

    class NanStop(TrainerCallback):
        def on_log(self, args, state, control, logs=None, **kwargs):
            loss = (logs or {}).get("loss")
            if loss is not None and not math.isfinite(loss):
                print(f"\n[STOP] loss became {loss} at step {state.global_step}. "
                      "Lower LR (e.g. 1e-4) or check the data; training stopped.")
                control.should_training_stop = True

    class MemLog(TrainerCallback):
        def on_log(self, args, state, control, logs=None, **kwargs):
            if logs and "loss" in logs and torch.cuda.is_available():
                gb = torch.cuda.max_memory_allocated() / 1024**3
                print(f"  step {state.global_step:>4}  loss {logs['loss']:.4f}  peak GPU {gb:.2f} GB")

    return [NanStop(), MemLog()]


def generate_json(model, tokenizer, queries: list[str], system_prompt: str,
                  kwargs: dict[str, Any], max_new_tokens: int = MAX_NEW_TOKENS) -> list[str]:
    """Greedy generation, one query at a time (fine for a handful of checks)."""
    outputs = []
    model.eval()
    for q in queries:
        msgs = [{"role": "system", "content": system_prompt}, {"role": "user", "content": q}]
        text = tokenizer.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True, **kwargs)
        enc = tokenizer(text, return_tensors="pt", add_special_tokens=False).to(model.device)
        with torch.no_grad():
            out = model.generate(**enc, max_new_tokens=max_new_tokens, do_sample=False,
                                 pad_token_id=tokenizer.pad_token_id, use_cache=True)
        outputs.append(tokenizer.decode(out[0][enc["input_ids"].shape[1]:], skip_special_tokens=True))
    return outputs


def dir_size_mb(path: Path) -> float:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) / 1024**2


# =========================================================================
# Main
# =========================================================================


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        sys.exit(f"[ERROR] {path} not found. Run: python -m ai.finetune.prepare_extraction_dataset")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    ap = argparse.ArgumentParser(description="Local debug LoRA run for the Qwen3 NLU adapter.")
    ap.add_argument("--dry-run", action="store_true",
                    help="load only the tokenizer: check masking and sequence lengths, then exit")
    args = ap.parse_args()

    print("Library versions:")
    print_versions()

    from datasets import Dataset
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    tokenizer.padding_side = "right"
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tkw = template_kwargs(tokenizer)
    print(f"\nChat template kwargs: {tkw or '(none)'}")

    rows = _load_jsonl(DATA)
    tokenized = [tokenize_example(r, tokenizer, tkw) for r in rows]
    lengths = [len(t["input_ids"]) for t in tokenized]
    max_len = measure_max_len(lengths)
    kept = [t for t in tokenized if len(t["input_ids"]) <= max_len]
    print(f"Examples: {len(rows)}  |  tokens min/median/p95/max: {min(lengths)}/"
          f"{int(np.median(lengths))}/{int(np.percentile(lengths, 95))}/{max(lengths)}")
    print(f"MAX_SEQ_LENGTH = {max_len}  ({len(rows) - len(kept)} longer examples dropped, "
          "never truncated: a cut-off JSON would teach broken output)")

    sample = tokenized[0]
    answer_ids = [t for t, lab in zip(sample["input_ids"], sample["labels"]) if lab != -100]
    print(f"\nLoss is computed on {len(answer_ids)} of {len(sample['input_ids'])} tokens of example 0:")
    print("  " + repr(tokenizer.decode(answer_ids)))

    if args.dry_run:
        print("\n[OK] dry run finished — tokenizer, template and masking all work.")
        return

    if not torch.cuda.is_available():
        sys.exit("[ERROR] No CUDA GPU detected. This debug run needs the RTX 3050.")

    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, BitsAndBytesConfig

    from ai.nlu.prompt import NLU_SYSTEM_PROMPT
    from ai.nlu.schema import extract_first_json, validate_model_output

    bf16 = torch.cuda.is_bf16_supported()
    compute_dtype = torch.bfloat16 if bf16 else torch.float16
    print(f"\nLoading {MODEL_NAME} in 4-bit NF4 (compute dtype {compute_dtype}) ...")
    t0 = time.time()
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        quantization_config=BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=compute_dtype),
        device_map={"": 0},
        **dtype_kwarg(compute_dtype),
    )
    model.config.use_cache = False
    print(f"  loaded in {time.time() - t0:.1f}s, GPU {torch.cuda.memory_allocated() / 1024**3:.2f} GB")

    model = prepare_model_for_kbit_training(
        model, use_gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False})
    lora_cfg = yaml.safe_load(LORA_CONFIG_PATH.read_text(encoding="utf-8"))
    model = get_peft_model(model, LoraConfig(**lora_cfg))
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    pct = 100 * trainable / total
    print(f"  trainable parameters: {trainable:,} of {total:,} ({pct:.2f}%)")
    assert 0 < pct < 5, f"trainable share {pct:.2f}% is outside (0, 5) — check target_modules"

    train_ds = Dataset.from_list(kept)
    # Trainer scratch lives outside OUTPUT_DIR so the adapter folder holds only the adapter.
    trainer = build_trainer(model, tokenizer, train_ds, str(SCRATCH_DIR), max_len,
                            epochs=EPOCHS, lr=LR, batch=BATCH, grad_accum=GRAD_ACCUM,
                            bf16=bf16, callbacks=make_callbacks())

    print(f"\nTraining {EPOCHS} epochs on {len(kept)} examples ...")
    t0 = time.time()
    try:
        result = trainer.train()
    except torch.cuda.OutOfMemoryError:
        print("\n[OOM] Out of GPU memory. Try, in order:\n"
              "  1. Reduce MAX_SEQ_LENGTH (drop the clamp floor from 256 to 192 in measure_max_len)\n"
              "  2. Switch MODEL_NAME to 'Qwen/Qwen3-0.6B'")
        sys.exit(1)
    print(f"\nTraining done in {(time.time() - t0) / 60:.1f} min, final train loss {result.training_loss:.4f}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)
    size = dir_size_mb(OUTPUT_DIR)
    print(f"Adapter saved to {OUTPUT_DIR} ({size:.1f} MB)")
    assert size < MAX_ADAPTER_MB, f"adapter is {size:.0f} MB — expected well under {MAX_ADAPTER_MB} MB"

    print("\nSanity check on held-out val queries (greedy):")
    model.config.use_cache = True
    val_rows = _load_jsonl(VAL_DATA)[:SANITY_QUERIES]
    queries = [r["messages"][1]["content"] for r in val_rows]
    for q, raw in zip(queries, generate_json(model, tokenizer, queries, NLU_SYSTEM_PROMPT, tkw)):
        obj = extract_first_json(raw)
        valid = obj is not None and validate_model_output(obj) is not None
        print(f"\n  query : {q}\n  output: {raw.strip()}\n  JSON parsed: {obj is not None}, valid: {valid}")


if __name__ == "__main__":
    main()
