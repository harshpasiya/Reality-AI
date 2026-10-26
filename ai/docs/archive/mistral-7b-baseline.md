# Mistral-7B Generative Baseline (Archived)

**Date:** 2026-10-23  
**Status:** Archived & Superseded by [ADR-002](../ADR-002-qwen3-nlu-model.md)  
**Author:** Person 1 (AI/RAG Track)  

---

## 1. Overview & What We Ran

In the initial phase of Reality AI ([ADR-001](../ADR-001-base-model.md)), we pursued a fully generative assistant where a fine-tuned large language model would ingest retrieved property listings and write conversational customer replies from scratch.

### Setup & Configurations
- **Base Model:** `mistralai/Mistral-7B-v0.1` (selected for its open Apache 2.0 license and strong foundational reasoning capabilities).
- **Fine-Tuning Technique:** QLoRA (Quantized Low-Rank Adaptation) using `bitsandbytes` NF4 (Normal Float 4-bit) precision with double quantization.
- **LoRA Configuration:**
  - Rank ($r$): 16
  - Scaling factor ($\alpha$): 32 (2× rank convention)
  - Dropout: 0.05
  - Target Modules: All attention projections (`q_proj`, `k_proj`, `v_proj`, `o_proj`)
  - Optimizer: `paged_adamw_8bit` with gradient checkpointing
- **Training Infrastructure:** Remote Kaggle environment running on a single NVIDIA Tesla T4 GPU (16 GB VRAM).
- **Dataset Size:** 750 synthetically generated domain-specific conversation examples tailored to the Surat, Gujarat real estate market (`ai/finetune/prepare_dataset.py`). The dataset encompassed diverse query patterns including locality-based searches, budget and BHK configurations, nearby amenities (schools, hospitals, transit), multi-turn follow-ups, and polite off-topic guardrail redirects.
- **Chat Template:** Custom ChatML prompt formatting (`<|im_start|>` and `<|im_end|>`) injected into the tokenizer, as the base Mistral model did not come with an inherent instruction/chat template.

---

## 2. Training Results

- **Loss Convergence:** Training loss showed healthy, steady convergence over 3 epochs, dropping from an initial **1.54** down to approximately **0.06**.
- **Wall-Clock Duration:** The single complete training run required **6+ hours** on the Kaggle T4 GPU.
- **Artifact Output:** The final extracted LoRA adapter weights (`adapter_model.bin` / `adapter_config.json`) totaled around **52 MB**.

---

## 3. Problems & Obstacles Encountered

During the development, training, and export process of this 7B baseline, we hit multiple technical hurdles:

### 1. `bitsandbytes` and `triton` Version Errors
Kaggle's pre-installed GPU environment experienced version drift. Default combinations of `bitsandbytes` and PyTorch threw CUDA compilation failures and Triton dependency errors when attempting 4-bit quantization kernels. Resolving this required pinning compatible combinations (specifically downgrading `bitsandbytes` from 0.45 to `0.43.3` to match `transformers 4.46.3`).

### 2. SafetensorError on Checkpoint Save
When attempting to save the model and adapter states, serialization threw `SafetensorError` due to shared tensor memory handles and metadata mismatches during 4-bit quantized serialization. The model save pipeline had to be carefully adjusted to save only the adapter layer tensors rather than attempting full-model serialization.

### 3. The 20.6 GB Zip Archive
The training script originally pointed both the trainer's intermediate checkpointing (`save_strategy="epoch"`) and the final output packaging to the same output directory (`/kaggle/working/output`). When `shutil.make_archive()` executed, it recursively zipped every intermediate checkpoint directory—including full model weight shards, optimizer states, and cached layers across all epochs—resulting in an unwieldy **20.6 GB zip file** instead of a clean, lightweight 52 MB LoRA adapter archive.

### 4. Lost Run from an Accidental Session Restart
Early training attempts were executed inside an interactive Kaggle Jupyter session. A browser disconnection and subsequent container session restart abruptly wiped the ephemeral `/kaggle/working` state after nearly 4 hours of training, wasting valuable compute time and consuming a large portion of the 30-hour weekly GPU quota.

### 5. TRL Kwargs Drift & Padding-Side Warnings
API transitions between TRL versions (such as `trl 0.12.x` vs `trl 0.15.x`) caused repeated failures:
- Parameters like `max_seq_length`, `packing`, and `processing_class` moved between `TrainingArguments`, `SFTConfig`, and `SFTTrainer`, triggering unexpected keyword argument crashes.
- Mistral's tokenizer defaults triggered recurring warnings: `A decoder-only architecture is being used, but right-padding was detected! For proper generation results, please set padding_side='left'`. Proper coordination between right-padding during training and left-padding for autoregressive generation had to be manually enforced.

---

## 4. Why We Replaced It

Despite achieving low training loss, the generative Mistral-7B baseline was ultimately superseded ([ADR-002](../ADR-002-qwen3-nlu-model.md)) for two decisive reasons:

1. **Hardware Infeasibility on Local Machines (4 GB VRAM):**
   - The team's primary local target is an NVIDIA GeForce RTX 3050 Laptop GPU with **4 GB VRAM**.
   - Even in 4-bit quantization, Mistral-7B requires ~4.5–5.0 GB of memory just for base weights and KV cache.
   - Pushing the model onto 4 GB forced CPU memory offloading, which caused meta-tensor hook errors (`RuntimeError: Tensor.item() cannot be called on meta tensors`) or degraded inference response latency to 30–60 seconds per turn—unusable for a responsive pitch or production app.

2. **Architecture-to-Task Mismatch (Risk of Hallucination):**
   - The core objective of the AI assistant is **query understanding**: converting natural language queries into structured search parameters (locality, BHK count, budget in rupees, property type, and keywords) to filter the PostgreSQL/pgvector database.
   - Using a free-form 7B generative model introduces unnecessary complexity and the danger of hallucinations (e.g., describing property amenities or prices not found in the actual database).
   - A compact, task-focused model (such as Qwen3) dedicated strictly to structured JSON extraction, combined with deterministic parsing rules and templated property responses, eliminates hallucinations entirely while fitting comfortably within local memory constraints.

---

## 5. What We Kept (Lessons Learned)

The challenges faced during the Mistral-7B run established essential engineering practices that we carry forward into all future model training:

1. **Headless Committed Runs:**
   - Never rely on interactive browser sessions for runs lasting longer than 15 minutes.
   - Always launch long-running jobs using Kaggle's "Save & Run All" (committed batch runs), which execute headlessly in isolated containers and persist outputs reliably regardless of network disconnects.

2. **Strict Separation of Checkpoint and Export Directories:**
   - Maintain dedicated, isolated paths for trainer checkpoints (`/kaggle/working/checkpoints`) and the final exported adapter (`/kaggle/working/export/adapter`).
   - When zipping artifacts for download, package only the clean adapter directory, preventing bloated multi-gigabyte archives.

3. **Mandatory Fast Smoke Tests:**
   - Never initiate an expensive multi-hour training run without first validating the pipeline via a localized smoke test.
   - Run 1–2 steps on a micro-dataset (50–100 samples) locally or on a debug checkpoint to verify dataset parsing, chat template rendering, tokenizer padding, trainer argument compatibility, and export serialization end-to-end before spending GPU quota.
