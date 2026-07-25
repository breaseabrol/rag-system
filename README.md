# RAG System with Eval Harness

A Retrieval-Augmented Generation system built around one core idea: **you can't improve what you can't measure.** Ingestion and query are separate services, the vector store and retrieval logic are swappable, and every change runs through an automated eval harness before it ships.

> **Status:** Active development (07/2026 – present). See [Current Status](#-current-status--roadmap) below for what's built vs. planned.

## 🎯 Why this architecture

Most RAG demos couple everything into one script, which makes two things impossible: scaling ingestion independently of queries, and knowing whether a change (new chunking strategy, new embedding model, new prompt) actually made retrieval better or worse. Three decisions drive this system:

1. **Ingestion and query are separate services.** Ingestion is an async, queue-driven pipeline; query is a stateless, low-latency API. Coupling them is the fastest way for a RAG system to fall over under real load.
2. **The vector store and eval harness are decoupled from application logic.** Chunking strategy and embedding model are swappable via config, not code changes — that's what makes "compare X vs Y" experiments possible to run cleanly.
3. **Everything emits structured logs.** Latency, cost, and retrieved-chunk IDs are logged on every request, so quality and performance are observable, not assumed.

## 🏗️ Architecture

```
                                   ┌─────────────────┐
                                   │   Frontend       │
                                   │  (React + Vite)  │
                                   └────────┬─────────┘
                                            │ REST/SSE
                                   ┌────────▼─────────┐
                                   │   API Gateway     │
                                   │  (FastAPI)        │
                                   └──┬──────────────┬─┘
                        ┌────────────▼───┐    ┌──────▼─────────┐
                        │  Query Service   │    │ Ingestion       │
                        │  (retrieval +    │    │ Service         │
                        │   generation)    │    │ (async worker)  │
                        └──┬────────────┬──┘    └──────┬──────────┘
                           │            │               │
                  ┌────────▼──┐   ┌─────▼─────┐   ┌─────▼──────┐
                  │  Vector DB │   │ Claude API │   │  Doc Store  │
                  │ (pgvector) │   │ (Anthropic)│   │ (S3/local)  │
                  └────────────┘   └────────────┘   └─────────────┘
                           │
                  ┌────────▼──────────┐
                  │  Eval Harness      │
                  │  (offline, CI-run) │
                  └────────────────────┘

           Cross-cutting: structured logs → latency/cost metrics → dashboard
```

**Why it scales the way it's designed to:** ingestion runs as a queue-driven worker, so it can scale horizontally independent of query traffic. The query service is stateless, so it can run behind multiple replicas. The vector DB and eval harness are both swappable without touching the API layer — the abstraction exists whether or not the system is ever actually deployed at that scale.

## 🛠️ Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Frontend | React + TypeScript + Vite | Fast to build, type discipline |
| API | FastAPI (Python) | Async-native, plays well with LLM SDKs |
| Vector DB | Postgres + pgvector | Real SQL + vector search together, not a toy store |
| Embeddings | Voyage AI / OpenAI `text-embedding-3` (swappable) | Need ≥2 to run comparisons |
| LLM | Claude (Anthropic API) | Strong for both generation and eval judging |
| Eval | Custom harness + Ragas metrics | Ragas for standard metrics, custom code for control over what's reported |
| Queue | Redis + RQ | Simple, well-understood async ingestion |
| Observability | Structured JSON logs → Postgres → lightweight dashboard | A well-designed lightweight version proves the concept without the OpenTelemetry setup tax |
| CI | GitHub Actions | Tests + eval regression check on every push |

## 📂 Repository Structure

```
rag-system/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI entrypoint
│   │   ├── config.py                # Env-driven settings (swap models/strategies here)
│   │   ├── api/                     # routes_query, routes_ingest, routes_admin
│   │   ├── core/                    # chunking, embeddings, retrieval, generation, reranker
│   │   ├── db/                      # models, session, vector_store (pgvector)
│   │   ├── ingestion/                # loader, worker, tasks (async pipeline)
│   │   └── observability/            # logger, tracer, metrics
│   ├── eval/
│   │   ├── build_eval_set.py         # constructs the QA eval set
│   │   ├── run_eval.py               # runs full eval, computes Ragas metrics
│   │   └── eval_dataset.jsonl        # committed eval set (question, ground-truth, source)
│   ├── tests/                        # unit + integration tests, incl. eval regression test
│   ├── scripts/                      # compare_chunking.py, compare_embeddings.py
│   └── Dockerfile
├── frontend/
│   └── src/                          # ChatWindow, SourceCitations, UploadPanel, EvalDashboard
├── .github/workflows/
│   ├── ci.yml                        # lint + unit tests
│   └── eval-regression.yml           # fails CI if eval metrics regress
├── docker-compose.yml                 # Postgres+pgvector, Redis, API, worker — one command
└── README.md
```

## 🚀 Quick Start

```bash
git clone https://github.com/breaseabrol/rag-system.git
cd rag-system

# Spins up Postgres+pgvector, Redis, API, and worker together
docker-compose up --build
```

*(Confirm exact env vars required — API keys for Voyage AI/OpenAI/Anthropic, DB URL — against `config.py` and add a `.env.example` if one doesn't exist yet.)*

### Running an evaluation

```bash
python backend/eval/run_eval.py
```

### Comparing configurations

```bash
python backend/scripts/compare_chunking.py
python backend/scripts/compare_embeddings.py
```

## 📊 Evaluation Methodology

The harness runs a committed QA eval set (`eval_dataset.jsonl` — real questions paired with ground-truth answers and source documents) through the full retrieval + generation pipeline, and scores it on:

| Metric | What it measures |
|---|---|
| Retrieval Precision/Recall@k | Whether the retriever surfaces the right chunks |
| Faithfulness (Ragas) | Whether generated answers are grounded in retrieved context |
| Answer Relevance (Ragas) | Whether the answer actually addresses the question |

`eval-regression.yml` runs this on every push and fails CI if a change drops these metrics below threshold — a quality gate, not just a correctness gate.

**Results:**

| Configuration | Retrieval Recall | Faithfulness | Notes |
|---|---|---|---|
| *(fill in once `compare_chunking.py` / `compare_embeddings.py` have been run)* | | | |

## ⚖️ Tradeoffs

- **Postgres + pgvector over a managed vector DB** (Pinecone/Weaviate): keeps the stack to one database, avoids a second service to operate, at the cost of some retrieval-at-scale performance a purpose-built vector DB would offer.
- **Redis + RQ over Celery/Kafka**: sufficient to prove async ingestion works and scales independently of query load, without the operational overhead a heavier queue would add for a project at this scale.
- **What breaks at 10x scale**: *(fill in honestly once you've thought it through — this is one of the highest-signal sections in the whole README for an interviewer)*.
- **What's deliberately not built**: no auth/multi-tenancy, no Kubernetes/service mesh — this project is scoped to prove architectural thinking, not to be production infrastructure.

## ✅ Current Status & Roadmap

- [ ] `db/models.py` + `docker-compose.yml` — Postgres+pgvector running locally
- [ ] Manual single-document ingestion confirmed end to end
- [ ] Bare-bones query endpoint working (curl, no frontend)
- [ ] Claude generation wired in with citations
- [ ] Eval set built + first real eval numbers produced
- [ ] Async ingestion via worker + queue
- [ ] Frontend: chat window → citations → upload panel
- [ ] Observability layer + eval dashboard
- [ ] Chunking/embedding comparison results published in this README
- [ ] CI workflows live, deployed publicly

*(Check off what's actually done — this list is more credible half-checked and honest than fully checked and wrong.)*

## 👤 Author

**Branden Rease Abrol**
- GitHub: [@breaseabrol](https://github.com/breaseabrol)
- LinkedIn: [breaseabrol](https://linkedin.com/in/breaseabrol)
