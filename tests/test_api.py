from datetime import date

import pytest
from fastapi.testclient import TestClient


def _create(client: TestClient, **overrides: object) -> dict[str, object]:
    response = client.post(
        "/api/applications", json={"company": "Acme", "title": "Engineer", **overrides}
    )
    assert response.status_code == 201, response.text
    body: dict[str, object] = response.json()
    return body


@pytest.mark.parametrize(
    "path", ["/", "/?range=14", "/?range=30", "/?range=all", "/applications", "/paste"]
)
def test_pages_render(client: TestClient, path: str) -> None:
    _create(client)

    response = client.get(path)

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


@pytest.mark.parametrize("value", ["weekly", "90"])
def test_dashboard_rejects_unknown_range(client: TestClient, value: str) -> None:
    assert client.get("/", params={"range": value}).status_code == 422


def test_applications_filter_accepts_empty_status(client: TestClient) -> None:
    _create(client, company="Globex", status="rejected")

    response = client.get("/applications", params={"status": "", "q": "glob"})

    assert response.status_code == 200
    assert "Globex" in response.text


def test_companies_endpoint(client: TestClient) -> None:
    for _ in range(3):
        _create(client, company="BMW AG")
    _create(client, company="Acme")

    companies = client.get("/api/companies").json()

    assert companies[0] == {"company": "BMW AG", "total": 3, "rejected": 0, "waiting": 3}
    assert companies[1]["company"] == "Acme"


def test_company_filter_shows_frequent_warning(client: TestClient) -> None:
    for title in ("A", "B", "C"):
        _create(client, company="BMW AG", title=title)
    _create(client, company="Acme", title="Other role")

    response = client.get("/applications", params={"company": "bmw ag"})

    assert response.status_code == 200
    assert "Other role" not in response.text
    assert "Bu şirkete çok sayıda başvuru yaptın." in response.text


def test_detail_page_shows_company_total(client: TestClient) -> None:
    created = _create(client, company="BMW AG")
    _create(client, company="BMW AG")

    response = client.get(f"/applications/{created['id']}")

    assert "şirketine toplam 2 başvuru" in response.text


def test_detail_page_and_404(client: TestClient) -> None:
    created = _create(client)

    assert client.get(f"/applications/{created['id']}").status_code == 200
    assert client.get("/applications/999").status_code == 404


def test_patch_sets_and_clears_rejection_date(client: TestClient) -> None:
    app_id = _create(client)["id"]

    rejected = client.patch(f"/api/applications/{app_id}", json={"status": "rejected"}).json()
    assert rejected["rejected_at"] == date.today().isoformat()

    reopened = client.patch(
        f"/api/applications/{app_id}", json={"status": "applied", "rejected_at": ""}
    ).json()
    assert reopened["rejected_at"] is None


@pytest.mark.parametrize(
    "payload",
    [
        {"status": "hired"},
        {"source": "kariyer_net"},
        {"company": "   "},
        {"applied_at": ""},
        {"applied_at": "not-a-date"},
    ],
)
def test_patch_rejects_invalid_payload(client: TestClient, payload: dict[str, str]) -> None:
    app_id = _create(client)["id"]

    assert client.patch(f"/api/applications/{app_id}", json=payload).status_code == 422


def test_patch_missing_application(client: TestClient) -> None:
    assert client.patch("/api/applications/999", json={"notes": "x"}).status_code == 404


def test_delete(client: TestClient) -> None:
    app_id = _create(client)["id"]

    assert client.delete(f"/api/applications/{app_id}").status_code == 204
    assert client.delete(f"/api/applications/{app_id}").status_code == 404


def test_html_delete_redirects(client: TestClient) -> None:
    app_id = _create(client)["id"]

    response = client.post(f"/applications/{app_id}/delete", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/applications"


def test_bulk_create(client: TestClient) -> None:
    response = client.post(
        "/api/applications/bulk",
        json={"items": [{"company": "A", "title": "X"}, {"company": "B", "title": "Y"}]},
    )

    assert response.status_code == 201
    assert response.json()["count"] == 2


def test_bulk_create_requires_items(client: TestClient) -> None:
    assert client.post("/api/applications/bulk", json={"items": []}).status_code == 422


def test_parse_uses_heuristic_without_api_key(client: TestClient) -> None:
    response = client.post("/api/parse", json={"text": "Engineer at Acme"})

    assert response.status_code == 200
    body = response.json()
    assert body["parser"] == "heuristic"
    assert body["jobs"][0]["company"] == "Acme"
