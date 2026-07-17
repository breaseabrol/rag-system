from sqlalchemy import Column, Integer, String, Text, ForeignKey, JSON, Index, Computed
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import declarative_base, relationship
from pgvector.sqlalchemy import Vector

Base = declarative_base()

class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True)
    url = Column(String, nullable=False, unique=True)
    title = Column(String)
    raw_tedxt = Column(JSON)

    chunks = relationship("Chunk", back_populates="document")

class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    content = Column(Text, nullable=False)
    chunk_index = Column(Integer, nullable=False)

    # sentence-transformers all-MiniLM-L6-v2 -> 384 dims. Change if you pick a different model.
    embedding = Column(Vector(384))

    # auto-generated lexical search column, kept in sync by Postgres itself
    content_tsv = Column(
        TSVECTOR,
        Computed("to_tsvector('english', content)", persisted=True)
    )

    document = relationship("Document", back_populates="chunks")

    __table_args__ = (
        Index("ix_chunks_content_tsv", "content_tsv", postgresql_using="gin"),
        Index(
            "ix_chunks_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )