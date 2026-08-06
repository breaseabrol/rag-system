from rank_bm25 import BM25Okapi

class LexicalIndex:
    def __init__(self):
        self._bm25: BM25Okapi | None = None
        self._chunk_ids: list[int] = []

    def build(self, chunks: list[tuple[int,str]]) -> None:
        self._chunk_ids = [chunk_id for chunk_id, _ in chunks]
        tokenised = [content.lower().split() for _,content in chunks]
        self._bm25 = BM25Okapi(tokenised)

    def search(self, query: str, top_k: int = 10) -> list[tuple[int,str]]:
        if self._bm25 is None:
            raise RuntimeError("LexicalIndex.search() called before build()")

        tokenised_query = query.lower().split()
        scores = self._bm25.get_scores(tokenised_query)

        ranked = sorted(zip(self._chunk_ids, scores), key=lambda pair: pair[1], reverse=True)
        return ranked[:top_k]

lexical_index = LexicalIndex()