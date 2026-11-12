import os

import pytest

@pytest.fixture(scope="module")
def api(tmp_path_factory):
    root = tmp_path_factory.mktemp("workbench")
    os.environ.update(MORTGAGE_DATA=str(root), REVIEWER_PASSWORD="test-reviewer", PROCESSOR_PASSWORD="test-processor", ADMIN_PASSWORD="test-admin")
    if database_url := os.getenv("TEST_DATABASE_URL"):
        os.environ["DATABASE_URL"] = database_url
        from alembic import command
        from alembic.config import Config
        command.upgrade(Config("alembic.ini"), "head")
    from fastapi.testclient import TestClient
    from backend.app.main import app
    with TestClient(app) as client:
        yield client

def test_reviewed_case_workflow(api):
    from backend.app.worker import process_one
    from benchmarks.run import fixture, values_for

    p = "/api/v1"
    assert api.get(p + "/cases").status_code == 401
    assert api.post(p + "/session", json={"username":"processor", "password":"test-processor"}).status_code == 200
    borrower = "Fictional Borrower 10000"
    case = api.post(p + "/cases", json={"title":"Home purchase", "borrower":borrower})
    assert case.status_code == 201
    route = p + "/cases/" + case.json()["id"]
    assert api.post(route + "/documents", files={"file": ("bad.pdf", b"bad")}).status_code == 415
    for kind, values in values_for(borrower).items():
        upload = api.post(route + "/documents", files={"file": (kind + ".pdf", fixture(kind, values))})
        assert upload.status_code == 202
    while process_one():
        pass
    detail = api.get(route).json()
    assert detail["status"] == "needs_review"
    assert not detail["checks"]
    doc = detail["documents"][0]
    key = doc["fields"][0]["key"]
    endpoint = p + "/documents/" + doc["id"] + "/fields/" + key
    assert api.put(endpoint, json={"value":"x"}).status_code == 403
    assert api.put(route + "/access/reviewer").status_code == 200
    assert api.post(p + "/session", json={"username":"reviewer", "password":"test-reviewer"}).status_code == 200
    assert api.post(route + "/release", json={"note":"Reviewed"}).status_code == 409
    for doc in detail["documents"]:
        for field in doc["fields"]:
            assert field["source"] and field["page"] == 1
            assert api.put(p + "/documents/" + doc["id"] + "/fields/" + field["key"], json={"value":field["value"]}).status_code == 200
    scenario = api.post(route + "/calculations", json={"monthly_income":10000,"monthly_debt":2500,"loan_amount":250000,"property_value":312500})
    assert scenario.json()["dti"] == 25
    assert scenario.json()["ltv"] == 80
    assert api.post(route + "/release", json={"note":"Reviewed"}).status_code == 200
    packet = api.get(route + "/exports/latest").json()
    assert packet["review_note"] == "Reviewed"
    assert len(packet["documents"]) == 4
    assert packet["calculations"]["dti"] == 25
    assert api.put(endpoint, json={"value":detail["documents"][0]["fields"][0]["value"]}).status_code == 200
    assert api.get(route + "/exports/latest").status_code == 409
    versions = api.get(route + "/exports").json()
    assert len(versions) == 1
    assert api.get(route + "/exports/" + versions[0]["id"]).json() == packet

def test_benchmark_missing_values():
    from benchmarks.run import evaluate
    result = evaluate("rules", 81)
    assert result["conditions"]["missing_field"]["unsupported"] == 0
    assert result["conditions"]["held_out_layout"]["field_accuracy"] == 1

def test_scanned_pay_stub(monkeypatch):
    import shutil
    from pathlib import Path

    import pymupdf
    from backend.app.extraction import extract
    from benchmarks.run import fixture, values_for

    windows = Path("C:/Program Files/Tesseract-OCR/tesseract.exe")
    executable = os.getenv("TESSERACT_CMD") or shutil.which("tesseract") or (str(windows) if windows.exists() else None)
    if not executable:
        pytest.skip("Tesseract is unavailable")
    monkeypatch.setenv("TESSERACT_CMD", executable)
    borrower = "Fictional Borrower 10000"
    with pymupdf.open(stream=fixture("pay_stub", values_for(borrower)["pay_stub"]), filetype="pdf") as pdf:
        png = pdf[0].get_pixmap(dpi=180).tobytes("png")
    kind, fields = extract(png, "image/png", "rules")
    assert kind == "pay_stub"
    assert {f["key"]: f["value"] for f in fields} == values_for(borrower)["pay_stub"]

def test_organization_and_case_isolation(api):
    from backend.app.access import hash_password
    from backend.app.storage import Account, Organization, Session
    from backend.app.worker import process_one
    from benchmarks.run import fixture, values_for

    with Session.begin() as db:
        if db.get(Organization, "external") is None:
            db.add(Organization(slug="external", name="External test"))
            db.flush()
            db.add(Account(username="external-admin", organization="external", role="admin",
                           password_hash=hash_password("test-external")))
    p = "/api/v1"
    def sign_in(name, password):
        assert api.post(p + "/session", json={"username":name, "password":password}).status_code == 200
    sign_in("processor", "test-processor")
    case = api.post(p + "/cases", json={"title":"Private case", "borrower":"Synthetic Owner"}).json()
    route = p + "/cases/" + case["id"]
    upload = api.post(route + "/documents", files={"file":("pay.pdf", fixture("pay_stub", values_for("Synthetic Owner")["pay_stub"]))})
    assert upload.status_code == 202
    document = p + "/documents/" + upload.json()["id"]
    assert process_one()
    sign_in("external-admin", "test-external")
    assert api.get(p + "/cases").json() == []
    assert api.get(route).status_code == 404
    assert api.get(document + "/source").status_code == 404
    assert api.get(document + "/pages/1").status_code == 404
    assert api.get(route + "/exports").status_code == 404
    assert api.get(route + "/exports/latest").status_code == 404
    assert api.get(route + "/exports/guessed").status_code == 404
    assert api.post(document + "/retry").status_code == 404
    assert api.put(document + "/classification", json={"kind":"pay_stub"}).status_code == 404
    assert api.put(document + "/fields/employee_name", json={"value":"Another Name"}).status_code == 404
    assert api.put(route + "/worksheets/income", json={"amount":"4000"}).status_code == 404
    sign_in("reviewer", "test-reviewer")
    assert api.get(route).status_code == 404
    sign_in("processor", "test-processor")
    assert api.put(route + "/access/external-admin").status_code == 404
    assert api.put(route + "/access/reviewer").status_code == 200
    sign_in("reviewer", "test-reviewer")
    assert api.get(document + "/pages/1").status_code == 200
    assert api.put(route + "/worksheets/income", json={"amount":"4000"}).status_code == 200
    assert api.get(route).json()["worksheets"]["income"]["amount"] == "4000"
    assert api.delete(route + "/access/reviewer").status_code == 403
    sign_in("admin", "test-admin")
    assert api.get(route).status_code == 200
    assert api.delete(route + "/access/reviewer").status_code == 200
    sign_in("reviewer", "test-reviewer")
    assert api.get(route).status_code == 404

def test_paired_benchmark_detects_layout_and_conflicts():
    from benchmarks.suite import LOCAL_MODES, run_suite
    report = run_suite(81, LOCAL_MODES, ("plain", "split_columns", "missing_field", "contradiction"))
    assert report["fixture_count"] == 16
    assert report["modes"]["rules"]["split_columns"]["field_accuracy"] == 0
    assert report["modes"]["layout"]["split_columns"]["field_accuracy"] == 1
    assert report["modes"]["layout"]["contradiction"]["unsupported"] == 4
    assert report["modes"]["layout_verified"]["contradiction"]["unsupported"] == 0
    assert report["modes"]["layout_verified"]["contradiction"]["conflict_recall"] == 1

def test_legacy_case_migration(tmp_path):
    import sqlite3
    import subprocess
    import sys

    env = {**os.environ, "MORTGAGE_DATA": str(tmp_path)}
    env.pop("DATABASE_URL", None)
    env.pop("POSTGRES_HOST", None)
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "0002_exports"], env=env, check=True)
    with sqlite3.connect(tmp_path / "workbench.db") as db:
        db.execute("insert into cases (id, title, borrower, status, events) values (?, ?, ?, ?, ?)",
                   ("legacy", "Existing case", "Synthetic Borrower", "draft", "[]"))
        db.execute("drop table alembic_version")
    subprocess.run([sys.executable, "-m", "backend.app.migrate"], env=env, check=True)
    with sqlite3.connect(tmp_path / "workbench.db") as db:
        assert db.execute("select organization, owner from cases where id='legacy'").fetchone() == ("demo", "reviewer")
        assert db.execute("select version_num from alembic_version").fetchone() == ("0008_document_contents",)

def test_benchmark_queue_and_organization_scope(api):
    p = "/api/v1"
    assert api.post(p + "/session", json={"username":"reviewer", "password":"test-reviewer"}).status_code == 200
    submitted = api.post(p + "/benchmark/runs", json={"seed":53})
    assert submitted.status_code == 202
    run = submitted.json()
    assert run["status"] == "queued"
    assert api.get(p + "/benchmark/runs/" + run["id"]).json()["seed"] == 53
    assert api.post(p + "/benchmark/runs", json={"seed":54}).status_code == 409
    from backend.app.access import hash_password
    from backend.app.storage import Account, Organization, Session
    with Session.begin() as db:
        db.add(Organization(slug="benchmark-other", name="Separate research organization"))
        db.flush()
        db.add(Account(username="benchmark-admin", organization="benchmark-other", role="admin",
                       password_hash=hash_password("test-benchmark")))
    assert api.post(p + "/session", json={"username":"benchmark-admin", "password":"test-benchmark"}).status_code == 200
    assert api.get(p + "/benchmark/runs").json() == []
    assert api.get(p + "/benchmark/runs/" + run["id"]).status_code == 404

def test_vision_candidates_only_credit_matching_source_lines():
    from backend.app.extraction import proposed_fields
    page = ("Employee Name: Fictional Example\nGross Pay: 3500.00", None)
    fields = proposed_fields("pay_stub", [page],
                             [("pay_stub", {"employee_name": "Fictional Example", "gross_pay": "3600.00"})])
    values = {field["key"]: field for field in fields}
    assert values["employee_name"]["source"] == "Employee Name: Fictional Example"
    assert values["gross_pay"]["value"] == "3600.00"
    assert values["gross_pay"]["source"] == ""

def test_organization_administrator_manages_local_accounts(api):
    p = "/api/v1"
    assert api.post(p + "/session", json={"username":"admin", "password":"test-admin"}).status_code == 200
    user = {"username":"managed-reviewer", "password":"test-managed-pass", "role":"reviewer"}
    assert api.post(p + "/users", json=user).status_code == 201
    change = {"role":"processor", "active":False}
    assert api.put(p + "/users/external-admin", json=change).status_code == 404
    assert api.put(p + "/users/admin", json=change).status_code == 409
    assert api.put(p + "/users/managed-reviewer", json=change).json()["active"] is False
    assert api.post(p + "/session", json={"username":user["username"], "password":user["password"]}).status_code == 401

def test_organization_can_choose_layout_only_for_documents(api):
    from backend.app.access import hash_password
    from backend.app.storage import Account, Organization, Session
    with Session.begin() as db:
        db.add(Organization(slug="settings-other", name="Separate settings organization"))
        db.flush()
        db.add(Account(username="settings-admin", organization="settings-other", role="admin",
                       password_hash=hash_password("test-settings")))
    p = "/api/v1"
    preference = {"document_vision": False}
    assert api.post(p + "/session", json={"username":"reviewer", "password":"test-reviewer"}).status_code == 200
    assert api.put(p + "/settings", json=preference).status_code == 403
    assert api.post(p + "/session", json={"username":"admin", "password":"test-admin"}).status_code == 200
    assert api.put(p + "/settings", json=preference).status_code == 200
    assert api.get(p + "/settings").json()["document_vision"] is False
    assert api.post(p + "/session", json={"username":"settings-admin", "password":"test-settings"}).status_code == 200
    assert api.get(p + "/settings").json()["document_vision"] is True
