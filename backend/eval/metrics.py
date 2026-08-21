def keyword_recall(answer: str, expected_keywords: list[str]) -> float:
    if not expected_keywords:
        return 1.0
    answer_lower = answer.lower()
    hits = sum(1 for kw in expected_keywords if kw.lower() in answer_lower)
    return hits / len(expected_keywords)


def retrieval_hit_rate(retrieved_chunks: list, expected_keywords: list[str]) -> float:
    if not expected_keywords:
        return 1.0
    combined_text = " ".join(c.content.lower() for c in retrieved_chunks)
    hits = sum(1 for kw in expected_keywords if kw.lower() in combined_text)
    return hits / len(expected_keywords)