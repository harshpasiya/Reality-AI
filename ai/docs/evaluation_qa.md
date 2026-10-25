# Reality AI — Practical Evaluation Q&A Cheat Sheet

> **Your project:** AI-powered real estate chat assistant for Surat, Gujarat. A LoRA-fine-tuned Qwen3-4B model (plus a rules parser) turns each chat message into search filters; PostgreSQL filters and pgvector semantic search find the listings; PostGIS handles locality radius and drawn-boundary search; replies are built from templates; nearby amenities are cached from the Google Places API. Full write-up: `ai/docs/ai-architecture.md`.

---

## 1. Project Architecture & Overview

**Q: What is Reality AI?**
> An AI-powered real estate platform where customers search properties through a chat assistant next to a map. The assistant understands the request ("2 bhk in vesu under 80 lakh"), retrieves matching listings from the database, and replies with them. It supports boundary search (draw on the map) and cached nearby amenities.

**Q: Explain the overall architecture.**
> Three tracks: **AI/RAG** (my track — query understanding, embeddings, retrieval, fine-tuning, replies), **Backend** (FastAPI, PostgreSQL, REST API), and **Frontend** (React, Google Maps). The backend imports my AI modules directly as Python packages — no HTTP between AI and Backend. The frontend talks to the backend via REST APIs.

**Q: What is RAG and how does your project use it?**
> RAG = Retrieval-Augmented Generation: answer from retrieved data instead of what a model memorised. We retrieve listings from our own database first and build the answer only from them. Our "generation" step is deliberately templated rather than an LLM writing free text, so the reply can only mention properties that were actually retrieved — it cannot hallucinate a listing or a price.

**Q: Where is the language model used, then?**
> Only for **query understanding**. The fine-tuned Qwen3-4B model reads the customer's message and outputs one JSON object: `is_property_query`, `bhk`, `locality`, `price_min`, `price_max`, `property_type`, `keywords`. Code then converts prices to rupees, validates the locality against a Surat gazetteer, and runs the SQL.

**Q: Why not just use ChatGPT/GPT-4 API directly?**
> (1) **Cost** — no per-call fees; the model runs on our own GPU. (2) **Control** — fine-tuned on our exact output format and labeling rules, measured on our own test set. (3) **Privacy** — listing and chat data stay local. (4) **Fallback** — a rules parser covers machines with no GPU, so the system never depends on an external service.

**Q: How do the three tracks integrate?**
> The backend imports AI modules directly in the same Python process:
> - `ai.rag.retriever.search(query, candidate_ids=None, top_k=5)` — understand + filter + rank
> - `ai.rag.boundary_filter.get_candidates(polygon)` — polygon search
> - `ai.inference.generate_response(query, listings, history)` — chat reply
> - `ai.embeddings.embed_listings.embed_single(listing_id)` — embed new listings
> - `ai.amenities.amenities_service.fetch_and_cache(listing_id)` — cache nearby POIs
>
> These function signatures are frozen in `AGENTS.md` — the shared contract between all three tracks. The model change did not alter any of them.

---

## 2. Embeddings & Semantic Search

**Q: What embedding model did you use and why?**
> `all-MiniLM-L6-v2` from sentence-transformers. It produces 384-dimensional vectors, runs fast on both CPU and GPU, and is well-suited for semantic similarity. It's small (~80 MB) so it loads quickly.

**Q: How does the embedding pipeline work?**
> 1. `build_listing_text()` combines title, description, price, property type, and amenities into a natural-language paragraph
> 2. `EmbeddingModel.embed()` converts that text into a 384-dim L2-normalised vector
> 3. The vector is stored in the `embedding` column (pgvector `vector(384)`) in PostgreSQL
> 4. At query time, the user's message is embedded with the same model, and pgvector orders the filtered listings by distance to it

**Q: Why do you normalize embeddings?**
> With `normalize_embeddings=True` every vector has length 1, so Euclidean distance and cosine distance give the same ranking (for unit vectors, L2² = 2 − 2·cos). We can use pgvector's `<->` (Euclidean) operator and still rank by meaning.

**Q: What is pgvector?**
> A PostgreSQL extension that adds vector data types and similarity operators. We store 384-dimensional vectors next to the normal columns (title, price, location) and order results with `<->`, the Euclidean-distance operator.

**Q: What index do you use for vector search?**
> None, on purpose. At our scale (~200 listings) an exact scan takes milliseconds (median 12 ms for the whole retrieval step in our pipeline run). We first used an IVFFlat index but removed it: an approximate index returns its nearest rows first and the SQL filters (price, BHK, area) can then discard most of them, leaving fewer than 5 results. With thousands of listings we would add an HNSW index with pgvector's iterative scan.

**Q: How does `retriever.search()` work step by step?**
> 1. Validate the query (non-empty) and `top_k` (positive, capped at 50)
> 2. If `candidate_ids` is an empty list → return `[]` (the drawn boundary matched nothing)
> 3. `parse_query(query)` → filters; if it's not a property question → return `[]`
> 4. Embed the query
> 5. Build SQL: price range, property type, BHK, `ST_DWithin` radius around the locality, `id = ANY(:candidate_ids)`, `embedding IS NOT NULL`, ordered by `embedding <-> :query_vector`
> 6. If nothing matches, relax step by step: radius ×2 → drop BHK → drop locality (never price or type)
> 7. Return dicts with id, title, description, price, property_type, bhk, lat, lng, amenities, distance_score, and `match_note` saying which step matched

**Q: What is `distance_score` in the results?**
> The pgvector Euclidean distance between the query vector and the listing vector. For unit vectors it runs from 0 (identical) to 2 (opposite); lower = more similar. It is used for ranking, not shown to the customer.

**Q: Why not use a vector database like Pinecone or Weaviate?**
> PostgreSQL with pgvector keeps everything in one database — vectors, listing data, PostGIS geometry — so filters and vector ranking run in one SQL query. No separate service, no sync issues. At our scale it is more than fast enough.

---

## 3. Query Understanding & Fine-Tuning

**Q: What base model did you use?**
> `Qwen/Qwen3-4B-Instruct-2507` (4 billion parameters) with a LoRA adapter, for query understanding only. For debugging the training pipeline locally I used `Qwen/Qwen3-1.7B`, which fits the 4 GB laptop GPU.

**Q: Didn't you start with a bigger model?**
> Yes — Mistral-7B, fine-tuned to write the whole reply (documented in `ai/docs/archive/mistral-7b-baseline.md` and ADR-001). It trained (loss 1.54 → ~0.06) but did not fit our 4 GB RTX 3050 even in 4-bit, took 6+ hours per Kaggle run, and a free-form generator can describe properties that are not in the data. Since the listings come from the database anyway, the model only needs to understand the request. ADR-002 records the switch.

**Q: What does the model output?**
> One JSON object, for example for "3bhk flat in vesu under 80 lakh":
> ```json
> {"is_property_query": true, "bhk": 3, "locality": "Vesu", "price_min": null,
>  "price_max": {"amount": 80, "unit": "lakh"}, "property_type": "flat", "keywords": []}
> ```
> Prices are copied as written (`amount` + `unit`); code multiplies by 1,00,000 or 1,00,00,000. Models are unreliable at arithmetic; code is exact.

**Q: Why combine the model with a rules parser?**
> Each fails on different messages. On our 150 hand-written test queries, rules alone got 91.3% fully correct but only 42.9% of misspelled queries and 66.7% of off-topic ones; the model got 96.7% overall but occasionally left out a value the rules found. The hybrid merge takes prices from rules, other fields from the model with rules filling any gaps, and keywords from both: **99.3%** fully correct. Rules also run alone when there is no GPU.

**Q: What stops the model from inventing a locality?**
> Validation and a grounding check. Its locality must be a name in our Surat gazetteer (20 localities, 33 landmarks), and the hybrid merge drops it unless some name or alias of that place fuzzily appears in the message. Example caught in validation: "villas batavo" ("show villas" in Gujarati) read as the locality Bhatar.

**Q: What is LoRA and why did you use it?**
> LoRA (Low-Rank Adaptation) freezes the original weights and trains small low-rank matrices added to chosen layers. Only a tiny fraction of parameters is trained, so a 4B model can be fine-tuned on a free Kaggle T4 (16 GB), and the result is a small adapter file (132 MB) instead of a full model copy.

**Q: What are the LoRA hyperparameters and why?**
> - **r = 16** (rank) — double the local debug run's r = 8; more capacity for typos, Hinglish and off-topic cases
> - **lora_alpha = 32** — the 2× rank convention, so the learning rate transfers between configs
> - **lora_dropout = 0.05** — light regularisation for ~3,000 examples
> - **target_modules** = all seven projections: `q_proj, k_proj, v_proj, o_proj` (attention) and `gate_proj, up_proj, down_proj` (MLP)
> - **task_type = CAUSAL_LM**

**Q: What is 4-bit quantization?**
> `BitsAndBytesConfig` with NF4 (Normal Float 4-bit): each frozen weight is stored in 4 bits instead of 16, about 4× less memory. Double quantization also compresses the quantization constants. This is what lets the 4B model run on a 4 GB laptop GPU for inference.

**Q: How did you create the training dataset?**
> `ai/finetune/prepare_extraction_dataset.py` uses **exact-label generation**: it first samples the answer (the JSON filters) according to `ai/nlu/LABELING_RULES.md`, then writes a sentence from templates that expresses exactly that answer — English, Hinglish and Gujarati-in-English, with typo noise, landmarks and off-topic messages. Because the text is built from the label, the label is always right. 3,000 training, 300 validation and 200 debug examples.

**Q: How do you know it isn't just memorising the templates?**
> Two ways. About 25% of phrasing templates are held out of training and appear only in validation (99.3% exact match there). More importantly, the real test is a separate set of 150 queries written by hand, sharing nothing with the generated data.

**Q: What format is the training data in?**
> JSONL with chat messages; the loss is computed only on the assistant's JSON (prompt tokens are masked):
> ```json
> {"messages": [
>   {"role": "system", "content": "<NLU system prompt>"},
>   {"role": "user", "content": "2bhk adajan 60L"},
>   {"role": "assistant", "content": "{\"is_property_query\":true,\"bhk\":2,\"locality\":\"Adajan\",...}"}
> ]}
> ```

**Q: Where did the actual training happen?**
> On Kaggle with a Tesla T4 (16 GB), as a committed "Save & Run All" run (`train_lora_qwen3_kaggle.ipynb`): 3 epochs, 561 steps, 97 minutes, final loss 0.0165. A 30-step smoke test ran first. The adapter is unzipped to `ai/finetune/adapters/qwen3-nlu-lora/`.

**Q: What training arguments did you use?**
> - 3 epochs, learning rate 2e-4
> - Effective batch size 16, max sequence length 256 tokens (the JSON answers are short)
> - FP16 on the T4: it has no native BF16 (compute capability 7.5); the LoRA weights are kept in FP32 because the FP16 gradient scaler requires it
> - Completion-only loss (prompt masked)

**Q: What problems did you hit on Kaggle?**
> Library drift: the dataset mount path changed, BF16 was reported as "supported" on the T4 through slow emulation and crashed a matrix multiply, and newer PEFT left LoRA weights in BF16, which the FP16 gradient scaler rejects. Fixes: detect native BF16 by compute capability, force the FP32 fallback for TRL's log-prob kernel, and upcast trainable weights to FP32 before training.

---

## 4. Inference Pipeline

**Q: How does the model get loaded for inference?**
> `ai/inference/load_model.py` is a lazy, thread-safe singleton:
> 1. The first `get_model()` call loads the tokenizer, the base model in 4-bit, and attaches the LoRA adapter, then `model.eval()`
> 2. The `(model, tokenizer)` pair is cached in the module
> 3. Later calls return it immediately; a lock makes sure concurrent first calls load it once
> 4. It refuses an adapter trained on a different base model

**Q: What if there's no GPU or no adapter?**
> `is_model_available()` returns False and `get_model()` raises `ModelUnavailableError`; `parse_query()` catches it and uses the rules parser. A backend machine without a GPU therefore still works (`NLU_BACKEND=rules` does this explicitly).

**Q: How does `generate_response()` work?**
> 1. `parse_query(query)` — cached, so the model does not run a second time
> 2. Not a property question → a polite redirect, picked deterministically from a few variants
> 3. No listings → a reply naming the filters that found nothing
> 4. Otherwise: an opening line with the count and the understood filters, a sentence for each relaxation step used, and one line per listing (title, price in lakh/crore, type, BHK)
> 5. Nearby amenities are added only if the message asks about them
> 6. It never raises; on an internal error it returns a short apologetic fallback

**Q: What decoding settings does the model use?**
> Greedy decoding (`do_sample=False`), at most 160 new tokens. The output must be a precise JSON object, so there is no reason for randomness; the same message always gives the same filters.

**Q: How fast is it?**
> Measured on the RTX 3050 (4 GB): parsing with the model takes a median of ~7 s per message (8 s mean); retrieval 12 ms median; the reply under 0.2 ms. The backend calls `search()` first, so the listings can go to the map as soon as they are ready. Rules-only parsing takes under 2 ms.

---

## 5. Prompting

**Q: What does the model's system prompt contain?**
> The output schema and labeling rules (`ai/nlu/prompt.py`): the seven fields and their types, prices as written with unit `lakh`/`crore`/`rupee`, canonical locality names, the keyword vocabulary, and when a message is *not* a property query (for example asking about restaurants in Vesu). The same prompt is used in training and inference.

**Q: How does the amenity-aware reply work?**
> `is_amenity_related(query)` checks the message against a keyword list (school, hospital, nearby, metro, park and similar). If true, each listing line gets a summary of the cached amenities (name, distance, Google rating). If false, amenities are left out to keep the reply short.

---

## 6. Boundary-Aware Search

**Q: What is boundary search?**
> Users can draw a polygon on the map (Google Maps Drawing Library) to define a search area. `boundary_filter.get_candidates(polygon)` runs a PostGIS query to find listings inside that polygon, returning their IDs. These IDs are then passed to `retriever.search(candidate_ids=...)` to restrict the search to those listings.

**Q: How does the PostGIS query work?**
> ```sql
> SELECT id FROM listings
> WHERE ST_Contains(
>     ST_GeomFromText(:polygon_wkt, 4326),
>     ST_SetSRID(ST_MakePoint(lng, lat), 4326)
> )
> ```
> The polygon is converted to WKT format. `ST_Contains` checks if each listing's point falls inside the polygon. SRID 4326 = WGS84 (standard GPS coordinates).

**Q: What if the polygon has fewer than 3 points?**
> Raises `ValueError`. If the ring isn't closed (first ≠ last point), it's auto-closed — a common frontend omission handled gracefully.

**Q: How do boundary search and semantic search combine?**
> Two-stage: (1) `get_candidates(polygon)` → list of IDs inside the drawn area. (2) `search(query, candidate_ids=ids)` → filtered, ranked search restricted to those IDs. If the polygon matches zero listings, `candidate_ids=[]` returns empty immediately without querying.

**Q: How is a locality like "Vesu" searched?**
> The gazetteer gives Vesu a centre point and radius (1.5–2.5 km depending on the area). SQL keeps listings with `ST_DWithin(point::geography, centre::geography, radius_m)` — geography type, so the radius is in metres.

---

## 7. Amenities Enrichment

**Q: How do amenities work?**
> When a listing is created, `fetch_and_cache(listing_id)` calls the Google Places Nearby Search API for 5 categories (schools, hospitals, restaurants, transit, parks) within a 2km radius. Results are cached as JSON in the `amenities` column. The listing is then re-embedded so semantic search picks up amenity data.

**Q: Why cache amenities at write-time instead of fetching live?**
> **Hard rule from AGENTS.md:** Never call Google Places API during a chat or search request. Reasons: (1) API latency adds 1-2 seconds per category × 5 categories × multiple listings = unacceptable. (2) API quota is limited and expensive. (3) Amenities don't change frequently — caching once is sufficient.

**Q: What does the cached amenities JSON look like?**
> ```json
> {
>   "schools": [
>     {"name": "Sunrise Public School", "distance_m": 450, "rating": 4.3, "user_ratings_total": 127},
>     {"name": "DPS School", "distance_m": 800, "rating": 4.1, "user_ratings_total": 89}
>   ],
>   "hospitals": [...],
>   "restaurants": [...],
>   "transit": [...],
>   "parks": [...]
> }
> ```

**Q: How does re-embedding after amenities work?**
> After writing amenities to the DB, `fetch_and_cache()` calls `embed_single(listing_id)`. This re-runs `build_listing_text()`, which now includes an amenities paragraph like "Nearby amenities include 2 schools (highest rated: Sunrise Public School, 4.3 stars), 1 hospital...". The new embedding captures this, making queries like "flat near a good school" actually retrieve relevant results.

**Q: What if the API key is missing?**
> `fetch_and_cache()` logs an ERROR and writes nothing, so the `amenities` column stays NULL and the listing is fetched once the key is configured. The rest of the system works normally, just without amenity data.

**Q: How do you handle API rate limiting and failures?**
> Linear backoff: up to 3 tries per category with `2 × attempt` second delays. If a category still fails, nothing is cached for that listing, so a later run retries it instead of storing "no amenities". A genuine `ZERO_RESULTS` is cached as an empty list. `fetch_and_cache_all_missing()` adds a 0.2-second delay between listings during batch processing.

**Q: Can the API key leak into logs?**
> No. Error messages from `requests` contain the full request URL including `key=…`; every logged message is passed through `_redact()`, which replaces the key with `<redacted>`.

---

## 8. Database & Infrastructure

**Q: What database are you using?**
> PostgreSQL 16 with two extensions: **PostGIS** (spatial queries for locality radius and boundary search) and **pgvector** (vector similarity search). Docker-compose runs it on port 5433.

**Q: What does the listings table look like?**
> Locally, the AI track tests against a stand-in table:
> ```sql
> CREATE TABLE listings (
>     id            SERIAL PRIMARY KEY,
>     title         TEXT NOT NULL,
>     description   TEXT,
>     price         NUMERIC(12, 2),
>     property_type TEXT CHECK (property_type IN ('flat', 'house_land')),
>     bhk           INTEGER,
>     lat           DOUBLE PRECISION NOT NULL,
>     lng           DOUBLE PRECISION NOT NULL,
>     embedding     vector(384),
>     amenities     JSONB,
>     created_at    TIMESTAMPTZ DEFAULT NOW()
> );
> ```
> The backend's real `listing` table stores a PostGIS `location` point and the bedroom count inside a `rooms` JSON column; at merge the AI SQL is switched to that schema.

**Q: How do you connect to the database?**
> SQLAlchemy engine with connection pooling (`pool_size=5, max_overflow=10, pool_pre_ping=True`). The `DATABASE_URL` comes from `.env`. Each module creates its own engine at import time — the pool is reused across calls, not a new connection per query.

**Q: What is the test data?**
> 210 synthetic listings across 20 real Surat neighbourhoods (Adajan, Vesu, Citylight, Varachha, etc.) with tiered pricing (premium/mid/budget), ~75% flats and ~25% house/land, with a BHK count for each flat. Generated by `_test_seed.py` using the Faker library with real coordinates.

---

## 9. Code Architecture & Design Decisions

**Q: How is the AI code organised?**
> `ai/nlu/` — query understanding (rules, gazetteer, keyword vocabulary, schema validation, prompt, hybrid merge, evaluation). `ai/inference/` — model loading and the templated reply. `ai/rag/` — retrieval and boundary search. `ai/embeddings/` — embedding model and pipeline. `ai/amenities/` — Google Places caching. `ai/finetune/` — dataset generator, configs, training scripts. Each part can change without touching the others.

**Q: How do you handle errors throughout the codebase?**
> Custom exceptions at every boundary: `RetrievalError`, `BoundaryFilterError`, `ListingNotFoundError`, `EmbeddingModelLoadError`, `ModelUnavailableError`. Every external call (DB, API, model) is wrapped. `parse_query()` and `generate_response()` never raise: a model problem falls back to rules, a reply problem to a fallback sentence, so the chat endpoint does not crash.

**Q: Why a lazy singleton for model loading?**
> Loading the 4B model takes a while (it is read from disk and quantised onto the GPU). Loading it per request would make every message that slow. The singleton loads once on the first model request; `reload_model()` clears it after retraining.

**Q: Why are results cached per message?**
> `search()` and `generate_response()` both need the parsed query for the same message. An LRU cache (256 entries) keyed by backend and message means the model runs once per message instead of twice.

**Q: What environment variables does the project use?**
> | Variable | Purpose |
> |---|---|
> | `DATABASE_URL` | PostgreSQL connection string |
> | `GOOGLE_PLACES_API_KEY` | Google Places Nearby Search API |
> | `HF_TOKEN` | Hugging Face authentication (optional, for faster downloads) |
> | `NLU_BACKEND` | `hybrid` (default), `rules` (no GPU) or `model` (evaluation) |
> | `NLU_ALLOW_CPU_MODEL` | `1` to allow loading the model on CPU (slow; off by default) |

---

## 10. Live Demo Commands

**Start the database:**
```bash
docker-compose up -d
```

**Seed test data:**
```bash
python -m ai.embeddings._test_seed
```

**Embed all listings:**
```bash
python -m ai.embeddings.embed_listings
```

**Test the retriever:**
```bash
python -m ai.rag._test_retriever
```

**End-to-end pipeline with per-stage timings:**
```bash
python -m ai.inference._test_pipeline              # hybrid (model + rules)
python -m ai.inference._test_pipeline --backend rules
```

**Run the interactive chat demo:**
```bash
python -m ai.demo_chat
```

**Evaluate the parsers on the 150 hand-written queries:**
```bash
python -m ai.nlu.run_all_evals                     # rules, model and hybrid
python -m ai.nlu.run_all_evals --backends rules    # no GPU needed
```

**Cache amenities for all listings** (requires API key):
```bash
python -m ai.amenities.amenities_service
```

**Cache amenities for one listing:**
```bash
python -m ai.amenities.amenities_service 42
```

---

## 11. Tricky / Deep-Dive Questions

**Q: What happens if a listing has no embedding?**
> `retriever.search()` has `WHERE embedding IS NOT NULL` — unembedded listings are simply not returned. They become searchable once `embed_single()` or `run()` is called.

**Q: Can the system hallucinate properties?**
> No. The model only produces filters, which are validated against a fixed schema and the gazetteer; the reply is built from templates using only the listings the database returned. There is no free-text generation step that could invent a property, price or amenity.

**Q: What if the model's JSON is broken?**
> `validate_model_output()` rejects anything that isn't a complete object with correctly typed fields, and the rules parser's result is used instead. On the 150-query test set the model's output was valid 100% of the time.

**Q: Why is price never relaxed when nothing matches?**
> A budget is a hard limit — a customer with 50 lakh cannot buy a 90 lakh flat, and someone looking for a plot does not want a flat. The search loosens the area and the BHK first, and tells the customer it did; if still nothing fits, the reply says so.

**Q: What if two users ask the same question at the same time?**
> SQLAlchemy's connection pool handles concurrent DB queries. Model generation is serialised with a lock (one `generate()` at a time), because parallel generation on one small GPU only adds memory pressure. The model is loaded once, guarded by its own lock.

**Q: Why Euclidean distance (`<->`) and not cosine (`<=>`)?**
> Our embeddings are normalised to length 1, and for unit vectors the two give exactly the same ordering (L2² = 2 − 2·cos). So `<->` ranks by meaning just like cosine would.

**Q: How does conversation history work?**
> The `/chat` route passes `history` to `generate_response()`, but each message is currently understood on its own, so "something cheaper" does not inherit the previous filters. Merging filters from earlier turns is a planned optional extension (Part F of the playbook).

**Q: What's the difference between the debug adapter and the production adapter?**
> | | Debug | Production |
> |---|---|---|
> | Base model | Qwen3-1.7B | Qwen3-4B-Instruct-2507 |
> | Dataset | 200 examples | 3,000 examples |
> | GPU | RTX 3050 (4 GB) | Kaggle T4 (16 GB) |
> | LoRA rank | 8 | 16 |
> | Purpose | Validate the pipeline | Real deployment |
> | Location | `adapters/debug-qwen3/` | `adapters/qwen3-nlu-lora/` |

**Q: What are the limitations?**
> "around 70 lakh" is treated as a maximum; only one locality per message; no follow-up questions yet; places outside the gazetteer (e.g. Reliance Mall) aren't recognised until added; synthetic data; ~8 s per message on a 4 GB GPU.

**Q: What would you improve with more time?**
> 1. **Follow-up questions** — carry filters across turns
> 2. **Faster inference** — a quantised llama.cpp runtime instead of Hugging Face `generate()`
> 3. **Real data** instead of synthetic listings and queries, with native-speaker review of the Hinglish/Gujarati data
> 4. **Bigger gazetteer** and price ranges for "around X"
> 5. **HNSW index** once there are thousands of listings
> 6. **Shared DB engine** across all modules (single `ai/db.py`)
> 7. **Google Places API (New)** (newer, more features)

**Q: Why Surat and not any other city?**
> Project requirement — all synthetic data, coordinates, and landmarks are for Surat, Gujarat. The architecture is city-agnostic, but switching cities requires a new gazetteer, re-seeding listings with new coordinates, re-running amenities caching, and retraining the model on the new place names.
