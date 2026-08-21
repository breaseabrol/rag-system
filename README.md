# Hybrid RAG Retrieval Backend

A Retrieval-Augmented Generation backend built around one idea: **fuse lexical and semantic retrieval properly, run entirely locally, and keep the pipeline simple enough to actually finish, test, and reason about end to end.**

## 🎯 Why this architecture

Earlier iterations of this project targeted a fully decoupled, queue-driven, multi-service architecture (async ingestion workers, swappable external embedding APIs, CI-gated eval regression). That scope was deliberately cut back — not because those ideas are wrong, but because a synchronous, single-process backend gets to a genuinely working, explainable, *tested* system faster, without carrying infrastructure that isn't earning its keep yet. Three decisions drive the current design:

1. **Hybrid retrieval, fused correctly.** BM25 (lexical) and pgvector ANN (semantic) search each surface results a single method would miss. They're combined via **Reciprocal Rank Fusion (RRF)** — rank-based, not a weighted sum of raw scores, since BM25 scores and cosine similarity live on incomparable scales.
2. **Runs entirely locally.** Embeddings via `sentence-transformers`, generation via Ollama — no external API keys required to run this end to end.
3. **Structure-aware ingestion.** The chunker treats code blocks and tables as atomic units rather than splitting them mid-block, which naive fixed-size chunking does by default.

## 🏗️ Architecture

```
                    Client (curl / Postman / Swagger UI)
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

No queue, no worker process, no separate frontend — every request is a normal synchronous FastAPI call. That's a real tradeoff (ingesting a document blocks the request until it's done), which is explicitly fine for a single-user, portfolio-scale corpus.

## 🛠️ Tech Stack

| Layer | Choice | Why |
|---|---|---|
| API | FastAPI (Python) | Async-native, auto OpenAPI docs at `/docs` |
| Vector DB | PostgreSQL + pgvector (HNSW index) | Real SQL + ANN vector search in one database |
| Lexical search | `rank_bm25` (BM25Okapi) | In-memory, no extra service to run |
| Fusion | Reciprocal Rank Fusion | Rank-based combination avoids mixing incomparable BM25/cosine score scales |
| Embeddings | `sentence-transformers` (`all-MiniLM-L6-v2`) | Local, no API key, 384-dim |
| LLM | Ollama (local, e.g. `llama3.2:3b`) | No external API dependency or per-token cost |
| Chunking | Custom recursive, structure-aware | Keeps code blocks/tables atomic instead of splitting them |

## 📂 Repository Structure

```
rag-system/
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
│   │   ├── build_eval_set.py
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

- Python 3.10+
- Docker (for Postgres/pgvector)
- [Ollama](https://ollama.com/download) — installed and running locally

### Setup

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

Visit `http://localhost:8000/docs` for the interactive API — ingest a page via `POST /ingest`, then ask questions about it via `POST /query`.

> ⚠️ **Windows PowerShell note:** the built-in `curl` alias is not real curl and mishandles `-H`/`-d` flags. Use `curl.exe` explicitly, `Invoke-RestMethod`, or just use the `/docs` UI — far less friction while iterating.

### Running tests

```bash
pytest tests/test_retrieval.py -v
```

Integration tests, not mocks — they exercise BM25, pgvector ANN, and RRF fusion against a real, temporarily-seeded Postgres database.

### Running an evaluation

```bash
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
- **Local models over hosted APIs** — no external cost or API key management, at some quality cost relative to larger hosted models (especially with a 3B-parameter local model).
- **Keyword-based eval scoring** — cheap and transparent, but can produce both false negatives (correct answers using different valid terminology) and false positives (substring matches inside unrelated words) — see the finding above.
- **No defense against indirect prompt injection** in ingested content — `POST /ingest` accepts any URL with no allowlist, and scraped content is passed into the LLM prompt without sanitization. Low realistic risk currently (only official PostgreSQL docs have been ingested), but a real gap if this were ever exposed beyond local use.
- **What's deliberately not built (yet)**: no frontend, no async ingestion, no CI, no auth, no observability dashboard.

## 🤖 Development Process

This project was built collaboratively with Claude (Anthropic), used as a pair-programming and design-review tool throughout — not as a black box that wrote the whole thing unsupervised.

**How AI was used:**
- Drafting initial implementations of individual functions/files, which were then read, tested, and debugged independently
- Architectural discussion — evaluating a fully async, queue-driven design against a simpler synchronous one, and choosing the latter for a buildable, testable scope without sacrificing the retrieval logic that actually matters
- Explaining trade-offs that were then defended or challenged — e.g. why Reciprocal Rank Fusion over a weighted sum of BM25/cosine scores

**What was done independently:**
- Every bug in this repo was diagnosed and fixed by reading the actual error/traceback — including a mistyped `__init__`, a FastAPI `response_model` pointing at the wrong schema, a missing pgvector extension after a volume reset, a stale schema after a model change, and the eval-scoring false-positive documented above
- All testing against a real local Postgres/pgvector instance and live Ollama calls
- The decision to cut scope from the original async/multi-service design when it added complexity the project didn't need

## ✅ Current Status & Roadmap

- [X] Hybrid retrieval (BM25 + pgvector ANN + RRF fusion), tested end to end
- [X] Structure-aware ingestion pipeline, tested against real pages
- [X] `POST /ingest` and `POST /query`, tested live
- [X] Eval harness with Hit@k / Precision@k / Recall@k / MRR + refusal detection
- [ ] Fix eval scoring false positive (word-boundary matching or LLM-as-judge)
- [ ] Retrieval-confidence gate before generation
- [ ] Stronger anti-hallucination grounding instruction
- [ ] Expand eval set beyond 10 questions / 1 document
- [ ] Frontend (chat window → citations → upload panel)
- [ ] CI workflow, once eval harness is more mature

## 👤 Author

**Branden Rease Abrol**
- GitHub: [@breaseabrol](https://github.com/breaseabrol)