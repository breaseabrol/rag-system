from ollama import Client

from app.config import settings
from app.db.models import Chunk

_client = Client(host=settings.ollama_base_url)

def build_prompt(question:str, chunks: list[Chunk]) -> str:
    context = "\n\n".join(
        f"[Source {i + 1}]\n{chunk.content}" for i, chunk in enumerate(chunks)
    )

    return f"""Answer the question using ONLY the sources below. If the sources don't contain enough information to answer, say so directly instead of guessing.

    Sources:
    {context}

    Question: {question}

    Answer:"""

def generate_answer(question: str, chunks: list[Chunk]) -> str:
    if not chunks:
        return "I don't have enough information in the ingested documents to answer this question."

    prompt = build_prompt(question, chunks)

    response = _client.chat(
        model=settings.ollama_model,
        messages=[{"role": "user", "content": prompt}],
    )
    return response["message"]["content"]
