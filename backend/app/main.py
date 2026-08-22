from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes_ingest import router as ingest_router
from app.db.session import SessionLocal
from app.ingestion.pipeline import _rebuild_lexical_index
from app.api.routes_query import router as query_router
from fastapi.middleware.cors import CORSMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SessionLocal()
    try:
        _rebuild_lexical_index(db)
    finally:
        db.close()

    yield  # app runs here


app = FastAPI(title="RAG Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["POST"],
    allow_headers=["*"],
)

app.include_router(query_router, tags=["query"])
app.include_router(ingest_router, tags=["ingest"])


@app.get("/health")
def health():
    return {"status": "ok"}