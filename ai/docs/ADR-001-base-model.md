# ADR-001 — Base Model Selection

**Date:** 2026-08-19
**Status:** Accepted
**Decided by:** Person 1 (AI/RAG track)

## Decision

**Base model for LoRA fine-tuning: `mistralai/Mistral-7B-v0.1`**
**Local debug stand-in: `microsoft/Phi-3-mini-4k-instruct`**

## Rationale

| Factor | Mistral 7B | Llama 3 8B |
|---|---|---|
| License | ✅ Apache 2.0 | ⚠️ Meta custom license |
| 4-bit VRAM (training, T4) | ~10–12 GB ✅ comfortable | ~12–14 GB ⚠️ tight |
| PEFT/trl tooling | Mature, many reference configs | Mature, minor edge-case bugs |
| Production-safe? | ✅ Yes | ⚠️ Ambiguous |

Apache 2.0 is the decisive factor for a project with potential production use.
Mistral also fits the Kaggle T4 (16GB) more comfortably during LoRA training.

## Debug Strategy

Phi-3-mini (3.8B, ~2.5GB at 4-bit) is used on the RTX 3050 (4GB VRAM) only
to validate the training pipeline plumbing. All scripts load the model via a
`MODEL_NAME` config variable so swapping Phi-3-mini → Mistral 7B for Kaggle
is a single env-var change.

## Environment Variables

```
BASE_MODEL=mistralai/Mistral-7B-v0.1
DEBUG_MODEL=microsoft/Phi-3-mini-4k-instruct
```

These are set in `.env` and read by all fine-tuning scripts via `python-dotenv`.
