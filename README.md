# Hybrid RAG Retrieval Backend

A Retrieval-Augmented Generation system built around one idea: **fuse lexical and semantic retrieval properly, run entirely locally, and keep the pipeline simple enough to actually finish, test, and reason about end to end.**

## 🎯 Why this architecture

Earlier iterations of this project targeted a fully decoupled, queue-driven, multi-service architecture (async ingestion workers, swappable external embedding APIs, CI-gated eval regression). That scope was deliberately cut back — not because those ideas are wrong, but because a synchronous, single-process backend gets to a genuinely working, explainable, *tested* system faster, without carrying infrastructure that isn't earning its keep yet. Three decisions drive the current design:

1. **Hybrid retrieval, fused correctly.** BM25 (lexical) and pgvector ANN (semantic) search each surface results a single method would miss. They're combined via **Reciprocal Rank Fusion (RRF)** — rank-based, not a weighted sum of raw scores, since BM25 scores and cosine similarity live on incomparable scales.
2. **Runs entirely locally.** Embeddings via `sentence-transformers`, generation via Ollama — no external API keys required to run this end to end.
3. **Structure-aware ingestion.** The chunker treats code blocks and tables as atomic units rather than splitting them mid-block, which naive fixed-size chunking does by default.

## 🏗️ Architecture

```
                Frontend (React, terminal-style console)
                              │
                    POST /query, POST /ingest
                              │
                     ┌────────▼────────┐
                     │   FastAPI app    │
                     │  (single process)│
                     └───┬──────────┬──┘
                          │          │
                  POST /ingest   POST /query
                  (sync)          │
                     │            ├──────────────┬──────────────┐
             loader → chunker     │              │              │
                     │       BM25 index      pgvector ANN   Ollama
                     │       (in-memory,      (HNSW index,  (local
                     │       rank_bm25)       cosine dist)  generation)
                     │            │              │
                     │            └──── RRF ─────┘
                     │                  │
              PostgreSQL          fused chunk ranking
           (Document, Chunk +          │
            embedding column)     answer + citations
```

No queue, no worker process. Every request is a normal synchronous FastAPI call. That's a real tradeoff (ingesting a document blocks the request until it's done), which is explicitly fine for a single-user, portfolio-scale corpus.

## 🛠️ Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Frontend | React + TypeScript + Vite | Minimal terminal/console-style query UI |
| API | FastAPI (Python) | Async-native, auto OpenAPI docs at `/docs` |
| Vector DB | PostgreSQL + pgvector (HNSW index) | Real SQL + ANN vector search in one database |
| Lexical search | `rank_bm25` (BM25Okapi) | In-memory, no extra service to run |
| Fusion | Reciprocal Rank Fusion | Rank-based combination avoids mixing incomparable BM25/cosine score scales |
| Embeddings | `sentence-transformers` (`all-MiniLM-L6-v2`) | Local, no API key, 384-dim |
| LLM | Ollama (local, e.g. `llama3.2:3b`) | No external API dependency or per-token cost |
| Chunking | Custom recursive, structure-aware | Keeps code blocks/tables atomic instead of splitting them |

## 💻 Frontend

A minimal, terminal/console-style single page — deliberately not a chat-bubble UI. Queries and answers stack as a running transcript, and each answer's cited sources are numbered `[Source 1]`, `[Source 2]`... which is not just a UI convention: it mirrors the exact numbering `generation.py` already uses internally when building the prompt sent to the LLM. The citation you click on screen is the same structure the model reasoned over — not a UI abstraction layered on top after the fact.

Markdown in generated answers (code blocks, lists) renders via `react-markdown`, since Ollama's responses frequently include real formatting (e.g. SQL snippets in fenced code blocks) that plain text rendering would show as literal backticks.

Read-only by design for now — query only, no ingestion UI. Sources are clickable/expandable to show the full retrieved chunk text and a link back to the original document.

## 📂 Repository Structure

```
rag-system/
├── frontend/
│   ├── src/
│   │   ├── App.tsx                  # Terminal-console UI, query transcript
│   │   ├── api/client.ts            # Fetch wrapper for POST /query
│   │   ├── types.ts                 # Mirrors backend Pydantic schemas
│   │   └── index.css                # Design tokens (color/type system)
│   └── package.json
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI entrypoint, startup hook rebuilds BM25 index
│   │   ├── config.py                # Env-driven settings (pydantic-settings)
│   │   ├── api/
│   │   │   ├── routes_query.py      # POST /query
│   │   │   └── routes_ingest.py     # POST /ingest
│   │   ├── core/
│   │   │   ├── chunking.py          # Structure-aware recursive chunker
│   │   │   ├── embeddings.py        # sentence-transformers wrapper
│   │   │   ├── lexical_index.py     # In-memory BM25 index
│   │   │   ├── retrieval.py         # RRF fusion of BM25 + ANN
│   │   │   └── generation.py        # Ollama call + grounded prompt
│   │   ├── db/
│   │   │   ├── models.py            # Document, Chunk (pgvector column, HNSW index)
│   │   │   ├── session.py
│   │   │   └── vector_store.py      # pgvector cosine ANN search
│   │   ├── ingestion/
│   │   │   ├── loader.py            # HTML → clean text + segment tagging
│   │   │   └── pipeline.py          # loader → chunker → embedder → DB → BM25 rebuild
│   │   └── schemas/
│   │       └── model.py             # Pydantic request/response models
│   ├── eval/
│   │   ├── run_eval.py
│   │   ├── metrics.py               # hit@k, precision@k, recall@k, MRR, refusal detection
│   │   └── eval_dataset.jsonl
│   ├── tests/
│   │   └── test_retrieval.py        # Integration tests against real Postgres + BM25
│   ├── scripts/
│   │   ├── init_db.py
│   │   └── smoke_test_ingest.py
│   └── requirements.txt
├── docker-compose.yml                 # Postgres+pgvector
└── README.md
```

## 🚀 Getting Started

### Prerequisites

- Python 3.10+, Node.js 18+
- Docker (for Postgres/pgvector)
- [Ollama](https://ollama.com/download) — installed and running locally

### Backend setup

```bash
git clone https://github.com/breaseabrol/rag-system.git
cd rag-system

# 1. Start Postgres + pgvector
docker-compose up -d

# 2. Enable the pgvector extension (one-time, per fresh volume)
docker-compose exec postgres-db psql -U raguser -d ragdb -c "CREATE EXTENSION IF NOT EXISTS vector;"

# 3. Install Python dependencies
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1        # Windows PowerShell
# source .venv/bin/activate       # macOS/Linux
pip install -r requirements.txt

# 4. Create tables
python scripts/init_db.py

# 5. Pull a local model
ollama pull llama3.2:3b
# (update OLLAMA_MODEL in .env or config.py if you use a different model)

# 6. Run the API
uvicorn app.main:app --reload
```

### Frontend setup

```bash
cd frontend
npm install
npm run dev
```
Opens at `http://localhost:5173`. Requires `CORSMiddleware` enabled in `main.py` for that origin.

> ⚠️ **GPU users:** if Ollama crashes with a CUDA initialization error, force CPU mode: stop any running Ollama process, then `$env:OLLAMA_NO_GPU="1"; ollama serve` before retrying. CPU-only generation is noticeably slower — a real tradeoff of running fully local, not a bug.

> ⚠️ **Windows PowerShell note (for API testing without the frontend):** the built-in `curl` alias is not real curl and mishandles `-H`/`-d` flags. Use `curl.exe` explicitly, `Invoke-RestMethod`, or the `/docs` interactive UI.

### Running tests

```bash
cd backend
pytest tests/test_retrieval.py -v
```

Integration tests, not mocks — they exercise BM25, pgvector ANN, and RRF fusion against a real, temporarily-seeded Postgres database.

### Running an evaluation

```bash
cd backend
python -m eval.run_eval
```

## 📊 Evaluation

A 10-question eval set was run against a single ingested page ([PostgreSQL string functions docs](https://www.postgresql.org/docs/16/functions-string.html)), measuring retrieval quality (Hit@k, Precision@k, Recall@k, MRR) separately from answer quality.

| Metric | Result |
|---|---|
| Hit@3 | 80% |
| Hit@5 | 90% |
| Recall@5 | 82% |
| MRR | 0.70 |
| Answer keyword score | 90% |

**This eval set is small (10 questions, 1 document) and the answer-scoring method (keyword matching) has known limitations — both described honestly below, not smoothed over.**

### A finding worth calling out specifically

One question ("what function converts a string to lowercase?") scored a misleadingly perfect answer score despite a real, meaningful failure:

- **Retrieval missed the correct chunk entirely** (Hit@5: 0%).
- Instead of declining to answer, the model **inferred a guess from a different function it had actually retrieved** (`upper()`), reasoning by name pattern rather than by grounded evidence — and got it right by luck, not by design.
- The keyword-based scorer gave this a perfect score, because the substring `"lower"` appears inside the word `"lowercase"` in the model's own sentence explaining that it *couldn't* find the answer. A false positive caused by naive substring matching, not evidence of a correct, grounded answer.

This is the most important thing this eval run surfaced: **retrieval failure and generation hallucination can combine to look like success on a shallow metric.** A separate question, correctly labeled as unanswerable from the ingested corpus, *did* get a correctly refused answer — showing the grounding instruction works when retrieval and generation are both functioning; this case shows what happens when retrieval quietly fails first.

**Mitigations identified, not yet implemented (see [Roadmap](#-current-status--roadmap)):**
- Word-boundary matching instead of substring matching in eval scoring (or LLM-as-judge scoring)
- A stronger grounding instruction explicitly forbidding inference from function naming patterns
- A retrieval-confidence gate: if RRF fusion scores fall below a threshold, return an explicit "not confident enough to answer" response rather than passing weak context to generation at all

## ⚖️ Tradeoffs

- **Synchronous ingestion, no queue** — simpler to build and reason about; `/ingest` blocks until a document is fully processed. Fine for single-user, small-corpus use.
- **RRF over weighted score fusion** — BM25 and cosine similarity scores aren't on comparable scales, so combining them by rank position avoids an arbitrary, hard-to-justify weighting scheme.
- **Local models over hosted APIs** — no external cost or API key management, at some quality cost relative to larger hosted models, and noticeably slower generation on CPU-only hardware.
- **Keyword-based eval scoring** — cheap and transparent, but can produce both false negatives (correct answers using different valid terminology) and false positives (substring matches inside unrelated words) — see the finding above.
- **No defense against indirect prompt injection** in ingested content — `POST /ingest` accepts any URL with no allowlist, and scraped content is passed into the LLM prompt without sanitization. Low realistic risk currently (only official PostgreSQL docs have been ingested), but a real gap if this were ever exposed beyond local use.
- **What's deliberately not built (yet)**: async ingestion, CI, auth, observability dashboard, an ingestion UI in the frontend.

## 🤖 Development Process

This project was built collaboratively with Claude (Anthropic), used differently across the two halves of the stack — worth being specific rather than giving one blanket disclosure for both.

**Frontend:** built by AI end-to-end — component structure, the terminal-console design direction, the design token system (color/type), and the markdown rendering fix all came from AI-generated code. My role there was directing scope (read-only, dev-tool aesthetic), applying the code, and catching/fixing the issues that came up when actually running it (an unused-import warning after a half-applied edit, and the missing `react-markdown` styling for code blocks). I did not design or hand-write the frontend myself.

**Backend:** AI facilitated the process rather than authoring it unsupervised — drafting initial implementations of individual functions/files, and engaging in architectural discussion (e.g. evaluating a fully async, queue-driven design against a simpler synchronous one, and explaining why Reciprocal Rank Fusion over a weighted sum of BM25/cosine scores). But the actual debugging — the part that required understanding *why* something broke, not just applying a suggested fix — was done independently by reading real errors and tracebacks: a mistyped `__init__`, a FastAPI `response_model` pointing at the wrong schema, a missing pgvector extension after a volume reset, a stale schema after a model change, a CUDA/Ollama driver crash requiring a CPU-only fallback, and the eval-scoring false-positive documented above. All testing was run against a real local Postgres/pgvector instance and live Ollama calls, not mocked.

**The scope-down decision** — cutting the original async/multi-service architecture in favor of the simpler synchronous design actually shipped here — was a judgment call made independently, prompted by AI laying out the tradeoff honestly rather than defaulting to the more complex design.

## ✅ Current Status & Roadmap

- [X] Hybrid retrieval (BM25 + pgvector ANN + RRF fusion), tested end to end
- [X] Structure-aware ingestion pipeline, tested against real pages
- [X] `POST /ingest` and `POST /query`, tested live
- [X] Eval harness with Hit@k / Precision@k / Recall@k / MRR + refusal detection
- [X] Frontend — query console with numbered, expandable source citations
- [X] Fix eval scoring false positive (word-boundary matching or LLM-as-judge)
- [X] Retrieval-confidence gate before generation
- [X] Stronger anti-hallucination grounding instruction
- [X] Expand eval set beyond 10 questions / 1 document
- [X] Ingestion UI in the frontend

## 👤 Author

**Branden Rease Abrol**
- GitHub: [@breaseabrol](https://github.com/breaseabrol)