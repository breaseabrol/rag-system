from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import SessionLocal,get_db
from app.ingestion.pipeline import ingest_url
from app.schemas.model import IngestRequest, IngestResponse

router = APIRouter()

@router.post("/ingest", response_model=IngestResponse)
def ingest(request: IngestRequest, db:Session = Depends(get_db)) -> IngestResponse:
    try:
        document = ingest_url(db, request.url)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to ingest {request.url}: {e}")
    return IngestResponse(
        document_id = document.id,
        url = document.url,
        title = document.title,
        chunk_count = len(document.chunks)
    )