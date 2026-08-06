from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Chunk

def similarity_search(db: Session, query_embedding: list[float], top_k: int = 10) -> list[tuple[int,float]]:
    distance = Chunk.embedding.cosine_distance(query_embedding)

    rows = db.execute(
        select(Chunk.id, distance.label("distance"))
        .order_by(distance)
        .limit(top_k)
    ).all()

    return [(row.id, 1-row.distance) for row in rows]