"""Run the repository's small keyword-retrieval evaluation."""

import argparse
import json
from pathlib import Path

from ..ingestion.chunker import chunk_repo
from .metrics import evaluate_retrieval


DATASET = Path(__file__).parent / "dataset" / "questions.jsonl"


def load_questions(path: Path = DATASET) -> list[dict]:
    """Load questions from a JSON Lines dataset."""
    with path.open(encoding="utf-8") as dataset_file:
        return [json.loads(line) for line in dataset_file if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "repo",
        nargs="?",
        default=".",
        help="repository to scan (defaults to the current directory)",
    )
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    chunks = chunk_repo(args.repo)
    report = evaluate_retrieval(chunks, load_questions(), top_k=args.top_k)
    print(f"Recall@{report['top_k']}: {report['recall_at_k']:.1%} "
          f"({report['hits']}/{report['total']})")
    for case in report["cases"]:
        if case["hit"]:
            status = f"rank {case['rank']}"
        elif case["rank"] is None:
            status = "not retrieved"
        else:
            status = f"rank {case['rank']} (outside top {report['top_k']})"
        print(f"{case['id']}: {status}; expected "
              f"{case['expected_file']}:{case['expected_qualified_name']}")


if __name__ == "__main__":
    main()
