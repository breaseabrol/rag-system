from sqlalchemy import Column, Integer, String, Text, ForeignKey, JSON
from sqlalchemy.orm import declarative_base, relationship
from pgvector.sqlalchemy import Vector

base = declarative_base()

class Document(base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True)
    url = Column(String, nullable=False, unique=True)
    title = Column(String)
    raw_tedxt = Column(JSON)

    chunks = relationship("Chunk", back_populates="document")

class Chunk(base):
    __tablename__ = "chunks"

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents_id"), nullable=False)
    content = Column(Text, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    embedding = Column(Vector(1536))

    document = relationship("Document", back_populates="chunks")