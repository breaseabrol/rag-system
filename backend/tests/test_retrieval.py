"""
Integration tests for vector_store.py, lexical_index.py, and retrieval.py.

Requires:
  - docker-compose Postgres running (docker-compose up -d)
  - init_db.py already run against it
  - dependencies installed (sentence-transformers will download the model
    on first run, so the first test invocation will be slower)
"""

import pytest
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models import Document, Chunk
from app.core.embeddings import embedder
from app.core.lexical_index import lexical_index
from app.core.retrieval import retrieve, reciprocal_rank_fusion
from app.db.vector_store import similarity_search
from typing import Generator


SAMPLE_CHUNKS = [
    "PostgreSQL is a powerful open source relational database.",
    "The cat sat on a warm windowsill in the afternoon sun.",
    "Vector similarity search uses cosine distance to find nearest neighbors.",
    "Bananas are a good source of potassium and fiber.",
]


@pytest.fixture(scope="module")
def db() -> Generator[Session, None, None]:
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture(scope="module")
def seeded_chunks(db: Session) -> Generator[list[tuple[int, str]], None, None]:
    """
    Inserts a throwaway Document + Chunks with real embeddings, yields
    (chunk_id, text) pairs, then cleans up after the test module finishes.
    """
    doc = Document(url="test://retrieval-smoke-test", title="Test Doc")
    db.add(doc)
    db.flush()  # assigns doc.id without committing

    embeddings = embedder.embed(SAMPLE_CHUNKS)

    chunks = []
    for i, (text, emb) in enumerate(zip(SAMPLE_CHUNKS, embeddings)):
        chunk = Chunk(document_id=doc.id, content=text, chunk_index=i, embedding=emb)
        db.add(chunk)
        chunks.append(chunk)
    db.commit()

    for c in chunks:
        db.refresh(c)

    chunk_pairs = [(c.id, c.content) for c in chunks]

    yield chunk_pairs

    # cleanup: remove test data so repeated runs don't accumulate junk
    for c in chunks:
        db.delete(c)
    db.delete(doc)
    db.commit()


def test_vector_store_similarity_search(db, seeded_chunks):
    query_embedding = embedder.embed_one("Tell me about databases")

    results = similarity_search(db, query_embedding, top_k=4)

    assert len(results) > 0
    result_ids = [chunk_id for chunk_id, _ in results]
    seeded_ids = {chunk_id for chunk_id, _ in seeded_chunks}
    assert seeded_ids & set(result_ids)

    scores_by_id = dict(results)
    postgres_chunk_id = seeded_chunks[0][0]
    cat_chunk_id = seeded_chunks[1][0]
    if postgres_chunk_id in scores_by_id and cat_chunk_id in scores_by_id:
        assert scores_by_id[postgres_chunk_id] > scores_by_id[cat_chunk_id]


def test_lexical_index_search(seeded_chunks):
    lexical_index.build(seeded_chunks)

    results = lexical_index.search("PostgreSQL database", top_k=4)

    assert len(results) > 0
    top_chunk_id, top_score = results[0]
    postgres_chunk_id = seeded_chunks[0][0]

    assert top_chunk_id == postgres_chunk_id
    assert top_score > 0


def test_lexical_index_raises_before_build():
    from app.core.lexical_index import LexicalIndex

    fresh_index = LexicalIndex()
    with pytest.raises(RuntimeError):
        fresh_index.search("anything")


def test_reciprocal_rank_fusion_unit():
    """
    Pure unit test of the fusion math itself, no DB/model involved.
    Chunk 1 ranks well in both lists -> should win.
    Chunk 2 only appears in bm25 -> should still count, just lower.
    Chunk 3 only appears in ann -> should still count, just lower.
    """
    bm25_results = [(1, 5.2), (2, 3.1)]
    ann_results = [(1, 0.91), (3, 0.80)]

    fused = reciprocal_rank_fusion(bm25_results, ann_results, k=60)
    fused_ids = [chunk_id for chunk_id, _ in fused]

    assert fused_ids[0] == 1
    assert set(fused_ids) == {1, 2, 3}
    assert fused[0][1] > fused[1][1]
    assert fused[0][1] > fused[2][1]


def test_retrieve_end_to_end(db, seeded_chunks):
    """
    Full pipeline: BM25 + ANN both hit real data, fused via RRF, returns
    actual Chunk objects from the DB in fused order.
    """
    lexical_index.build(seeded_chunks)

    results = retrieve(db, "Tell me about PostgreSQL databases", top_k=3)

    assert len(results) > 0
    assert len(results) <= 3

    result_texts = [chunk.content for chunk in results]
    assert any("PostgreSQL" in text for text in result_texts)