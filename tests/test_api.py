import pytest
from fastapi.testclient import TestClient

from mail_router.api import create_app
from mail_router.schema import Fields


def make(extract_fields=lambda r, t: Fields(patient_name="X")):
    return TestClient(create_app(lambda r: ("rezept", 0.9), extract_fields))


def test_route_contract():
    r = make().post("/route", json={"sender": "a@b.example", "subject": "s", "body": "b"})
    assert r.status_code == 200
    assert r.json() == {
        "type": "rezept",
        "confidence": 0.9,
        "fields": {**{k: None for k in Fields.model_fields}, "patient_name": "X"},
    }


def test_extraction_failure_degrades():
    def boom(r, t):
        raise ConnectionError("ollama down")

    r = make(boom).post("/route", json={"sender": "a@b.example", "subject": "s", "body": "b"})
    assert r.status_code == 200 and r.json()["type"] == "rezept"
    assert all(v is None for v in r.json()["fields"].values())


@pytest.mark.parametrize(
    "payload", [{"sender": "a@b.example", "subject": "", "body": "  "}, {"subject": "s"}]
)
def test_bad_request_422(payload):
    assert make().post("/route", json=payload).status_code == 422


def test_health_and_index():
    c = make()
    assert c.get("/health").json() == {"status": "ok"}
    assert "<form" in c.get("/").text
