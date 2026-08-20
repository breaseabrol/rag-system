from sentence_transformers import SentenceTransformer
from app.config import settings

class EmbeddingModel:
    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or settings.embedding_model_name
        self._model = SentenceTransformer(self.model_name)
        actual_dim = self._model.get_sentence_embedding_dimension()
        if actual_dim != settings.embedding_dim:
            raise ValueError(
                f"Model '{self.model_name}' produces {actual_dim}-dim vectors, "
                f"but settings.embedding_dim is {settings.embedding_dim}. "
                f"Update config.py and the Vector() column in models.py to match."
            )

    def embed(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        embeddings = self._model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True
        )
        return embeddings.tolist()

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]

embedder = EmbeddingModel()
