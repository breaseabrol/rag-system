UNANSWERABLE_MARKER = "UNANSWERABLE"

REFUSAL_PHRASES = [
    "don't have enough information",
    "do not have enough information",
    "cannot answer",
    "can't answer",
    "not enough context",
    "no information",
    "unable to answer",
    "not covered",
    "cannot be determined",
    "does not contain",
    "do not contain",
]


def is_correct_refusal(answer: str) -> bool:
    answer_lower = answer.lower()
    return any(phrase in answer_lower for phrase in REFUSAL_PHRASES)


def keyword_recall(answer: str, expected_keywords: list[str]) -> float:
    if expected_keywords == [UNANSWERABLE_MARKER]:
        return 1.0 if is_correct_refusal(answer) else 0.0

    if not expected_keywords:
        return 1.0

    answer_lower = answer.lower()
    hits = sum(1 for kw in expected_keywords if kw.lower() in answer_lower)
    return hits / len(expected_keywords)


def _resolve_relevant_chunk_ids(db, relevant_content_match: str) -> set[int]:
    from sqlalchemy import select
    from app.db.models import Chunk

    rows = db.execute(
        select(Chunk.id).where(Chunk.content.contains(relevant_content_match))
    ).all()
    return {row.id for row in rows}


def hit_at_k(retrieved_chunk_ids: list[int], relevant_ids: set[int], k: int) -> float:
    """Did ANY relevant chunk appear in the top k?"""
    if not relevant_ids:
        return 1.0  # nothing to find -- e.g. unanswerable question
    return 1.0 if set(retrieved_chunk_ids[:k]) & relevant_ids else 0.0


def precision_at_k(retrieved_chunk_ids: list[int], relevant_ids: set[int], k: int) -> float:
    """Of the k chunks retrieved, what fraction are relevant?"""
    top_k = retrieved_chunk_ids[:k]
    if not top_k:
        return 0.0
    if not relevant_ids:
        return 1.0  # unanswerable: nothing relevant exists, so nothing to be "wrong" about
    hits = sum(1 for cid in top_k if cid in relevant_ids)
    return hits / len(top_k)


def recall_at_k(retrieved_chunk_ids: list[int], relevant_ids: set[int], k: int) -> float:
    """Of all relevant chunks that exist, what fraction were retrieved in the top k?"""
    if not relevant_ids:
        return 1.0
    hits = sum(1 for cid in retrieved_chunk_ids[:k] if cid in relevant_ids)
    return hits / len(relevant_ids)


def mean_reciprocal_rank(retrieved_chunk_ids: list[int], relevant_ids: set[int]) -> float:
    """1/rank of the first relevant chunk found; 0 if none found."""
    if not relevant_ids:
        return 1.0
    for rank, cid in enumerate(retrieved_chunk_ids, start=1):
        if cid in relevant_ids:
            return 1.0 / rank
    return 0.0