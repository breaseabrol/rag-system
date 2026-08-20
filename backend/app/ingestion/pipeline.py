from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.chunking import RecursiveChunker
from app.core.embeddings import embedder
from app.core.lexical_index import lexical_index
from app.db.models import Document, Chunk
from app.ingestion.loader import load_doc

def _rebuild_lexical_index(db:Session) -> None:
    rows = db.execute(select(Chunk.id, Chunk.content)).all()
    all_chunks = [(row.id,row.content) for row in rows]
    lexical_index.build(all_chunks)

def ingest_url(db: Session, url: str) -> Document:
    loaded = load_doc(url)

    existing = db.execute(
        select(Document).where(Document.url == loaded.url)
    ).scalar_one_or_none()

    if existing is not None:
        db.execute(
            Chunk.__table__.delete().where(Chunk.document_id == existing.id)
        )
        db.delete(existing)
        db.flush()

    document = Document(
        url=loaded.url,
        title=loaded.title,
        raw_text=loaded.text,
        doc_metadata=loaded.doc_metadata,
    )
    db.add(document)
    db.flush()  

    chunker = RecursiveChunker(
        chunk_size=settings.chunk_size, overlap=settings.chunk_overlap
    )
    chunk_texts = chunker.chunk(loaded.text)

    if not chunk_texts:
        db.commit()
        _rebuild_lexical_index(db)
        return document

    chunk_embeddings = embedder.embed(chunk_texts)

    for i, (text, emb) in enumerate(zip(chunk_texts, chunk_embeddings)):
        db.add(
            Chunk(
                document_id=document.id,
                content=text,
                chunk_index=i,
                embedding=emb,
            )
        )

    db.commit()
    db.refresh(document)

    _rebuild_lexical_index(db)

    return document

def ingest_all(db: Session) -> list[Document]:
    from app.ingestion.loader import get_all_doc_urls

    urls = get_all_doc_urls()
    documents = []
    for url in urls:
        try:
            documents.append(ingest_url(db, url))
        except Exception as e:
            print(f"Failed to ingest {url}: {e}")
    return documents