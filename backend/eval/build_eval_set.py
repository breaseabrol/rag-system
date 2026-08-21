import json
from pathlib import Path

DATASET_PATH = Path(__file__).parent / "eval_dataset.jsonl"


def add_qa_pair(question: str, expected_keywords: list[str]) -> None:
    entry = {"question": question, "expected_keywords": expected_keywords}
    with open(DATASET_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")
    print(f"Added: {question}")


def main():
    print(f"Appending to {DATASET_PATH}")
    print("Enter blank question to stop.\n")
    while True:
        question = input("Question: ").strip()
        if not question:
            break
        keywords_raw = input("Expected keywords (comma-separated): ").strip()
        keywords = [k.strip() for k in keywords_raw.split(",") if k.strip()]
        add_qa_pair(question, keywords)


if __name__ == "__main__":
    main()