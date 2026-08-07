from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.embeddings import embedder
from app.core.lexical_index import lexical_index
from app.db.models import Chunk
from app.db.vector_store import similarity_search


def reciprocal_rank_fusion(
    bm25_results: list[tuple[int, float]],
    ann_results: list[tuple[int, float]],
    k: int = 60,
) -> list[tuple[int, float]]:
    
    # Returns [(chunk_id, fused_score), ...] sorted best-first.
    
    scores: dict[int, float] = {}

    for rank, (chunk_id, _) in enumerate(bm25_results, start=1):
        scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)

    for rank, (chunk_id, _) in enumerate(ann_results, start=1):
        scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)

    return sorted(scores.items(), key=lambda item: item[1], reverse=True)


def _fetch_chunks_by_id(db: Session, chunk_ids: list[int]) -> list[Chunk]:
    if not chunk_ids:
        return []

    rows = db.execute(select(Chunk).where(Chunk.id.in_(chunk_ids))).scalars().all()
    rows_by_id = {chunk.id: chunk for chunk in rows}

    return [rows_by_id[chunk_id] for chunk_id in chunk_ids if chunk_id in rows_by_id]


def retrieve(db: Session, query: str, top_k: int | None = None) -> list[Chunk]:
    """
    Hybrid retrieval: runs BM25 and ANN search independently, fuses their
    rankings via RRF, and returns the top_k Chunk objects in fused order.
    """
    top_k = top_k or settings.retrieval_top_k
    candidate_pool = top_k * 3  # widen candidates before fusing

    bm25_results = lexical_index.search(query, top_k=candidate_pool)

    query_embedding = embedder.embed_one(query)
    ann_results = similarity_search(db, query_embedding, top_k=candidate_pool)

    fused = reciprocal_rank_fusion(bm25_results, ann_results, k=settings.rrf_k)
    top_chunk_ids = [chunk_id for chunk_id, _ in fused[:top_k]]

    return _fetch_chunks_by_id(db, top_chunk_ids)