from fastapi.testclient import TestClient

from ask_repo.api.app import create_app


def test_health_route_reports_that_the_app_is_running():
    with TestClient(create_app()) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
