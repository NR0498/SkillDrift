from fastapi.testclient import TestClient

from skilldrift.api_app import app, get_repository, get_search


class FakeRepository:
    def ping(self):
        return True

    def list_trending(self, direction, limit):
        return [
            {
                "skill": "python",
                "drift": 1.25,
                "current_pct": 12.5,
                "snapshots": 7,
                "status": "rising",
            }
        ][:limit]

    def get_skill(self, skill_name):
        if skill_name.lower() != "python":
            return None
        return {
            "skill": "python",
            "drift": 1.25,
            "current_pct": 12.5,
            "snapshots": 7,
            "status": "rising",
            "trend": [{"date": "2026-06-19", "pct": 12.5}],
        }


class FakeSearch:
    def ping(self):
        return True

    def search(self, query, limit):
        return {
            "total": 1,
            "items": [
                {
                    "id": "1",
                    "title": "Python Engineer",
                    "company": "Example",
                    "tags": "python",
                    "description": "",
                    "source": "test",
                }
            ][:limit],
        }


def test_api_contracts():
    app.dependency_overrides[get_repository] = FakeRepository
    app.dependency_overrides[get_search] = FakeSearch
    try:
        with TestClient(app) as client:
            assert client.get("/health").json()["status"] == "ok"
            assert client.get("/skills/trending?direction=rising").json()[0]["skill"] == "python"
            assert client.get("/skills/python").json()["trend"][0]["pct"] == 12.5
            assert client.get("/skills/unknown").status_code == 404
            assert client.get("/search?q=python").json()["total"] == 1
            assert client.get("/search?q=x").status_code == 422
    finally:
        app.dependency_overrides.clear()
