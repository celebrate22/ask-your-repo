from dataclasses import asdict

from ask_repo.evals.metrics import evaluate_retrieval
from ask_repo.ingestion.chunker import make_chunks


def test_recall_and_mrr_use_best_rank_among_expected_chunks():
    chunks = make_chunks(
        "src/auth.py",
        "def validate_token():\n    return True\n\n"
        "def require_login():\n    return True\n",
    )
    ordered = [asdict(chunk) for chunk in reversed(chunks)]

    def fake_search(_chunks, _query, top_k):
        return ordered[:top_k]

    questions = [
        {
            "id": "both-auth-functions",
            "question": "Which functions handle authentication?",
            "expected": [
                {"path": "src/auth.py", "qualified_name": "validate_token"},
                {"path": "src/auth.py", "qualified_name": "require_login"},
            ],
        },
        {
            "id": "second-result",
            "question": "Find validate_token",
            "expected": [
                {"path": "src/auth.py", "qualified_name": "validate_token"},
            ],
        },
        {
            "id": "absent-target",
            "question": "Find account deletion",
            "expected": [
                {"path": "src/accounts.py", "qualified_name": "delete_account"},
            ],
        },
    ]

    report = evaluate_retrieval(chunks, questions, top_k=2, search_fn=fake_search)

    assert report["recall_at_k"] == 1.0
    assert report["mrr_at_k"] == 0.75
    assert (report["answerable"], report["unanswerable"]) == (2, 1)
    assert [case["status"] for case in report["cases"]] == [
        "HIT",
        "HIT",
        "UNANSWERABLE",
    ]
    assert report["cases"][1]["rank"] == 2
    assert report["cases"][2]["warning"]


def test_evaluation_rejects_empty_questions():
    try:
        evaluate_retrieval([], [])
    except ValueError as exc:
        assert "questions" in str(exc)
    else:
        raise AssertionError("empty evaluation dataset must be rejected")
