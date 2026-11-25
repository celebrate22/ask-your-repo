"""Metrics for checking whether retrieval finds the expected chunks."""

from ..retrieval.search import keyword_search


def evaluate_retrieval(
    chunks: list[dict], questions: list[dict], top_k: int = 5
) -> dict:
    """Run each question and report Recall@k plus per-question ranks.

    A question counts as a hit when its expected file and qualified name appear
    in the first ``top_k`` results. The dataset currently marks one expected
    chunk per question, so Recall@k is the fraction of questions retrieved.
    """
    if top_k <= 0:
        raise ValueError("top_k must be positive")
    if not questions:
        raise ValueError("questions must not be empty")

    cases = []
    hits = 0
    for question in questions:
        # Retrieve all chunks so a miss also reports the expected chunk's rank.
        results = keyword_search(
            chunks, question["question"], top_k=max(1, len(chunks))
        )
        expected = (
            question["expected_file"],
            question["expected_qualified_name"],
        )
        rank = next(
            (
                index
                for index, result in enumerate(results, start=1)
                if (result["file"], result["qualified_name"]) == expected
            ),
            None,
        )
        hit = rank is not None and rank <= top_k
        hits += hit
        cases.append({
            "id": question["id"],
            "question": question["question"],
            "expected_file": expected[0],
            "expected_qualified_name": expected[1],
            "rank": rank,
            "hit": hit,
            "top_result": (
                f"{results[0]['file']}:{results[0]['qualified_name']}"
                if results
                else None
            ),
        })

    return {
        "top_k": top_k,
        "recall_at_k": hits / len(questions),
        "hits": hits,
        "total": len(questions),
        "cases": cases,
    }
