# Reality AI — AI Track Architecture

**Track:** AI / RAG (Person 1) · **Status:** current as of 2026-10-25 ·
**Decision record:** [ADR-002](ADR-002-qwen3-nlu-model.md) ·
**Baseline:** [archive/mistral-7b-baseline.md](archive/mistral-7b-baseline.md)

## 1. Role of the AI track

Reality AI is a property search platform for Surat, Gujarat: customers chat
and see matching listings on a map, brokers publish listings. The AI track
turns a customer's chat message into the listings to show and the reply to
send. It is imported by the backend as plain Python modules with frozen
signatures (`Reality-AI-AGENTS.md` Section 5):

| Function | Job |
|---|---|
| `ai.rag.retriever.search(query, candidate_ids=None, top_k=5)` | Understand the message, filter and rank listings |
| `ai.inference.generate_response(query, listings, history)` | Write the chat reply from the listings `search()` returned |
| `ai.rag.boundary_filter.get_candidates(polygon)` | Listing IDs inside a polygon drawn on the map |
| `ai.embeddings.embed_listings.embed_single(listing_id)` | Compute a listing's embedding |
| `ai.amenities.amenities_service.fetch_and_cache(listing_id)` | Cache nearby schools, hospitals, transit, parks and restaurants from Google Places |

The backend calls `search()` first, so the filtered listings are available
for the map before the reply text is built; the reply then takes under 1 ms.

```
message ──► parse_query ──► SQL filters + pgvector ranking ──► listings ──► map / list
              (rules + Qwen3 LoRA,        (relaxation ladder)          │
               validated, merged,                                     ▼
               cached)                                    generate_response ──► reply text
                                                          (templates, no LLM)
```

## 2. Why a small fine-tuned model for query understanding

The first design (ADR-001) fine-tuned **Mistral-7B** with QLoRA to *write*
every reply from the retrieved listings. It trained (loss 1.54 → ~0.06 over 3
epochs on 750 synthetic conversations, 6+ hours on a Kaggle T4), but two
problems ended it:

1. **Hardware.** The team's GPU is an RTX 3050 with 4 GB VRAM. Mistral-7B
   does not fit even in 4-bit; CPU offloading gave meta-tensor errors or 30–60
   s per reply.
2. **Task mismatch.** The listings come from the database. What the chat
   needs from a language model is to understand the request: BHK, locality,
   budget, property type, preferences, and whether it is a property question
   at all. A free-form generator is oversized for that and can describe
   properties or prices that are not in the data.

The current design gives the model one narrow job. A **Qwen3-4B-Instruct-2507**
LoRA adapter converts the message into a fixed JSON object; code does the
arithmetic, validates places and writes the reply. The full baseline,
including its training problems and the practices kept from it (committed
headless runs, separate checkpoint and export folders, smoke tests first), is
in [archive/mistral-7b-baseline.md](archive/mistral-7b-baseline.md).

## 3. The NLU pipeline

`ai.nlu.query_parser.parse_query(query)` always returns a `ParsedQuery` and
never raises.

| Stage | Module | What it does |
|---|---|---|
| Rules parser | `ai/nlu/rules.py` | Regex and gazetteer extraction of prices, BHK, property type, keywords and locality. Exact rupee arithmetic. Runs in ~0.2 ms. |
| Model | `ai/inference/load_model.py`, `query_parser._generate` | Qwen3-4B + LoRA, 4-bit NF4 on the GPU, greedy decoding, one call at a time (a lock). Loaded once as a singleton. |
| Validation | `ai/nlu/schema.py` | Extracts the first JSON object, checks every field's type and range, maps localities to gazetteer names and keywords to the canonical vocabulary. Prices come back as `{amount, unit}`, exactly as written; code converts lakh/crore to rupees. Invalid output → rules. |
| Hybrid merge | `query_parser.merge` | Prices from rules when rules found one; BHK, locality, property type from the model, falling back to rules where the model left a field empty; keywords from both. A model locality is dropped unless some name or alias of it fuzzily appears in the text (rapidfuzz `partial_ratio` ≥ 80). If the model says "not a property query" but rules found two or more signals, rules win. |
| Cache | `functools.lru_cache` (256) | `search()` and `generate_response()` parse the same message; the model runs once. |

**Backends** (`NLU_BACKEND`): `hybrid` (default), `rules` (no GPU), `model`
(evaluation only). With no CUDA GPU or no adapter the system falls back to
rules automatically, so a backend machine without a GPU still works.

**Why the merge looks like this.** On the evaluation set the two parsers fail
on different queries: rules break on typos and off-topic messages, the model
occasionally leaves out a value the rules found ("rander me 2bhk flat
dikhao" → no locality). Filling the model's gaps from rules moved hybrid exact
match from 96.7% to 99.3% (Section 7). The locality check guards against the
model inventing a real place; in validation, "villas batavo" (Gujarati:
"show villas") was read as the locality Bhatar.

## 4. Retrieval: SQL pre-filters, pgvector ranking, gazetteer, relaxation

`search()` turns the parsed query into SQL filters, then ranks the remaining
listings by `embedding <-> query_vector` (Euclidean distance between
384-dimensional MiniLM embeddings, pgvector).

- **Price:** `price >= :min`, `price <= :max`.
- **Property type:** `flat` or `house_land`.
- **BHK:** bedroom count equality.
- **Locality:** the gazetteer (`ai/nlu/gazetteer.py`, 20 localities and 33
  landmarks with aliases) gives a centre point and radius (1.5–2.5 km); SQL
  keeps listings within it using PostGIS `ST_DWithin` on geography (metres).
- **Polygon:** `candidate_ids` from `get_candidates()` restrict the search.

No vector index is used: at demo scale an exact scan is fast, and an
approximate index (IVFFlat, removed) can return its nearest rows first and
then lose them to the filters.

**Relaxation ladder.** If the exact filters match nothing, `search()` retries
in a fixed order and labels each result with a `match_note`:

1. `exact`
2. `relaxed_radius` — the locality radius doubled
3. `relaxed_bhk` — BHK dropped
4. `relaxed_locality` — locality dropped

**Price and property type are never relaxed.** A customer with a 50 lakh
budget cannot use a 90 lakh flat, and someone looking for a plot does not
want a flat; showing them would look like a match but break the request. If
nothing fits, the reply says so instead.

## 5. Templated replies

`generate_response()` builds the reply from the listings it is given, using
fixed sentence templates (`ai/inference/generate_response.py`):

- an opening line with the count and the filters understood ("matching
  3 BHK flat in Vesu, up to Rs.80.0 L"), or "close to what you asked for" when the
  search had to relax;
- one sentence per relaxation step used, saying which filter was loosened;
- one line per listing: title, price in lakh/crore, type, BHK;
- a "no results" reply that names the filters when nothing matched;
- nearby amenities from the cached Google Places data, only when the message
  asks about schools, hospitals, transit and similar;
- a polite redirect for off-topic messages, varied deterministically by a hash
  of the message.

Because no language model writes reply text, the reply can only mention
listings, prices and amenities that are in the data it was given: it cannot
hallucinate a property.

## 6. Fine-tuning method

**Dataset by exact-label generation** (`ai/finetune/prepare_extraction_dataset.py`).
Each example starts as a structured label sampled according to
`ai/nlu/LABELING_RULES.md` and is then rendered into text from templates
(English, Hinglish, Gujarati written in English), with typo noise, landmark
mentions and off-topic messages (including casual mentions of a Surat place
or a home word). Because the text is built from the label, the two cannot
disagree. Splits: 3,000 training, 300 validation, 200 local-debug examples.
About 25% of phrasing templates are held out of training and appear only in
validation, so validation measures unseen phrasing, not just unseen values.

**Hand-written evaluation set** (`ai/nlu/eval_set.jsonl`): 150 queries written
by hand, with no overlap with the generated data, tagged by type (normal,
typo, Hinglish, Gujarati, off-topic, landmark, price forms, keywords, edge
cases). This, not the validation split, is the real test.

**Training.** QLoRA: base model in 4-bit NF4 with double quantisation; LoRA
on all seven projections (`q_proj`, `k_proj`, `v_proj`, `o_proj`,
`gate_proj`, `up_proj`, `down_proj`); loss only on the answer tokens (prompt
tokens masked).

| Setting | Local debug (RTX 3050, 4 GB) | Full run (Kaggle T4, 16 GB) |
|---|---|---|
| Base model | Qwen/Qwen3-1.7B | Qwen/Qwen3-4B-Instruct-2507 |
| LoRA r / alpha / dropout | 8 / 16 / 0.05 | 16 / 32 / 0.05 |
| Epochs, learning rate | — | 3, 2e-4 |
| Effective batch, max length | — | 16, 256 tokens |
| Steps, time | — | 561 steps, 97 min |
| Final training loss | 0.79 → 0.03 | 0.0165 |
| Adapter size | 48.5 MB | 132 MB |

The 1.7B debug run only proves the pipeline; its adapter is not used.

## 7. Results

All figures below are measured; nothing is estimated.

**Validation split (300 generated queries, held-out templates), Kaggle T4:**
100% valid JSON, 99.3% exact match. Generated data is easier than real
queries, so this mainly confirms training worked.

**Hand-written evaluation set (150 queries), RTX 3050 laptop.** Exact match
means all seven fields correct. Source: `ai/docs/nlu-eval-rules.md`,
`nlu-eval-qwen3-4b-model.md`, `nlu-eval-qwen3-4b-hybrid.md`.

| Metric | Rules | Qwen3-4B model | Hybrid |
|---|---|---|---|
| Exact match | 91.3% | 96.7% | **99.3%** |
| is_property_query | 96.7% | 100.0% | 100.0% |
| bhk | 100.0% | 100.0% | 100.0% |
| locality | 98.0% | 98.7% | 99.3% |
| property_type | 98.7% | 100.0% | 100.0% |
| price_min | 100.0% | 100.0% | 100.0% |
| price_max | 98.7% | 100.0% | 100.0% |
| keywords | 97.3% | 98.0% | 100.0% |
| keywords F1 | 95.7% | 96.8% | 100.0% |
| Valid model output | n/a | 100.0% | 100.0% |
| Parse latency, median | 0.2 ms | 7.9 s | 8.0 s |
| Parse latency, p95 | 1.5 ms | 10.3 s | 9.4 s |

| Tag (n) | Rules | Model | Hybrid |
|---|---|---|---|
| typo (14) | 42.9% | 92.9% | 92.9% |
| offtopic (12) | 66.7% | 100.0% | 100.0% |
| no-filters (6) | 83.3% | 100.0% | 100.0% |
| hinglish (18) | 100.0% | 88.9% | 100.0% |
| keywords (14) | 100.0% | 92.9% | 100.0% |
| edge-case (5) | 100.0% | 80.0% | 100.0% |
| all other tags (81) | 100.0% | 100.0% | 100.0% |

The model earns its place on exactly the messages rules cannot handle:
misspellings (42.9% → 92.9%) and off-topic chat (66.7% → 100%). The one
remaining hybrid failure is "flat near dumas bech 1 cr": both parsers return
the locality Dumas instead of the landmark Dumas Beach, so the search still
covers the right area.

**End-to-end pipeline** (`ai/inference/_test_pipeline.py`, 26 queries, hybrid,
local database), per stage:

| Stage | Mean | Median | p95 |
|---|---|---|---|
| Parse | 10,667 ms | 9,357 ms | 12,594 ms |
| Retrieve (SQL + pgvector) | 30.6 ms | 16.9 ms | 139.5 ms |
| Reply | 0.2 ms | 0.1 ms | 0.2 ms |

The first parse includes loading the model. One of the 26 queries fell back
to rules.

**Model load time and GPU memory on the RTX 3050** are measured by
`python -m ai.nlu.run_all_evals` and written to `ai/docs/nlu-eval-runtime.json`;
add them here from that file once it has been run.

**Latency verdict.** About 8 s per message on a 4 GB laptop GPU is slow but
was judged acceptable for this project, because the listings reach the map
before the reply and the reply itself is instant. Machines without a GPU use
`NLU_BACKEND=rules` (91.3% exact match, under 2 ms).

## 8. Limitations

- **Approximate prices.** "around 70 lakh" is treated as a maximum; there is
  no ± band. Thousands shorthand ("15k") and rent are not supported.
- **One locality per query.** "Vesu or Citylight" keeps only the first.
- **Follow-up questions.** Each message is parsed on its own, so "show me
  something cheaper" does not inherit the previous filters (playbook Part F,
  optional, not done).
- **Gazetteer coverage.** Places outside the 20 localities and 33 landmarks
  (for example Reliance Mall) are not recognised. New entries work with rules
  immediately; the model learns them only after retraining. Several landmark
  coordinates are marked "verify on Google Maps".
- **Synthetic data.** Listings and training queries are generated; the
  Hinglish and Gujarati templates need review by a native speaker.
- **Latency.** ~8 s per message on the RTX 3050 with Hugging Face
  `generate()`; a quantised llama.cpp runtime would be faster but changes the
  stack.
- **Schema mapping at merge.** The AI code currently runs against a local
  stand-in table (`listings` with `lat`, `lng` and `bhk` columns). At merge it
  must switch to the backend's `listing` table (`location` geometry, bedrooms
  inside `rooms` JSON). The required schema decisions are written up for the
  backend track in "Reality AI — Database Schema Recommendations for Person 2".
- **Library versions.** The adapter was saved with transformers 5.x on
  Kaggle; the local transformers 4.57 cannot read its tokenizer config, so the
  loader falls back to the base model's identical tokenizer.
