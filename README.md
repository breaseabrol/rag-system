# Hybrid RAG Retrieval Backend

A Retrieval-Augmented Generation backend built around one idea: **fuse lexical and semantic retrieval properly, run entirely locally, and keep the pipeline simple enough to actually finish and reason about end to end.**

> **Status:** Active development (07/2026 – present). See [Current Status](#-current-status--roadmap) below for what's built vs. planned.

## 🎯 Why this architecture

Earlier iterations of this project targeted a fully decoupled, queue-driven, multi-service architecture (async ingestion workers, swappable external embedding APIs, CI-gated eval regression). That scope was deliberately cut back — not because those ideas are wrong, but because a synchronous, single-process backend gets to a genuinely working, explainable system faster, without carrying infrastructure that isn't earning its keep yet. Three decisions drive the current design:

1. **Hybrid retrieval, fused correctly.** BM25 (lexical) and pgvector ANN (semantic) search each surface results a single method would miss. They're combined via **Reciprocal Rank Fusion (RRF)** — rank-based, not a weighted sum of raw scores, since BM25 scores and cosine similarity live on incomparable scales.
2. **Runs entirely locally.** Embeddings via `sentence-transformers`, generation via Ollama — no external API keys required to run this end to end.
3. **Structure-aware ingestion.** The chunker treats code blocks and tables as atomic units rather than splitting them mid-block, which naive fixed-size chunking does by default.

## 🏗️ Architecture

```
                    Client (curl / Postman)
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

**Why this shape works for now:** no queue, no worker process, no separate frontend — every request is a normal synchronous FastAPI call. That's a real tradeoff (ingesting a large document blocks the request until it's done), which is explicitly fine for a single-user, portfolio-scale corpus. The retrieval and generation logic underneath isn't a toy version of the idea — it's a real hybrid pipeline, just without the operational scaffolding a production deployment would need.

## 🛠️ Tech Stack

| Layer | Choice | Why |
|---|---|---|
| API | FastAPI (Python) | Async-native, auto OpenAPI docs |
| Vector DB | PostgreSQL + pgvector (HNSW index) | Real SQL + ANN vector search in one database |
| Lexical search | `rank_bm25` (BM25Okapi) | In-memory, no extra service to run |
| Fusion | Reciprocal Rank Fusion | Rank-based combination avoids mixing incomparable BM25/cosine score scales |
| Embeddings | `sentence-transformers` (`all-MiniLM-L6-v2`) | Local, no API key, 384-dim, fast enough on CPU |
| LLM | Ollama (local) | No external API dependency, no per-token cost while iterating |
| Chunking | Custom recursive, structure-aware | Keeps code blocks/tables atomic instead of splitting them |

## 📂 Repository Structure

```
rag-system/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI entrypoint
│   │   ├── config.py                # Env-driven settings (pydantic-settings)
│   │   ├── api/
│   │   │   ├── routes_query.py
│   │   │   └── routes_ingest.py
│   │   ├── core/
│   │   │   ├── chunking.py          # Fixed-size + structure-aware recursive chunker
│   │   │   ├── embeddings.py        # sentence-transformers wrapper
│   │   │   ├── lexical_index.py     # In-memory BM25 index
│   │   │   └── retrieval.py         # RRF fusion of BM25 + ANN
│   │   ├── db/
│   │   │   ├── models.py            # Document, Chunk (pgvector column, HNSW + GIN indexes)
│   │   │   ├── session.py
│   │   │   └── vector_store.py      # pgvector cosine ANN search
│   │   ├── ingestion/
│   │   │   └── loader.py            # HTML → clean text + segment tagging
│   │   └── schemas/
│   │       └── models.py            # Pydantic request/response models
│   ├── eval/
│   │   ├── build_eval_set.py
│   │   ├── run_eval.py
│   │   ├── metrics.py
│   │   └── eval_dataset.jsonl
│   ├── tests/
│   ├── scripts/
│   │   └── init_db.py
│   ├── requirements.txt
│   └── Dockerfile
├── docker-compose.yml                 # Postgres+pgvector
└── README.md
```

## 🚀 Quick Start

```bash
git clone https://github.com/breaseabrol/rag-system.git
cd rag-system

# Spin up Postgres + pgvector
docker-compose up -d

# Install dependencies
cd backend
pip install -r requirements.txt

# Create tables
python scripts/init_db.py

# Run the API
uvicorn app.main:app --reload
```

Requires [Ollama](https://ollama.ai) running locally with a model pulled (e.g. `ollama pull llama3.1`) for the generation step.

*(`.env.example` to be added — confirm required vars against `config.py`.)*

### Running an evaluation

```bash
python eval/run_eval.py
```

## 📊 Evaluation Methodology

*(To be filled in once the eval harness is built — retrieval precision/recall@k and answer faithfulness against a committed QA set in `eval_dataset.jsonl`.)*

## ⚖️ Tradeoffs

- **Synchronous ingestion, no queue**: simpler to build and reason about; means `/ingest` blocks until a document is fully processed. Fine for single-user, small-corpus use — would need an async worker if ingesting many large documents concurrently.
- **RRF over weighted score fusion**: BM25 and cosine similarity scores aren't on comparable scales, so combining them by rank position avoids an arbitrary, hard-to-justify weighting scheme.
- **Local models over hosted APIs**: no external cost or API key management while iterating, at the cost of generation/embedding quality relative to larger hosted models.
- **What's deliberately not built (yet)**: no frontend, no async ingestion, no CI, no observability dashboard. These are staged for later — see roadmap below — not abandoned.

## ✅ Current Status & Roadmap

- [X] `config.py` — env-driven settings
- [X] `db/session.py` — connection pooling wired to config
- [X] `core/embeddings.py` — sentence-transformers wrapper
- [X] `core/lexical_index.py` — BM25 index
- [X] `db/vector_store.py` — pgvector ANN search
- [X] `db/models.py` — fix outstanding typo, finalize schema
- [ ] `ingestion/loader.py` — fix known bug in `get_all_doc_urls`
- [ ] `core/retrieval.py` — wire RRF fusion end to end
- [ ] Sync ingestion pipeline + `POST /ingest` working end to end
- [ ] `core/generation.py` (Ollama) + `POST /query` working end to end
- [ ] Eval set built + first real eval numbers produced
- [ ] Frontend (chat window → citations → upload panel) — planned, after backend is solid
- [ ] CI workflow — planned, after eval harness exists

## 👤 Author

**Branden Rease Abrol**
- GitHub: [@breaseabrol](https://github.com/breaseabrol)
- LinkedIn: [breaseabrol](https://linkedin.com/in/breaseabrol)
