"""
Integration tests for vector_store.py and lexical_index.py.

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
from app.db.vector_store import similarity_search
from typing import Generator


SAMPLE_CHUNKS = [
    "PostgreSQL is a powerful open source relational database.",
    "The cat sat on a warm windowsill in the afternoon sun.",
    "Vector similarity search uses cosine distance to find nearest neighbors.",
    "Bananas are a good source of potassium and fiber.",
]


@pytest.fixture(scope="module")
def db() -> Generator[Session,None, None]:
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture(scope="module")
def seeded_chunks(db: Session)-> Generator[list[tuple[int,str]],None, None]:
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
    # at least one of our seeded chunks should show up in top results
    assert seeded_ids & set(result_ids)

    # the Postgres chunk should rank above the unrelated "cat" chunk
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

    # the chunk containing "PostgreSQL" and "database" should rank first
    # for a query containing those exact terms
    assert top_chunk_id == postgres_chunk_id
    assert top_score > 0


def test_lexical_index_raises_before_build():
    from app.core.lexical_index import LexicalIndex

    fresh_index = LexicalIndex()
    with pytest.raises(RuntimeError):
        fresh_index.search("anything")