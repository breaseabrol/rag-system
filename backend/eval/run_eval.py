import json
from pathlib import Path

from app.core.generation import generate_answer
from app.core.retrieval import retrieve
from app.db.session import SessionLocal
from app.ingestion.pipeline import _rebuild_lexical_index
from eval.metrics import (
    keyword_recall,
    hit_at_k,
    precision_at_k,
    recall_at_k,
    mean_reciprocal_rank,
    _resolve_relevant_chunk_ids,
    UNANSWERABLE_MARKER,
)

DATASET_PATH = Path(__file__).parent / "eval_dataset.jsonl"
RETRIEVAL_POOL = 10  # widen retrieval so @3, @5, @10 are all computable from one call
GENERATION_TOP_K = 5  # how many of those chunks actually get passed to the LLM


def load_eval_set() -> list[dict]:
    with open(DATASET_PATH) as f:
        return [json.loads(line) for line in f if line.strip()]


def _answer_ground_truth_keyword(relevant_content_match: str) -> str:
    return relevant_content_match.split("(")[0].strip()


def run_eval():
    eval_set = load_eval_set()
    db = SessionLocal()
    _rebuild_lexical_index(db)

    results = []
    try:
        for item in eval_set:
            question = item["question"]
            relevant_content_match = item.get("relevant_content_match")
            is_unanswerable = relevant_content_match is None

            chunks = retrieve(db, question, top_k=RETRIEVAL_POOL)
            retrieved_chunk_ids = [c.id for c in chunks]

            answer = generate_answer(question, chunks[:GENERATION_TOP_K])

            if is_unanswerable:
                relevant_ids: set[int] = set()
                answer_score = keyword_recall(answer, [UNANSWERABLE_MARKER])
            else:
                relevant_ids = _resolve_relevant_chunk_ids(db, relevant_content_match)
                keyword = _answer_ground_truth_keyword(relevant_content_match)
                answer_score = keyword_recall(answer, [keyword])

            results.append({
                "question": question,
                "answer": answer,
                "is_unanswerable": is_unanswerable,
                "relevant_ids_found": len(relevant_ids),
                "hit@3": hit_at_k(retrieved_chunk_ids, relevant_ids, k=3),
                "hit@5": hit_at_k(retrieved_chunk_ids, relevant_ids, k=5),
                "precision@5": precision_at_k(retrieved_chunk_ids, relevant_ids, k=5),
                "recall@5": recall_at_k(retrieved_chunk_ids, relevant_ids, k=5),
                "mrr": mean_reciprocal_rank(retrieved_chunk_ids, relevant_ids),
                "answer_score": answer_score,
            })
    finally:
        db.close()

    return results


def print_report(results: list[dict]) -> None:
    print(f"\n{'Question':<45} {'Hit@3':>6} {'Hit@5':>6} {'P@5':>6} {'R@5':>6} {'MRR':>6} {'Answer':>7}")
    print("-" * 90)
    for r in results:
        q = r["question"][:42] + "..." if len(r["question"]) > 42 else r["question"]
        flag = " *" if r["is_unanswerable"] else ""
        print(
            f"{q:<45} {r['hit@3']:>6.0%} {r['hit@5']:>6.0%} "
            f"{r['precision@5']:>6.0%} {r['recall@5']:>6.0%} "
            f"{r['mrr']:>6.2f} {r['answer_score']:>6.0%}{flag}"
        )

    n = len(results)
    print("-" * 90)
    for key, label in [("hit@3", "Hit@3"), ("hit@5", "Hit@5"), ("precision@5", "P@5"),
                        ("recall@5", "R@5"), ("mrr", "MRR"), ("answer_score", "Answer")]:
        avg = sum(r[key] for r in results) / n
        fmt = f"{avg:.2f}" if key == "mrr" else f"{avg:.0%}"
        print(f"AVG {label}: {fmt}")

    print("\n* = unanswerable-by-design question (correct behavior = refusal, not retrieval)")


if __name__ == "__main__":
    results = run_eval()
    print_report(results)

    out_path = Path(__file__).parent / "eval_results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nFull results written to {out_path}")