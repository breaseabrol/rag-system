"""
scripts/smoke_test_ingest.py

One-off manual test: ingests a single real PostgreSQL docs page and
prints what got written, so you can eyeball correctness before wiring
this into an API endpoint.

Usage:
    cd backend
    py scripts/smoke_test_ingest.py
"""

from app.db.session import SessionLocal
from app.ingestion.pipeline import ingest_url

TEST_URL = "https://www.postgresql.org/docs/16/functions-string.html"

def main():
    db = SessionLocal()
    try:
        document = ingest_url(db, TEST_URL)

        print(f"Document id: {document.id}")
        print(f"Title: {document.title}")
        print(f"URL: {document.url}")
        print(f"Metadata: {document.doc_metadata}")
        print(f"Raw text length: {len(document.raw_text or '')} chars")

        chunk_count = len(document.chunks)
        print(f"Chunks created: {chunk_count}")

        if chunk_count:
            first = document.chunks[0]
            print(f"\nFirst chunk (index {first.chunk_index}):")
            print(first.content[:300])
            print(f"Embedding dim: {len(first.embedding)}")
    finally:
        db.close()

if __name__ == "__main__":
    main()