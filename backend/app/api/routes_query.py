from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.generation import generate_answer
from app.core.retrieval import retrieve
from app.db.session import get_db
from app.schemas.model import ChunkResult, QueryRequest, QueryResponse

router = APIRouter()

@router.post("/query", response_model=QueryResponse)
def query(request: QueryRequest, db: Session = Depends(get_db)) -> QueryResponse:
    chunks = retrieve(db, request.query, top_k = request.top_k)
    answer = generate_answer(request.query, chunks)

    sources = [
        ChunkResult(
            chunk_id=chunk.id,
            content=chunk.content,
            document_title=chunk.document.title,
            document_url=chunk.document.url,
        )
        for chunk in chunks
    ]

    return QueryResponse(answer=answer, sources=sources)