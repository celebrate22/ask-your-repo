"""Metrics for checking whether retrieval finds the expected chunks."""

from collections.abc import Callable, Mapping, Sequence

from ..ingestion.chunker import Chunk
from ..retrieval.search import keyword_search

ChunkInput = Mapping[str, object] | Chunk
SearchFunction = Callable[[Sequence[ChunkInput], str, int], list[dict]]


def _identity(chunk: Mapping[str, object] | Chunk) -> tuple[str, str]:
    if isinstance(chunk, Chunk):
        return chunk.path, chunk.qualified_name
    return str(chunk["path"]), str(chunk["qualified_name"])


def evaluate_retrieval(
    chunks: Sequence[ChunkInput],
    questions: list[dict],
    top_k: int = 5,
    search_fn: SearchFunction = keyword_search,
) -> dict:
    """Score search with Recall@k and MRR@k and explain every case.

    A question's ``expected`` list contains acceptable ``path`` and
    ``qualified_name`` pairs. The best-ranked acceptable chunk determines its
    rank. Targets absent from the corpus are marked UNANSWERABLE and excluded
    from the metric denominators.
    """
    if top_k <= 0:
        raise ValueError("top_k must be positive")
    if not questions:
        raise ValueError("questions must not be empty")

    corpus_identities = {_identity(chunk) for chunk in chunks}
    cases = []
    hits = 0
    reciprocal_ranks = []
    answerable = 0

    for question in questions:
        expected_records = question.get("expected")
        if not expected_records:
            raise ValueError(f"Question {question.get('id')!r} needs expected chunks")
        expected = {
            (record["path"], record["qualified_name"])
            for record in expected_records
        }
        present_expected = expected & corpus_identities
        case = {
            "id": question["id"],
            "question": question["question"],
            "expected": [
                {"path": path, "qualified_name": qualified_name}
                for path, qualified_name in sorted(expected)
            ],
            "rank": None,
            "hit": False,
            "reciprocal_rank": 0.0,
            "top_result": None,
        }

        if not present_expected:
            case["status"] = "UNANSWERABLE"
            case["warning"] = "No expected chunk exists in the scanned corpus."
            cases.append(case)
            continue

        answerable += 1
        results = search_fn(chunks, question["question"], max(1, len(chunks)))
        if results:
            case["top_result"] = (
                f"{results[0]['path']}:{results[0]['qualified_name']}"
            )
        rank = next(
            (
                index
                for index, result in enumerate(results, start=1)
                if _identity(result) in present_expected
            ),
            None,
        )
        case["rank"] = rank
        case["hit"] = rank is not None and rank <= top_k
        if case["hit"]:
            hits += 1
            case["status"] = "HIT"
            case["reciprocal_rank"] = 1.0 / rank
        else:
            case["status"] = "MISS"
        reciprocal_ranks.append(case["reciprocal_rank"])
        cases.append(case)

    return {
        "top_k": top_k,
        "recall_at_k": hits / answerable if answerable else None,
        "mrr_at_k": sum(reciprocal_ranks) / answerable if answerable else None,
        "hits": hits,
        "answerable": answerable,
        "unanswerable": len(questions) - answerable,
        "total": len(questions),
        "cases": cases,
    }
