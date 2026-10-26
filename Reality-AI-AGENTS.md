# Reality AI — Shared Contract for AI Coding Assistants

**Read this before writing any code.** You are one of several AI coding assistants working on this project — each teammate is building their piece in a separate repository, with their own AI assistant (Antigravity, Vercel, or similar), without visibility into each other's code. This file is the one thing all three tracks share. Everything in it is **frozen** — if something here seems wrong, incomplete, or gets in your way, tell your human user and ask before deviating. Silently "improving," renaming, or restructuring anything in this file will break integration when the repos are merged into one at the end.

---

## 1. Project Overview

**Reality AI** is an AI-powered real estate exploration and publishing platform. Customers search properties through a conversational, retrieval-grounded chat assistant paired with an interactive split-screen map (including free-form boundary search and cached nearby-amenities data). Brokers publish and manage listings. Current phase uses synthetic data with real-world coordinates in **Surat, Gujarat** — this is the one city the whole project works with for now; do not substitute another city.

## 2. The Three Tracks

| Track | Owner(s) | Repo becomes this folder at merge |
|---|---|---|
| AI / RAG | Person 1 | `ai/` |
| Backend | Person 2 | `backend/` |
| Frontend | Persons 3 & 4 | `frontend/` |

Figure out which track your human is building (check their repo name or ask) and pay closest attention to that section — but the contract in Sections 3–7 applies no matter which track you're assisting.

**Why this matters:** at the end of development, all three repos get merged into one unified repo (via `git subtree`, preserving commit history) with each repo dropping into the folder named above. Your repo's root should already be organized as if it were that folder — don't add an extra wrapping folder, and don't use a different name.

---

## 3. The API Contract (frozen)

| Method | Path | Purpose | Called by | Implemented by |
|---|---|---|---|---|
| `POST` | `/auth/register` | Broker or customer signup | Frontend | Backend |
| `POST` | `/auth/login` | Login, returns a JWT | Frontend | Backend |
| `POST` | `/listings` | Broker publishes a listing; triggers embedding + amenities caching | Frontend | Backend |
| `GET` | `/listings/{id}` | Fetch one listing, including cached amenities | Frontend | Backend |
| `GET` | `/listings/search` | Radius / bounding-box search | Frontend | Backend |
| `POST` | `/listings/search-boundary` | Polygon (hand-drawn) boundary search | Frontend | Backend |
| `POST` | `/chat` | Customer chat message; orchestrates RAG + LLM | Frontend | Backend (calls AI modules) |
| `GET` | `/brokers/{id}/analytics` | Views and leads per listing | Frontend | Backend |

`/chat` request: `{ conversation_id, message, polygon? }` — response: `{ reply, listings }`.
`/listings/search-boundary` request: `{ polygon: [[lat, lng], ...] }`.

**Backend additions (2026-10-26, from the AI track's backend review — Frontend: confirm before coding against them):**

| Method | Path | Purpose | Who |
|---|---|---|---|
| `GET` | `/auth/me` | Current user's profile (`phone` included for brokers) | Any user |
| `GET` | `/chat/{conversation_id}` | Conversation history | Owning customer |
| `PATCH` | `/listings/{id}` | Edit a listing (partial; `lat` + `lng` together). Re-embeds on title/description/price/type change; `fetch_and_cache(id, force=True)` on location change | Owning broker |
| `PATCH` | `/listings/{id}/status` | `{status}` — `available` / `under_offer` / `sold` / `withdrawn` | Owning broker |
| `DELETE` | `/listings/{id}` | Soft delete: sets `withdrawn` (204) | Owning broker |
| `POST` | `/listings/{id}/images` | Multipart `file`, JPEG/PNG up to 5 MB; URL appended to `images`, served from `/uploads/...` | Owning broker |
| `POST` | `/listings/{id}/leads` | "Contact broker": `{message?, conversation_id?}`; one per customer and listing (409 on repeat or on sold/withdrawn); response includes `broker: {name, phone}` | Customer |
| `GET` | `/brokers/{id}/listings` | Broker's own listings, every status, with `view_count` and `lead_count`; `?status=&limit=&offset=` | That broker |
| `GET` | `/brokers/{id}/leads` | Leads inbox with listing title and customer name/email; `?status=&limit=&offset=` | That broker |
| `PATCH` | `/leads/{id}` | `{status}` — `new` / `contacted` / `visit_scheduled` / `closed` / `lost` | Broker owning the listing |

Shape details: `/chat` responses also carry `conversation_id`, and each listing in them adds `bhk`, `match_note` and `distance_score` from `search()`. Listing responses add `status`, `images` (`[{url, order}]`) and `updated_at`. `/brokers/{id}/analytics` adds `total_views` and per-listing `view_count` and `status`. `POST /auth/register` takes `name` and, for brokers, an optional `phone` (E.164); `POST /auth/login` is an OAuth2 form (`username` = email, `password`). Emails are case-insensitive and passwords are 8–72 bytes. Errors use FastAPI's `{detail}`; `/chat` returns 422 for bad input and 503 when AI search is unavailable.

**Search visibility:** `/listings/search`, `/listings/search-boundary` and `/chat` return only `available` and `under_offer` listings; `GET /listings/{id}` returns any status. Boundary search follows the AI rule: 3–1000 points, ring closed automatically, self-crossing polygons repaired (not rejected).

**Backend:** implement these exact paths, methods, and field names — do not rename or restructure them, even if a different shape seems cleaner.
**Frontend:** call these exact paths and field names — do not invent alternate endpoints or guess at shapes.

## 4. The Database Schema (frozen)

| Table | Key fields |
|---|---|
| `listing` | `id`, `broker_id` (FK), `title`, `description`, `price`, `property_type` (enum: `flat` \| `house_land`), `location` (PostGIS `Geometry(Point, 4326)`), `carpet_area`, `built_up_area`, `plot_area`, `floor_number`, `rooms` (JSON, see below), `embedding` (pgvector), `amenities` (JSON), `status` (enum: `available` \| `under_offer` \| `sold` \| `withdrawn`, default `available`), `images` (JSON `[{url, order}]`), `view_count` (int), `created_at`, `updated_at` |
| `broker` | `id`, `name`, `email`, `phone_hash`, `phone` (E.164, never public), `password_hash`, `created_at` |
| `customer` | `id`, `name`, `email`, `password_hash`, `created_at` |
| `conversation` | `id`, `customer_id` (FK), `messages` (JSON array of `{role, content, timestamp}`; assistant messages also store `listing_ids`), `created_at`, `updated_at` |
| `lead` | `id`, `listing_id` (FK), `customer_id` (FK), `message`, `status` (enum: `new` \| `contacted` \| `visit_scheduled` \| `closed` \| `lost`), `conversation_id` (FK, nullable), `created_at`, `updated_at` — unique (`listing_id`, `customer_id`) |

**Backend owns this schema and its migrations.** AI and Frontend tracks write code that *assumes* these exact table/column names — if you (AI or Frontend track) need a field that isn't listed here, flag it to your human rather than assuming it exists.

**Agreed 2026-10-26 (Backend, answering "Reality AI — Database Schema Recommendations for Person 2"):**
- **`rooms`** is `{"bedrooms": int 1–10, "bathrooms"?, "balconies"?, "hall"?, "kitchen"?, "garden"?}` — unknown keys are rejected. `bedrooms` is required for flats; open plots store `rooms` as SQL `NULL`. A database check keeps `bedrooms` a whole number, and an index serves `(rooms->>'bedrooms')::int`.
- **`status`**: customer search (radius, boundary, chat) shows only `available` and `under_offer` — AI track: add `status IN ('available', 'under_offer')` to `search()` and `get_candidates()`. Listings are never hard-deleted.
- **`updated_at`** changes on every edit; edits re-embed as described in Section 5.
- **`amenities`** is written only by `ai.amenities.amenities_service`; the backend never writes it and no request schema accepts it. `NULL` means "not fetched yet".
- **`phone`** (R5, option A) is returned only to the broker (`/auth/me`) and to a customer in the response to creating a lead.
- **Leads** are created only by an explicit customer action (`POST /listings/{id}/leads`), never by chat search; being shown in `/chat` or opened via `GET /listings/{id}` adds to `view_count` instead.
- **Database driver:** the merged `requirements.txt` includes both psycopg 3 (backend) and `psycopg2-binary` (AI engines); the AI track needs no change.
- **Not yet:** an HNSW index on `embedding` (R8, only beyond a few thousand listings) and a `features` column for building facilities (R4, needs names agreed with the AI track).

## 5. AI Module Interface (frozen — this is what Backend imports directly)

The backend's `/chat` route imports these as Python modules in the same process — no HTTP call between them. Function names and signatures must match exactly on both sides:

| Module | Function | Purpose |
|---|---|---|
| `ai.embeddings.embed_listings` | `run()` | Batch-embeds all un-embedded listings (initial pass over freshly-seeded data) |
| `ai.embeddings.embed_listings` | `embed_single(listing_id)` | Embeds/re-embeds one listing — called after creation, again after amenities are cached, and after `PATCH /listings/{id}` changes the title, description, price or property type |
| `ai.rag.retriever` | `search(query, candidate_ids=None, top_k=5)` | Returns top-k relevant listings |
| `ai.rag.boundary_filter` | `get_candidates(polygon)` | Returns listing IDs inside a drawn polygon |
| `ai.amenities.amenities_service` | `fetch_and_cache(listing_id, force=False)` | Fetches nearby amenities (with ratings) from Google Places, caches them, and re-embeds the listing. `force` is optional: leave it out normally; pass `force=True` to refresh after a listing's location changes (otherwise already-cached amenities are kept) |
| `ai.inference` | `generate_response(query, listings, history)` | Produces the final chat reply text |

**AI track:** implement exactly these function names, argument names, and return shapes.
**Backend track:** call them exactly this way — don't rename on import or wrap them differently than documented. Call `embed_single(listing.id)` after creating a listing, not `run()` — `run()` is for the initial batch pass only.

**Qwen3 migration notes (AI track, all signatures above unchanged):**
- `retriever.search()` results carry two extra keys: `match_note` — `"exact"`, `"relaxed_radius"`, `"relaxed_bhk"` or `"relaxed_locality"` (how far the search had to be widened to find anything; show it or ignore it) — and `bhk` (bedroom count or `null`).
- Off-topic messages (greetings, weather, coding, instruction-override attempts, …) make `search()` return `[]`; `generate_response()` then returns a polite redirect.
- `generate_response()` no longer uses a language model: the reply is built from templates around the listings passed in, so it is deterministic and can only mention those listings.
- Query understanding returns prices as `{amount, unit}` (`unit` is `lakh`, `crore` or `rupee`), exactly as the user wrote them; code converts to rupees.
- Call order in `/chat`: `search()` first (with a GPU, ~8 s per message for query understanding; without one, rules mode takes milliseconds), send the listings to the frontend if you want the map to update early, then `generate_response()` (under 1 ms — it reuses the cached parse).

**Errors and input limits (Backend: handle these):**

| Function | Raises | Notes |
|---|---|---|
| `search()` | `ValueError` — empty `query`, `top_k` not a positive integer, or a non-integer in `candidate_ids`; `RetrievalError` — embedding the query or the database query failed | `candidate_ids=[]` returns `[]` without a query (the drawn boundary matched nothing). `top_k` above 50 is clamped. Messages are cut to 500 characters before parsing and embedding. |
| `get_candidates()` | `ValueError` — fewer than 3 points, more than 1000 points, or a point that is non-numeric, NaN/infinite, or outside lat −90..90 / lng −180..180; `BoundaryFilterError` — database failure | Points are `[lat, lng]` (check the order: a swapped pair usually fails the range check). An unclosed ring is closed automatically; a self-crossing polygon is repaired, not rejected. |
| `fetch_and_cache()` | `ListingNotFoundError` only | Every other failure is logged, not raised, so it is safe in a background task. If `GOOGLE_PLACES_API_KEY` is missing or any Google request fails, nothing is written and the listing is retried on the next run. |
| `embed_single()` | `ListingNotFoundError`; `ValueError` if the listing has no text to embed; SQLAlchemy errors on a failed write | Run it in a background task after create/update. |
| `generate_response()` | never | Returns a short fallback sentence on any internal error. |

**Amenities cache shape:** each category (`schools`, `hospitals`, `restaurants`, `transit`, `parks`) is a list of `{name, distance_m, rating, user_ratings_total}`. `rating` and `user_ratings_total` come straight from the Google Places response and may be `null`/`0` — not every place has one, handle that everywhere this data is read or displayed.

## 6. Environment Variables (exact names, frozen)

| Variable | Used by |
|---|---|
| `DATABASE_URL` | Backend, AI |
| `SECRET_KEY` | Backend |
| `GOOGLE_PLACES_API_KEY` | AI |
| `VITE_API_BASE_URL` | Frontend |
| `VITE_GOOGLE_MAPS_API_KEY` | Frontend |
| `HF_TOKEN` (optional) | AI |
| `NLU_BACKEND` (optional: `hybrid` \| `rules` \| `model`, default `hybrid`) | AI |
| `NLU_ALLOW_CPU_MODEL` (optional, default off; `1` allows loading the NLU model on CPU) | AI |
| `PLACEHOLDER_MODE` (optional, default `true`; set `false` once the `ai/` package is merged) | Backend |
| `CORS_ORIGINS` (optional, comma-separated, default `http://localhost:5173`) | Backend |
| `UPLOAD_DIR` (optional, default `uploads`) | Backend |

Never rename these, even if your framework's convention suggests a different name. Never commit real values — use `.env` files and keep `.env` in `.gitignore`.

## 7. Tech Stack (locked — do not substitute)

| Track | Stack |
|---|---|
| AI | Python 3.11+, PyTorch, PEFT + bitsandbytes, trl, sentence-transformers, pgvector, base model Qwen/Qwen3-4B-Instruct-2507 with a LoRA adapter used for query understanding (Qwen/Qwen3-1.7B for local debug), Kaggle Notebooks for the full fine-tune, Google Places API |
| Backend | Python 3.11+, FastAPI, SQLAlchemy + GeoAlchemy2, PostgreSQL + PostGIS, Alembic, python-jose + passlib, Faker |
| Frontend | React (Vite), Zustand, Google Maps JavaScript API + Drawing Library, Axios |

If your AI assistant suggests a different framework or library "for simplicity" (e.g. Flask instead of FastAPI, MongoDB instead of PostgreSQL, Vue instead of React) — don't take it, even if it would work. Consistency across repos matters more than any one repo's elegance.

---

## 8. Hard Rules

- Never call the Google Places API live during a chat or search request — amenities are cached once, at listing-creation time, in the `amenities` column.
- Whenever amenities data is written for a listing, that listing must be re-embedded (`embed_single`) so amenities and ratings actually affect search results, not just chat replies.
- Never restructure your repo's top-level folder layout — it must drop cleanly into `ai/`, `backend/`, or `frontend/` at merge time with no renaming.
- Never invent a new endpoint, rename an existing one, or change a request/response shape without your human confirming it with the other two tracks first.
- Never rename a database field, table, or environment variable.
- Don't assume you have access to another track's running server or live database during development — build and test against the shapes documented above, not against a real integration.
- The language model never computes rupee amounts or invents listings; price conversion is done by code.
- If no GPU or adapter is present the AI package must fall back to rules, never crash.
- Render the chat reply (and any listing title or description) as plain text, never as HTML: titles and descriptions are written by brokers, so inserting them as HTML would allow script injection (XSS).
- Never log or return the Google Places API key; the AI track redacts it from its own logs.
- If something in this contract blocks you or seems wrong, stop and tell your human — don't quietly work around it.

## 9. Where to Find More

This file is the cross-team contract only. Full track-specific detail — file-by-file structure, week-by-week roadmap, risks, setup commands — lives in each person's individual roadmap document and the project README. This file should never contradict those; if it seems to, flag it.