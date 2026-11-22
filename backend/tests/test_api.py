from fastapi.testclient import TestClient

from app.main import EVIDENCE, app

client = TestClient(app)


def setup_function():
    EVIDENCE.clear()


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_upload_tickets_and_list():
    csv = b"ticket_id,subject,body\nT-1,Late reminder,Reminder came after my visit\n"
    r = client.post("/projects/demo/tickets", files={"file": ("t.csv", csv, "text/csv")})
    assert r.status_code == 200
    assert r.json()["added"] == 1

    listed = client.get("/projects/demo/evidence").json()
    assert listed[0]["id"] == "T-1"


def test_upload_bad_csv_returns_422():
    r = client.post("/projects/demo/tickets", files={"file": ("t.csv", b"foo\nbar\n", "text/csv")})
    assert r.status_code == 422
