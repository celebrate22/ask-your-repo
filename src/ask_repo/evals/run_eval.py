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
        help="repository to scan (use the sample repo for the bundled questions)",
    )
    parser.add_argument("--dataset", type=Path, default=DATASET)
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    scan = chunk_repo(args.repo)
    for skipped in scan.skipped:
        print(
            f"Warning: skipped {skipped['file']} "
            f"({skipped['error_type']}): {skipped['message']}"
        )

    report = evaluate_retrieval(
        scan.chunks,
        load_questions(args.dataset),
        top_k=args.top_k,
    )
    recall = report["recall_at_k"]
    mrr = report["mrr_at_k"]
    recall_text = f"{recall:.1%}" if recall is not None else "n/a"
    mrr_text = f"{mrr:.3f}" if mrr is not None else "n/a"
    print(
        f"Recall@{report['top_k']}: {recall_text}; "
        f"MRR@{report['top_k']}: {mrr_text}; "
        f"answerable: {report['answerable']}; "
        f"unanswerable: {report['unanswerable']}"
    )
    for case in report["cases"]:
        if case["status"] == "UNANSWERABLE":
            status = f"UNANSWERABLE: {case['warning']}"
        elif case["hit"]:
            status = f"HIT at rank {case['rank']}"
        elif case["rank"] is None:
            status = "MISS: expected chunk was not retrieved"
        else:
            status = f"MISS at rank {case['rank']} (outside top {report['top_k']})"
        expected = ", ".join(
            f"{chunk['path']}:{chunk['qualified_name']}"
            for chunk in case["expected"]
        )
        print(f"{case['id']}: {status}; expected {expected}")


if __name__ == "__main__":
    main()
