"""Health check endpoint."""

from fastapi import APIRouter


router = APIRouter()


@router.get("/health")
def health_check() -> dict[str, str]:
    """Return a small response showing that the API is reachable."""
    return {"status": "ok"}
