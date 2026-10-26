# ADR-002 — Qwen3 for Query Understanding Instead of a Generative 7B Model

**Date:** 2026-10-23
**Status:** Accepted
**Supersedes:** ADR-001 (Mistral-7B-v0.1 as the fine-tuned base model)
**Decided by:** Person 1 (AI/RAG track)

## Context

ADR-001 selected `mistralai/Mistral-7B-v0.1` as the base model for a LoRA
fine-tuned assistant that would write every chat reply from the retrieved
listings. Building that pipeline exposed three problems:

1. **Hardware.** Mistral-7B does not fit the project's only local GPU, an
   RTX 3050 with 4 GB VRAM, even at 4-bit quantisation. Every inference test
   therefore depended on remote hardware, and the model could not be shipped
   as part of a demo running on team hardware.
2. **Training cost.** A single LoRA run on a Kaggle T4 took more than six
   hours of wall-clock time, consuming a large share of the free weekly GPU
   quota and making iteration slow.
3. **Mismatch with the task.** The product's backend already returns the
   matching listings for the map and list views. What the chat layer actually
   needs from a language model is to turn a user sentence into structured
   search filters — bedroom count (BHK), locality, price range, property type,
   soft preference keywords, and whether the message is a property query at
   all. A free-form 7B generator is far larger than this task requires, and
   generating replies freely introduces a risk of describing properties or
   prices that are not in the retrieved data.

## Decision

- Use **`Qwen/Qwen3-4B-Instruct-2507`** with a LoRA adapter for **query
  understanding only**: the model reads the user's message and outputs a
  single JSON object containing the filter fields listed above.
- Use **`Qwen/Qwen3-1.7B`** as the local debugging proxy on the 4 GB GPU, to
  validate the training pipeline before spending Kaggle GPU hours.
- **Rupee arithmetic and locality matching are performed by deterministic
  code, never by the model.** The model reports prices as an amount and unit
  exactly as written (for example `{"amount": 0.8, "unit": "crore"}`); code
  converts them. Locality names are validated against a Surat gazetteer.
- Every model output is validated against a fixed schema. Invalid output
  falls back to a rules-based parser, which also serves when no GPU or adapter
  is available.
- **Chat replies are templated from the retrieved listings.** No language
  model writes reply text, so a reply cannot mention a property that
  retrieval did not return.
- Retrieval is unchanged in spirit: SQL pre-filters derived from the parsed
  query narrow the candidate set, and the existing MiniLM embeddings with
  pgvector rank what remains.

The licence of both Qwen3 checkpoints is stated as Apache 2.0 on their model
cards; this must be re-verified on the cards before any production use.

## Alternatives Considered

| Alternative | Outcome | Reason |
|---|---|---|
| Keep Mistral-7B (ADR-001) | Rejected | Does not fit 4 GB VRAM; slow to train; oversized for filter extraction. |
| Rules-only parser | Kept as fallback and evaluation baseline | Deterministic and fast, but expected to be brittle on misspellings, code-mixed (Hinglish / Gujarati-in-English) and unusual phrasing. The fine-tuned model must outperform it on the hand-written evaluation set to justify its inclusion. |
| `Qwen/Qwen2.5-3B-Instruct` | Rejected | Older generation, and its licence terms were not verified for this project. |
| `meta-llama/Llama-3.2-3B-Instruct` | Rejected | Gated download and a custom licence requiring separate review. |

## Consequences

- **Replies are no longer model-generated.** They are deterministic and
  grounded, but less conversational in tone than a generative assistant.
- **Follow-up questions need extra work.** Each message is parsed on its own,
  so a message such as "show me something cheaper" has no filters to inherit.
  An optional follow-up mechanism (merging filters from earlier turns) is
  planned separately and requires agreement from the backend track because it
  adds an optional parameter to `retriever.search()`.
- **Public function signatures are unchanged.** `retriever.search(query,
  candidate_ids=None, top_k=5)` and `generate_response(query, listings,
  history)` keep their documented signatures, so the backend and frontend
  tracks are unaffected apart from one additional optional result key.
- **The shared contract must be updated.** The tech-stack row in `AGENTS.md`
  names Llama 3 8B or Mistral 7B; it must be amended and communicated to the
  other tracks.
- **Library versions move forward.** Qwen3 requires `transformers >= 4.51`,
  so the Kaggle notebook needs newer library versions than the Mistral run
  used.
- **Evaluation becomes measurable.** Because the model's output is
  structured, it can be scored field by field against a hand-labelled
  evaluation set, and compared directly with the rules-only baseline. Results
  will be reported in `ai/docs/nlu-eval-*.md`; no figures are claimed here.
