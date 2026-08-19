# Reality AI — Shared Contract for AI Coding Assistants

**Read this before writing any code.** You are one of several AI coding assistants working on this project — each teammate is building their piece in a separate repository, with their own AI assistant (Antigravity, Vercel, or similar), without visibility into each other's code. This file is the one thing all three tracks share. Everything in it is **frozen** — if something here seems wrong, incomplete, or gets in your way, tell your human user and ask before deviating. Silently "improving," renaming, or restructuring anything in this file will break integration when the repos are merged into one at the end.

---

## 1. Project Overview

**Reality AI** is an AI-powered real estate exploration and publishing platform. Customers search properties through a conversational, retrieval-grounded chat assistant paired with an interactive split-screen map (including free-form boundary search and cached nearby-amenities data). Brokers publish and manage listings. Current phase uses synthetic data with real-world coordinates in an actual city.

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

**Backend:** implement these exact paths, methods, and field names — do not rename or restructure them, even if a different shape seems cleaner.
**Frontend:** call these exact paths and field names — do not invent alternate endpoints or guess at shapes.

## 4. The Database Schema (frozen)

| Table | Key fields |
|---|---|
| `listing` | `id`, `broker_id` (FK), `title`, `description`, `price`, `property_type` (enum: `flat` \| `house_land`), `location` (PostGIS `Geometry(Point, 4326)`), `carpet_area`, `built_up_area`, `plot_area`, `floor_number`, `rooms` (JSON), `embedding` (pgvector), `amenities` (JSON), `created_at` |
| `broker` | `id`, `name`, `email`, `phone_hash`, `password_hash`, `created_at` |
| `customer` | `id`, `name`, `email`, `created_at` |
| `conversation` | `id`, `customer_id` (FK), `messages` (JSON array of `{role, content, timestamp}`) |
| `lead` | `id`, `listing_id` (FK), `customer_id` (FK), `created_at` |

**Backend owns this schema and its migrations.** AI and Frontend tracks write code that *assumes* these exact table/column names — if you (AI or Frontend track) need a field that isn't listed here, flag it to your human rather than assuming it exists.

## 5. AI Module Interface (frozen — this is what Backend imports directly)

The backend's `/chat` route imports these as Python modules in the same process — no HTTP call between them. Function names and signatures must match exactly on both sides:

| Module | Function | Purpose |
|---|---|---|
| `ai.embeddings.embed_listings` | `run()` | Batch-embeds all un-embedded listings |
| `ai.rag.retriever` | `search(query, candidate_ids=None, top_k=5)` | Returns top-k relevant listings |
| `ai.rag.boundary_filter` | `get_candidates(polygon)` | Returns listing IDs inside a drawn polygon |
| `ai.amenities.amenities_service` | `fetch_and_cache(listing_id)` | Fetches nearby amenities from Google Places and caches them |
| `ai.inference` | `generate_response(query, listings, history)` | Produces the final chat reply text |

**AI track:** implement exactly these function names, argument names, and return shapes.
**Backend track:** call them exactly this way — don't rename on import or wrap them differently than documented.

## 6. Environment Variables (exact names, frozen)

| Variable | Used by |
|---|---|
| `DATABASE_URL` | Backend, AI |
| `SECRET_KEY` | Backend |
| `GOOGLE_PLACES_API_KEY` | AI |
| `VITE_API_BASE_URL` | Frontend |
| `VITE_GOOGLE_MAPS_API_KEY` | Frontend |
| `HF_TOKEN` (optional) | AI |

Never rename these, even if your framework's convention suggests a different name. Never commit real values — use `.env` files and keep `.env` in `.gitignore`.

## 7. Tech Stack (locked — do not substitute)

| Track | Stack |
|---|---|
| AI | Python 3.11+, PyTorch, PEFT + bitsandbytes, trl, sentence-transformers, pgvector, base model Llama 3 8B or Mistral 7B (Phi-3-mini for local debug), Kaggle Notebooks for the full fine-tune, Google Places API |
| Backend | Python 3.11+, FastAPI, SQLAlchemy + GeoAlchemy2, PostgreSQL + PostGIS, Alembic, python-jose + passlib, Faker |
| Frontend | React (Vite), Zustand, Google Maps JavaScript API + Drawing Library, Axios |

If your AI assistant suggests a different framework or library "for simplicity" (e.g. Flask instead of FastAPI, MongoDB instead of PostgreSQL, Vue instead of React) — don't take it, even if it would work. Consistency across repos matters more than any one repo's elegance.

---

## 8. Hard Rules

- Never call the Google Places API live during a chat or search request — amenities are cached once, at listing-creation time, in the `amenities` column.
- Never restructure your repo's top-level folder layout — it must drop cleanly into `ai/`, `backend/`, or `frontend/` at merge time with no renaming.
- Never invent a new endpoint, rename an existing one, or change a request/response shape without your human confirming it with the other two tracks first.
- Never rename a database field, table, or environment variable.
- Don't assume you have access to another track's running server or live database during development — build and test against the shapes documented above, not against a real integration.
- If something in this contract blocks you or seems wrong, stop and tell your human — don't quietly work around it.

## 9. Where to Find More

This file is the cross-team contract only. Full track-specific detail — file-by-file structure, week-by-week roadmap, risks, setup commands — lives in each person's individual roadmap document and the project README. This file should never contradict those; if it seems to, flag it.
