import json
from pathlib import Path

from app.core.generation import generate_answer
from app.core.retrieval import retrieve
from app.db.session import SessionLocal
from app.ingestion.pipeline import _rebuild_lexical_index
from eval.metrics import keyword_recall, retrieval_hit_rate

DATASET_PATH = Path(__file__).parent / "eval_dataset.jsonl"


def load_eval_set() -> list[dict]:
    with open(DATASET_PATH) as f:
        return [json.loads(line) for line in f if line.strip()]


def run_eval():
    eval_set = load_eval_set()
    db = SessionLocal()

    _rebuild_lexical_index(db)

    results = []
    try:
        for item in eval_set:
            question = item["question"]
            expected_keywords = item.get("expected_keywords", [])

            chunks = retrieve(db, question)
            answer = generate_answer(question, chunks)

            results.append({
                "question": question,
                "answer": answer,
                "retrieval_hit_rate": retrieval_hit_rate(chunks, expected_keywords),
                "answer_keyword_recall": keyword_recall(answer, expected_keywords),
                "chunks_retrieved": len(chunks),
            })
    finally:
        db.close()

    return results


def print_report(results: list[dict]) -> None:
    print(f"\n{'Question':<55} {'Retrieval':>10} {'Answer':>10} {'Chunks':>8}")
    print("-" * 85)
    for r in results:
        q = r["question"][:52] + "..." if len(r["question"]) > 52 else r["question"]
        print(
            f"{q:<55} {r['retrieval_hit_rate']:>9.0%} "
            f"{r['answer_keyword_recall']:>9.0%} {r['chunks_retrieved']:>8}"
        )

    avg_retrieval = sum(r["retrieval_hit_rate"] for r in results) / len(results)
    avg_answer = sum(r["answer_keyword_recall"] for r in results) / len(results)
    print("-" * 85)
    print(f"{'AVERAGE':<55} {avg_retrieval:>9.0%} {avg_answer:>9.0%}")


if __name__ == "__main__":
    results = run_eval()
    print_report(results)

    out_path = Path(__file__).parent / "eval_results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nFull results written to {out_path}")