# Reality AI — Practical Evaluation Q&A Cheat Sheet

> **Your project:** AI-powered real estate chat assistant for Surat, Gujarat using RAG (Retrieval-Augmented Generation) with a fine-tuned Mistral-7B model, semantic search via pgvector, boundary-aware filtering via PostGIS, and cached amenities from Google Places API.

---

## 1. Project Architecture & Overview

**Q: What is Reality AI?**
> It's an AI-powered real estate platform where customers search properties through a conversational chat assistant. The assistant retrieves relevant listings using semantic search (RAG), then generates grounded responses using a fine-tuned LLM. It supports boundary-based search (draw on map), cached nearby amenities, and multi-turn conversations.

**Q: Explain the overall architecture.**
> Three tracks: **AI/RAG** (my track — embeddings, retrieval, fine-tuning, inference), **Backend** (FastAPI, PostgreSQL, REST API), and **Frontend** (React, Google Maps). The backend imports my AI modules directly as Python packages — no HTTP between AI and Backend. The frontend talks to the backend via REST APIs.

**Q: What is RAG and why did you use it?**
> RAG = Retrieval-Augmented Generation. Instead of relying solely on the LLM's training data (which doesn't know our listings), we first **retrieve** relevant listings from the database using semantic search, then **augment** the model's prompt with those listings, and let the model **generate** a grounded response. This prevents hallucination — the model can only describe properties that actually exist in our database.

**Q: Why not just use ChatGPT/GPT-4 API directly?**
> Three reasons: (1) **Cost** — API calls at scale are expensive; a self-hosted model is free after training. (2) **Control** — we fine-tuned the model to behave as a real estate assistant with specific guardrails. (3) **Data privacy** — listing data stays local, never sent to a third-party API. (4) **Latency** — local inference avoids network round-trips.

**Q: How do the three tracks integrate?**
> The backend imports AI modules directly in the same Python process:
> - `ai.rag.retriever.search()` — semantic search
> - `ai.rag.boundary_filter.get_candidates()` — polygon search
> - `ai.inference.generate_response()` — chat reply
> - `ai.embeddings.embed_listings.embed_single()` — embed new listings
> - `ai.amenities.amenities_service.fetch_and_cache()` — cache nearby POIs
>
> These function signatures are frozen in `AGENTS.md` — the shared contract between all three tracks.

---

## 2. Embeddings & Semantic Search

**Q: What embedding model did you use and why?**
> `all-MiniLM-L6-v2` from sentence-transformers. It produces 384-dimensional vectors, runs fast on both CPU and GPU, and is well-suited for semantic similarity. It's small (~80 MB) so it loads instantly, unlike large embedding models.

**Q: How does the embedding pipeline work?**
> 1. `build_listing_text()` combines title, description, price, property type, and amenities into a natural-language paragraph
> 2. `EmbeddingModel.embed()` converts that text into a 384-dim normalized vector
> 3. The vector is stored in the `embedding` column (pgvector `vector(384)`) in PostgreSQL
> 4. At query time, the user's query is embedded with the same model, and pgvector finds the nearest listings by cosine distance

**Q: Why do you normalize embeddings?**
> We use `normalize_embeddings=True` so that cosine similarity equals the dot product. This makes pgvector's `<=>` cosine-distance operator work correctly and consistently.

**Q: What is pgvector?**
> A PostgreSQL extension that adds vector data types and similarity search operators. We store 384-dimensional float vectors alongside regular columns (title, price, etc.) and query them with `<->` (cosine distance) to find semantically similar listings.

**Q: What index do you use for vector search?**
> IVFFlat (Inverted File with Flat compression) with `lists = 10`. At our scale (~200-1000 listings), this provides good recall without the complexity of HNSW. The index is created in `db/init.sql`:
> ```sql
> CREATE INDEX listings_embedding_idx ON listings
>     USING ivfflat (embedding vector_cosine_ops) WITH (lists = 10);
> ```

**Q: How does `retriever.search()` work step by step?**
> 1. Validate query (non-empty string) and top_k (positive integer, max 50)
> 2. If `candidate_ids` is an empty list → return `[]` immediately (boundary matched nothing)
> 3. Embed the query using `EmbeddingModel.embed()`
> 4. Run a SQL query ordering by `embedding <-> :query_vector` (cosine distance)
> 5. If `candidate_ids` is provided, add `AND id = ANY(:candidate_ids)` to restrict results
> 6. Return a list of dicts with id, title, description, price, property_type, lat, lng, amenities, distance_score

**Q: What is `distance_score` in the results?**
> It's the raw pgvector cosine distance — a float between 0 and 2. Lower = more similar. 0 means identical, 2 means completely opposite. Values under 0.5 are typically strong matches.

**Q: Why not use a vector database like Pinecone or Weaviate?**
> PostgreSQL with pgvector keeps everything in one database — vectors, listing data, PostGIS geometry. No need for a separate service, no data sync issues, simpler deployment. At our scale (<1000 listings), pgvector is more than fast enough.

---

## 3. Fine-Tuning

**Q: What base model did you use?**
> `mistralai/Mistral-7B-v0.1`. It's a 7-billion parameter model with a permissive Apache 2.0 license, strong instruction-following capability, and excellent PEFT/LoRA tooling support.

**Q: What is LoRA and why did you use it?**
> LoRA (Low-Rank Adaptation) freezes the original model weights and adds small trainable adapter matrices to attention layers. Instead of fine-tuning all 7 billion parameters (which would require >100 GB VRAM), LoRA trains only ~0.1-0.5% of parameters. This makes fine-tuning possible on a free Kaggle T4 GPU (16 GB VRAM).

**Q: What are the LoRA hyperparameters and why?**
> - **r = 16** (rank) — doubles capacity vs debug config (r=8); enough to learn domain patterns without overfitting
> - **lora_alpha = 32** — standard 2× rank convention; keeps effective scaling consistent with the debug config
> - **lora_dropout = 0.05** — light regularization; lower than debug (0.1) because 750 examples provide more signal
> - **target_modules = [q_proj, k_proj, v_proj, o_proj]** — all four attention projections in Mistral's architecture
> - **task_type = CAUSAL_LM** — autoregressive language modeling

**Q: What is 4-bit quantization?**
> We use `BitsAndBytesConfig` with NF4 (Normal Float 4-bit) quantization. Each weight is stored as 4 bits instead of 16/32 bits, reducing memory by ~4×. Double quantization (`bnb_4bit_use_double_quant=True`) quantizes the quantization constants too, saving another ~0.4 GB. This lets Mistral-7B fit in ~5 GB VRAM.

**Q: How did you create the training dataset?**
> `prepare_dataset.py` generates synthetic conversations using 8-10 template categories: price queries, location queries, amenity questions, comparisons, narrowing searches, off-topic redirects, and multi-turn conversations. Each template is filled with randomized but realistic Surat property data. The full dataset has 750 examples with dedup checks.

**Q: What format is the training data in?**
> JSONL format with chat-template structure:
> ```json
> {"messages": [
>   {"role": "system", "content": "You are a real estate assistant..."},
>   {"role": "user", "content": "What 2BHK flats do you have under 50 lakhs?"},
>   {"role": "assistant", "content": "I found a couple of options..."}
> ]}
> ```

**Q: Why did you use a debug model (Phi-3-mini) locally?**
> My local GPU (RTX 3050) has only 4 GB VRAM — not enough for Mistral-7B even in 4-bit. Phi-3-mini (~3.8B params) fits in 4 GB and proves the full training pipeline works end-to-end (dataset loading, tokenization, LoRA application, SFTTrainer) before spending Kaggle GPU hours on the real model.

**Q: Where did the actual training happen?**
> On Kaggle using a free Tesla T4 GPU (16 GB VRAM). The notebook (`train_lora_kaggle.ipynb`) runs the full 750-example training with Mistral-7B. The trained adapter (~52 MB) is downloaded as a zip and placed locally at `ai/finetune/adapters/reality-ai-lora/`.

**Q: What is SFTTrainer?**
> Supervised Fine-Tuning Trainer from the `trl` library. It handles chat-template tokenization, padding, and the training loop. We configure it with gradient checkpointing, paged AdamW 8-bit optimizer, and gradient accumulation to maximize what fits in VRAM.

**Q: What training arguments did you use?**
> - 3 epochs, learning rate 2e-4, warmup ratio 0.05
> - Batch size 2 × gradient accumulation 4 = effective batch size 8
> - Max sequence length 2048 tokens
> - FP16 precision (T4 doesn't support BF16)
> - Gradient checkpointing enabled (trades compute for memory)
> - Paged AdamW 8-bit optimizer (saves ~30% optimizer memory)

---

## 4. Inference Pipeline

**Q: How does the model get loaded for inference?**
> `load_model.py` implements a lazy singleton pattern:
> 1. First `get_model()` call loads the tokenizer, base model in 4-bit, attaches the LoRA adapter, calls `model.eval()`
> 2. Caches the `(model, tokenizer)` tuple in a module-level variable
> 3. Subsequent calls return the cache instantly (DEBUG log)
> 4. `reload_model()` clears the cache for hot-swapping adapters during development

**Q: What if the adapter isn't there?**
> Raises `AdapterNotFoundError` (subclass of `FileNotFoundError`) with a clear message explaining to run the Kaggle training first and where to unzip the adapter.

**Q: How does `generate_response()` work?**
> 1. Gets `(model, tokenizer)` from the singleton
> 2. Calls `build_prompt()` to assemble system prompt + listings + history + query
> 3. Applies the tokenizer's chat template and tokenizes
> 4. Calls `model.generate()` with: `max_new_tokens=300`, `temperature=0.7`, `top_p=0.9`, `repetition_penalty=1.15`, `do_sample=True`
> 5. Decodes only the newly generated tokens (strips the echoed prompt)
> 6. On any failure, returns a graceful fallback string rather than crashing

**Q: Why `temperature=0.7` and not 0 or 1?**
> 0 = deterministic (robotic, repetitive). 1 = highly random (may hallucinate). 0.7 gives natural-sounding but grounded responses — conversational without inventing facts.

**Q: What is `repetition_penalty=1.15`?**
> Discourages the model from repeating the same phrases. Without it, the model might list the same property features over and over. 1.15 is mild enough to not distort the output.

---

## 5. Prompt Engineering

**Q: What does the system prompt contain?**
> Five explicit rules:
> 1. Only use listing info from context — never invent details
> 2. Say honestly if no listings match
> 3. Only mention amenities when the customer asks
> 4. Politely decline off-topic questions and redirect to property search
> 5. Keep responses conversational, not raw data dumps

**Q: How is the prompt structured?**
> ```
> [System] The system prompt with rules
> [User]   Conversation so far: (truncated history)
>          Available properties: (formatted listings)
>          Customer's question: (the actual query)
> ```
> This is passed through `tokenizer.apply_chat_template()` to match Mistral's expected format.

**Q: How do you handle token budget overflow?**
> `build_prompt()` checks if the combined context exceeds ~12,000 characters (~3000 tokens). If so, it first trims listings from 5 to 3 (keeping the most relevant). If still too long, it trims history from 6 turns to 2. Listings are prioritized over history because they carry more answer-signal.

**Q: How does the amenity-aware prompting work?**
> `is_amenity_related(query)` checks the query against ~30 keywords (school, hospital, nearby, walking distance, etc.). If True, `format_listing_context()` includes amenity data in each listing's block (e.g., "Nearby: Schools: Sunrise Public School · 4.3★ · 450m"). If False, amenities are omitted to keep the context focused.

---

## 6. Boundary-Aware Search

**Q: What is boundary search?**
> Users can draw a polygon on the map (Google Maps Drawing Library) to define a search area. `boundary_filter.get_candidates(polygon)` runs a PostGIS query to find listings inside that polygon, returning their IDs. These IDs are then passed to `retriever.search(candidate_ids=...)` to restrict semantic search to only those listings.

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
> Two-stage: (1) `get_candidates(polygon)` → list of IDs inside the drawn area. (2) `search(query, candidate_ids=ids)` → semantic search restricted to those IDs. If the polygon matches zero listings, `candidate_ids=[]` returns empty immediately without querying.

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
> `_fetch_category()` logs an ERROR and returns `[]` for every category. The listing gets empty amenities but doesn't crash. The whole system still works — just without amenity data.

**Q: How do you handle API rate limiting?**
> Exponential backoff: up to 3 retries with `2 × attempt` second delays. If still failing, the category is treated as empty. `fetch_and_cache_all_missing()` adds a 0.2-second delay between listings during batch processing.

---

## 8. Database & Infrastructure

**Q: What database are you using?**
> PostgreSQL 16 with two extensions: **PostGIS** (geometry/spatial queries for boundary search) and **pgvector** (vector similarity search for embeddings). Docker-compose runs it on port 5433.

**Q: What does the listings table look like?**
> ```sql
> CREATE TABLE listings (
>     id           SERIAL PRIMARY KEY,
>     title        TEXT NOT NULL,
>     description  TEXT,
>     price        NUMERIC(12, 2),
>     property_type TEXT CHECK (property_type IN ('flat', 'house_land')),
>     lat          DOUBLE PRECISION NOT NULL,
>     lng          DOUBLE PRECISION NOT NULL,
>     embedding    vector(384),
>     amenities    JSONB,
>     created_at   TIMESTAMPTZ DEFAULT NOW()
> );
> ```

**Q: How do you connect to the database?**
> SQLAlchemy engine with connection pooling (`pool_size=5, max_overflow=10, pool_pre_ping=True`). The `DATABASE_URL` comes from `.env`. Each module creates its own engine at import time — the pool is reused across calls, not a new connection per query.

**Q: What is the test data?**
> 210 synthetic listings across 20 real Surat neighbourhoods (Adajan, Vesu, Citylight, Varachha, etc.) with tiered pricing (premium/mid/budget). ~75% flats, ~25% house/land. Generated by `_test_seed.py` using the Faker library with real coordinates.

---

## 9. Code Architecture & Design Decisions

**Q: Why is everything in separate modules instead of one big file?**
> Separation of concerns: `embedding_model.py` (embedding), `retriever.py` (search), `prompt_templates.py` (prompt assembly), `generate_response.py` (inference), `load_model.py` (model loading), `boundary_filter.py` (spatial queries), `amenities_service.py` (API calls). Each can be iterated independently. The prompt design can change without touching model loading code.

**Q: How do you handle errors throughout the codebase?**
> Custom exceptions at every boundary: `RetrievalError`, `ListingNotFoundError`, `AdapterNotFoundError`, `EmbeddingModelLoadError`, `BoundaryFilterError`. Every external call (DB, API, model) is wrapped in try/except. `generate_response()` never raises — returns a fallback string on any failure, so the chat endpoint never crashes.

**Q: Why lazy singleton for model loading?**
> Loading Mistral-7B takes ~30 seconds. If we loaded it per request, every chat message would take 30+ seconds. The singleton loads once and caches, so only the first request is slow. `reload_model()` allows hot-swapping the adapter without restarting the process.

**Q: What environment variables does the project use?**
> | Variable | Purpose |
> |---|---|
> | `DATABASE_URL` | PostgreSQL connection string |
> | `GOOGLE_PLACES_API_KEY` | Google Places Nearby Search API |
> | `HF_TOKEN` | Hugging Face authentication (optional, for faster downloads) |

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

**Test the retriever (12 queries):**
```bash
python -m ai.rag._test_retriever
```

**Run the interactive chat demo:**
```bash
python -m ai.demo_chat
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

**Q: Can the model hallucinate properties?**
> The system prompt explicitly forbids it: "Never invent a price, location, feature, or amenity that isn't explicitly present in the provided listings." Fine-tuning reinforces this through negative examples (off-topic redirects). However, LLMs can still occasionally hallucinate — that's why the system prompt is the primary guardrail, and Phase 5 evaluation tests for this.

**Q: What if two users ask the same question at the same time?**
> The model singleton is shared but `model.generate()` with `torch.no_grad()` is thread-safe for inference. SQLAlchemy's connection pool handles concurrent DB queries. Each request gets its own prompt and listings — no cross-contamination.

**Q: Why did you use cosine distance instead of L2 distance?**
> Cosine distance measures the angle between vectors, ignoring magnitude. Two listing descriptions of different lengths but similar meaning will have high cosine similarity. L2 distance is affected by vector magnitude, which isn't meaningful for semantic similarity. Our embeddings are L2-normalized, so cosine distance = 1 - dot product.

**Q: How does conversation history work?**
> The frontend sends `history` (list of `{role, content}` dicts) with each `/chat` request. `format_history()` takes the most recent 6 turns, formats as "Customer: ... / Assistant: ...", and includes them in the prompt. Older turns are dropped to fit the context window.

**Q: What's the difference between the debug adapter and the production adapter?**
> | | Debug | Production |
> |---|---|---|
> | Base model | Phi-3-mini (3.8B) | Mistral-7B |
> | Dataset | 100 examples | 750 examples |
> | GPU | RTX 3050 (4 GB) | Kaggle T4 (16 GB) |
> | LoRA rank | 8 | 16 |
> | Purpose | Validate pipeline | Real deployment |
> | Location | `adapters/debug-run/` | `adapters/reality-ai-lora/` |

**Q: What would you improve with more time?**
> 1. **HNSW index** instead of IVFFlat for better recall at scale
> 2. **Real training data** instead of synthetic — scrape actual property listings
> 3. **Streaming responses** for better UX (token-by-token display)
> 4. **Evaluation framework** with automated metrics (BLEU, relevance scoring)
> 5. **GPU server** for production deployment (not CPU offloading)
> 6. **Shared DB engine** across all modules (single `ai/db.py`)
> 7. **Google Places API v2** (newer, more features)

**Q: Why Surat and not any other city?**
> Project requirement — all synthetic data, coordinates, and landmarks are for Surat, Gujarat. The architecture is city-agnostic, but switching cities requires re-seeding listings with new coordinates and re-running amenities caching.
