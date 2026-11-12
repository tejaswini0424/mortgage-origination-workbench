import hashlib
import json
import os
import secrets
import time
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request, Response, UploadFile
from urllib.parse import quote
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import select, text
from typing import Annotated, Literal
from itsdangerous import BadSignature, URLSafeTimedSerializer

from .access import authenticate, authorized_case, bootstrap, hash_password, scope, user_info
from .extraction import NAMES, SCHEMAS, normalize
from .preview import render_page
from .storage import Account, Base, BenchmarkRun, Case, CaseExport, CaseGrant, CaseWorksheet, DATA, Document, DocumentContent, Organization, Session, document_json, documents, engine, event, read_document

app = FastAPI(title="Mortgage Origination Workbench", version="1.0")
if os.getenv("AUTO_CREATE_SCHEMA", "1") == "1":
    Base.metadata.create_all(engine)
bootstrap()
PREFIX = "/api/v1"
COOKIE = "mortgage_session"
signer = URLSafeTimedSerializer(os.getenv("SESSION_SECRET") or secrets.token_hex(32), salt="mortgage-session")
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]

class Login(BaseModel):
    username: ShortText
    password: str = Field(min_length=1, max_length=200)

class Intake(BaseModel):
    title: ShortText
    borrower: ShortText

class Correction(BaseModel):
    value: str = Field(min_length=1, max_length=200)

class Release(BaseModel):
    note: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]

class Kind(BaseModel):
    kind: str

class Scenario(BaseModel):
    monthly_income: Decimal = Field(gt=0, le=1_000_000_000, decimal_places=2)
    monthly_debt: Decimal = Field(ge=0, le=1_000_000_000, decimal_places=2)
    loan_amount: Decimal = Field(gt=0, le=1_000_000_000, decimal_places=2)
    property_value: Decimal = Field(gt=0, le=1_000_000_000, decimal_places=2)

def session_user(request: Request):
    try:
        username = signer.loads(request.cookies.get(COOKIE, ""), max_age=28800)
        if not isinstance(username, str):
            raise BadSignature("Invalid session")
        with Session() as db:
            account = db.get(Account, username)
            if account and account.active:
                return user_info(account)
        raise BadSignature("Inactive account")
    except BadSignature:
        raise HTTPException(401, "Sign in to continue.") from None

def reviewer(user=Depends(session_user)):
    if user["role"] not in {"reviewer", "admin"}:
        raise HTTPException(403, "Reviewer access required.")
    return user

def required(db, model, identifier, lock=False):
    obj = db.get(model, identifier, with_for_update=lock)
    if obj is None:
        raise HTTPException(404, "Record not found.")
    return obj

def summary(case):
    return {key: getattr(case, key) for key in ("id", "title", "borrower", "status", "owner")}

def checks(case, docs, saved=None):
    co_borrower = (saved or {}).get("borrowers", {}).get("name", "")
    parties = {" ".join(name.casefold().split()) for name in (case.borrower, co_borrower) if name.strip()}
    result = [f"Missing completed {kind.replace('_', ' ')}." for kind in SCHEMAS
              if not any(doc.kind == kind and doc.status == "completed" for doc in docs)]
    for doc in docs:
        if doc.status != "completed":
            result.append(f"{doc.name}: processing {doc.status}.")
        elif doc.kind == "unknown":
            result.append(f"{doc.name}: classification needed.")
        for field in doc.fields:
            value, key = field["value"], field["key"]
            if field.get("conflict") and not field["reviewed"]:
                result.append(f"{doc.name}: conflicting source values for {key}.")
            elif not value:
                result.append(f"{doc.name}: {key} missing.")
            elif key in NAMES and value.casefold() not in parties:
                result.append(f"{doc.name}: {key} differs from the case parties.")
            elif key == "expiration_date" and date.fromisoformat(value) < date.today():
                result.append(f"{doc.name}: identity document expired.")
    values_by_key = {}
    for doc in docs:
        for field in doc.fields:
            if field["value"]:
                values_by_key.setdefault(field["key"], set()).add(field["value"].casefold())
    result.extend(f"Conflicting {key.replace('_', ' ')} values across documents."
                  for key, values in values_by_key.items() if len(values) > 1)
    return list(dict.fromkeys(result))

@app.middleware("http")
async def prevent_cross_site_writes(request: Request, call_next):
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        allowed = {value.strip().rstrip("/") for value in os.getenv(
            "WORKBENCH_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080,http://127.0.0.1:8080"
        ).split(",")}
        same_origin = str(request.base_url).rstrip("/")
        cross_site = request.headers.get("sec-fetch-site") == "cross-site"
        if (origin and origin not in allowed and origin != same_origin) or (cross_site and origin not in allowed):
            return Response(
                json.dumps({"detail": "This request came from an unrecognized site. Open the workbench in its own browser tab."}),
                status_code=403, media_type="application/json", headers={"Cache-Control": "no-store"},
            )
    response = await call_next(request)
    if request.url.path.startswith(PREFIX):
        response.headers["Cache-Control"] = "no-store"
    return response

@app.post(PREFIX + "/session")
def login(data: Login, response: Response):
    user = authenticate(data.username, data.password)
    if user is None:
        raise HTTPException(401, "Invalid credentials.")
    return start_session(response, user)

def start_session(response, user):
    response.set_cookie(COOKIE, signer.dumps(user["username"]), max_age=28800, httponly=True,
                        samesite="strict", secure=os.getenv("COOKIE_SECURE") == "1")
    return user

@app.post(PREFIX + "/signup", status_code=201)
def signup(data: Login, response: Response):
    from sqlalchemy.exc import IntegrityError

    try:
        with Session.begin() as db:
            organization = Organization(slug=uuid4().hex, name=data.username)
            db.add(organization)
            db.flush()
            account = Account(username=data.username, organization=organization.slug,
                              role="admin", password_hash=hash_password(data.password))
            db.add(account)
            db.flush()
            user = user_info(account)
    except IntegrityError:
        raise HTTPException(409, "That username is already in use.") from None
    return start_session(response, user)

@app.get(PREFIX + "/session")
def current(user=Depends(session_user)):
    return user

@app.delete(PREFIX + "/session")
def logout(response: Response):
    response.delete_cookie(COOKIE)
    return {"status": "signed out"}

@app.get("/healthz")
def health():
    with Session() as db:
        db.execute(text("SELECT 1"))
    return {"status": "API and database reachable"}

@app.get(PREFIX + "/health")
def system_health(user=Depends(session_user)):
    data = health()
    try:
        age = max(0, round(time.time() - (DATA / "worker.heartbeat").stat().st_mtime))
    except FileNotFoundError:
        age = None
    return {**data, "database": engine.dialect.name, "worker": "active" if age is not None and age <= 90 else "no recent heartbeat",
            "heartbeat_age_seconds": age}

@app.get(PREFIX + "/cases")
def list_cases(user=Depends(session_user)):
    with Session() as db:
        return [summary(case) for case in db.scalars(select(Case).where(scope(user)).order_by(Case.title, Case.id))]

@app.post(PREFIX + "/cases", status_code=201)
def create_case(data: Intake, user=Depends(session_user)):
    with Session.begin() as db:
        case = Case(id=uuid4().hex, **data.model_dump(), organization=user["organization"], owner=user["username"], status="draft", events=[])
        event(case, f"Created by {user['username']}.")
        db.add(case)
        return summary(case)

@app.get(PREFIX + "/cases/{case_id}")
def get_case(case_id: str, user=Depends(session_user)):
    with Session() as db:
        case = authorized_case(db, case_id, user)
        docs = documents(db, case.id)
        saved = worksheets(db, case.id)
        return {**summary(case), "documents": [document_json(d) for d in docs],
                "checks": checks(case, docs, saved), "events": case.events, "calculation": case.calculation,
                "exports": list_exports(db, case.id), "worksheets": saved}

@app.post(PREFIX + "/cases/{case_id}/documents", status_code=202)
def upload(case_id: str, file: UploadFile, user=Depends(session_user)):
    limit = 10 * 1024 * 1024
    content = file.file.read(limit + 1)
    if len(content) > limit:
        raise HTTPException(413, "The maximum file size is 10 MiB.")
    signatures = [(b"%PDF-", "application/pdf"), (b"\x89PNG\r\n\x1a\n", "image/png"), (b"\xff\xd8\xff", "image/jpeg")]
    media = next((kind for magic, kind in signatures if content.startswith(magic)), None)
    if media is None:
        raise HTTPException(415, "Upload a PDF, PNG, or JPEG.")
    key = uuid4().hex
    path = DATA / key
    try:
        with Session.begin() as db:
            case = authorized_case(db, case_id, user, lock=True)
            digest = hashlib.sha256(content).hexdigest()
            if any(d.digest == digest for d in documents(db, case.id)):
                raise HTTPException(409, "This file is already attached to the case.")
            name = Path((file.filename or "Document").replace(chr(92), "/")).name[:255]
            doc = Document(id=key, case_id=case.id, name=name, media=media, digest=digest, kind="unknown",
                           status="queued", fields=[], error="")
            db.add(doc)
            if os.getenv("DOCUMENT_STORAGE") == "database":
                db.flush()
                db.add(DocumentContent(document_id=key, content=content))
            else:
                path.write_bytes(content)
            case.status, case.packet = "processing", None
            event(case, f"Uploaded {doc.name} by {user['username']}.")
            return document_json(doc)
    except Exception:
        path.unlink(missing_ok=True)
        raise

@app.get(PREFIX + "/documents/{doc_id}/source")
def source(doc_id: str, user=Depends(session_user)):
    with Session() as db:
        doc = required(db, Document, doc_id)
        authorized_case(db, doc.case_id, user)
        try:
            content = read_document(db, doc.id)
        except FileNotFoundError:
            raise HTTPException(404, "Source document unavailable.") from None
        return Response(content, media_type=doc.media, headers={
            "Content-Disposition": "attachment; filename*=UTF-8''" + quote(doc.name, safe=""),
            "X-Content-Type-Options": "nosniff", "Content-Security-Policy": "sandbox",
        })

def requeue(db, doc_id, user, kind=None):
    doc = required(db, Document, doc_id)
    case = authorized_case(db, doc.case_id, user, lock=True)
    db.refresh(doc)
    if doc.status in {"queued", "running"} or (kind is None and doc.status != "failed"):
        raise HTTPException(409, "This document cannot be queued in its current state.")
    if kind:
        doc.kind = kind
    doc.status, doc.fields, doc.error = "queued", [], ""
    case.status, case.packet = "processing", None
    event(case, f"Queued {doc.name} by {user['username']}.")
    return document_json(doc)

@app.post(PREFIX + "/documents/{doc_id}/retry")
def retry(doc_id: str, user=Depends(session_user)):
    with Session.begin() as db:
        return requeue(db, doc_id, user)

@app.put(PREFIX + "/documents/{doc_id}/classification")
def classification(doc_id: str, data: Kind, user=Depends(reviewer)):
    if data.kind not in SCHEMAS:
        raise HTTPException(422, "Select a supported document type.")
    with Session.begin() as db:
        return requeue(db, doc_id, user, data.kind)

@app.put(PREFIX + "/documents/{doc_id}/fields/{key}")
def correct(doc_id: str, key: str, data: Correction, user=Depends(reviewer)):
    with Session.begin() as db:
        doc = required(db, Document, doc_id)
        case = authorized_case(db, doc.case_id, user, lock=True)
        db.refresh(doc)
        field = next((f for f in doc.fields if f["key"] == key), None)
        if field is None or doc.status != "completed":
            raise HTTPException(404, "Extracted field not found.")
        try:
            value = normalize(key, data.value)
        except ValueError as error:
            raise HTTPException(422, str(error)) from None
        updated = {**field, "original_value": field.get("original_value", field["value"]),
                   "value": value, "reviewed": True}
        doc.fields = [updated if f["key"] == key else f for f in doc.fields]
        case.packet = None
        if case.status != "processing":
            case.status = "needs_review"
        event(case, f"{user['username']} reviewed {doc.name} / {key}.")
        return updated

@app.post(PREFIX + "/cases/{case_id}/calculations")
def calculate(case_id: str, data: Scenario, user=Depends(session_user)):
    result = {"inputs": data.model_dump(mode="json"),
              "dti": float(data.monthly_debt / data.monthly_income * 100),
              "ltv": float(data.loan_amount / data.property_value * 100)}
    with Session.begin() as db:
        case = authorized_case(db, case_id, user, lock=True)
        case.calculation, case.packet = result, None
        if case.status in {"ready_for_export", "exported"}:
            case.status = "needs_review"
        event(case, f"Loan scenario calculated by {user['username']}.")
    return result

@app.post(PREFIX + "/cases/{case_id}/release")
def release(case_id: str, data: Release, user=Depends(reviewer)):
    with Session.begin() as db:
        case = authorized_case(db, case_id, user, lock=True)
        docs = documents(db, case.id)
        if case.status != "needs_review" or not any(d.status == "completed" and d.kind != "unknown" for d in docs):
            raise HTTPException(409, "Complete processing for at least one classified document first.")
        if any(f["value"] and not f["reviewed"] for d in docs for f in d.fields):
            raise HTTPException(409, "Confirm or correct every populated field first.")
        saved = worksheets(db, case.id)
        case.status = "exported"
        event(case, f"Case packet released by {user['username']}.")
        case.packet = {"id": uuid4().hex, "case": summary(case), "documents": [document_json(d) for d in docs],
                       "checks": checks(case, docs, saved), "review_note": data.note, "reviewer": user["username"],
                       "calculations": case.calculation, "worksheets": saved, "timeline": case.events}
        db.add(CaseExport(id=case.packet["id"], case_id=case.id,
                          created_at=datetime.now(timezone.utc).isoformat(), packet=case.packet))
        return {"id": case.packet["id"]}

@app.get(PREFIX + "/cases/{case_id}/exports/latest")
def download(case_id: str, user=Depends(session_user)):
    with Session() as db:
        case = authorized_case(db, case_id, user)
        if case.packet is None:
            raise HTTPException(409, "Release the case before downloading a packet.")
        return Response(json.dumps(case.packet, indent=2), media_type="application/json",
                        headers={"Content-Disposition": f'attachment; filename="case-{case.id}.json"'})

@app.get(PREFIX + "/documents/{doc_id}/pages/{number}")
def preview(doc_id: str, number: int, user=Depends(session_user)):
    with Session() as db:
        doc = required(db, Document, doc_id)
        authorized_case(db, doc.case_id, user)
        try:
            return Response(render_page(read_document(db, doc.id), doc.media, number), media_type="image/png")
        except (ValueError, RuntimeError, OSError):
            raise HTTPException(404, "Source page unavailable.") from None

def list_exports(db, case_id):
    versions = db.scalars(select(CaseExport).where(CaseExport.case_id == case_id).order_by(CaseExport.created_at.desc()))
    return [{"id": version.id, "created_at": version.created_at, "reviewer": version.packet["reviewer"]} for version in versions]

@app.get(PREFIX + "/cases/{case_id}/exports")
def export_history(case_id: str, user=Depends(session_user)):
    with Session() as db:
        authorized_case(db, case_id, user)
        return list_exports(db, case_id)

@app.get(PREFIX + "/cases/{case_id}/exports/{export_id}")
def archived_packet(case_id: str, export_id: str, user=Depends(session_user)):
    with Session() as db:
        authorized_case(db, case_id, user)
        version = required(db, CaseExport, export_id)
        if version.case_id != case_id:
            raise HTTPException(404, "Record not found.")
        return Response(json.dumps(version.packet, indent=2), media_type="application/json",
                        headers={"Content-Disposition": f'attachment; filename="case-{case_id}-{export_id}.json"'})

class Evaluation(BaseModel):
    seed: int = Field(ge=0, le=2147483647)

@app.post(PREFIX + "/evaluations")
def evaluate_baseline(data: Evaluation, user=Depends(session_user)):
    from benchmarks.run import evaluate
    return evaluate("rules", data.seed)

class NewAccount(BaseModel):
    username: Annotated[str, StringConstraints(pattern=r"^[a-zA-Z0-9_.-]{1,120}$")]
    role: Literal["processor", "reviewer", "admin"]
    password: str = Field(min_length=12, max_length=200)

def admin(user=Depends(session_user)):
    if user["role"] != "admin":
        raise HTTPException(403, "Administrator access required.")
    return user

def case_manager(db, case_id, user):
    case = authorized_case(db, case_id, user, lock=True)
    if user["role"] != "admin" and case.owner != user["username"]:
        raise HTTPException(403, "Case owner or administrator access required.")
    return case

@app.get(PREFIX + "/users")
def accounts(user=Depends(admin)):
    with Session() as db:
        return [user_info(account) for account in db.scalars(
            select(Account).where(Account.organization == user["organization"]).order_by(Account.username))]

@app.post(PREFIX + "/users", status_code=201)
def create_account(data: NewAccount, user=Depends(admin)):
    from sqlalchemy.exc import IntegrityError
    try:
        with Session.begin() as db:
            account = Account(username=data.username, organization=user["organization"], role=data.role,
                              password_hash=hash_password(data.password))
            db.add(account)
            return user_info(account)
    except IntegrityError:
        raise HTTPException(409, "Username is unavailable.") from None

@app.get(PREFIX + "/cases/{case_id}/access")
def case_access(case_id: str, user=Depends(session_user)):
    with Session.begin() as db:
        case_manager(db, case_id, user)
        return list(db.scalars(select(CaseGrant.username).where(CaseGrant.case_id == case_id).order_by(CaseGrant.username)))

@app.put(PREFIX + "/cases/{case_id}/access/{username}")
def grant_case(case_id: str, username: str, user=Depends(session_user)):
    with Session.begin() as db:
        case = case_manager(db, case_id, user)
        account = db.get(Account, username)
        if not account or account.organization != case.organization or not account.active:
            raise HTTPException(404, "User not found in this organization.")
        if db.get(CaseGrant, (case_id, username)) is None:
            db.add(CaseGrant(case_id=case_id, username=username))
            event(case, f"{user['username']} assigned case access to {username}.")
        return {"username": username}

@app.delete(PREFIX + "/cases/{case_id}/access/{username}")
def revoke_case(case_id: str, username: str, user=Depends(session_user)):
    with Session.begin() as db:
        case = case_manager(db, case_id, user)
        grant = db.get(CaseGrant, (case_id, username))
        if grant:
            db.delete(grant)
            event(case, f"{user['username']} revoked case access for {username}.")
        return {"username": username}

def worksheets(db, case_id):
    return {row.section: row.data for row in db.scalars(select(CaseWorksheet).where(CaseWorksheet.case_id == case_id))}

class Worksheet(BaseModel):
    amount: Decimal | None = Field(default=None, ge=0, le=1_000_000_000, decimal_places=2)
    name: str = Field(default="", max_length=120)
    notes: str = Field(default="", max_length=1000)

@app.put(PREFIX + "/cases/{case_id}/worksheets/{section}")
def save_worksheet(case_id: str, section: Literal["borrowers", "income", "assets", "liabilities"],
                   data: Worksheet, user=Depends(session_user)):
    if section != "borrowers" and data.amount is None:
        raise HTTPException(422, "Enter an amount.")
    with Session.begin() as db:
        case = authorized_case(db, case_id, user, lock=True)
        values = data.model_dump(mode="json")
        row = db.get(CaseWorksheet, (case.id, section))
        if row is None:
            db.add(CaseWorksheet(case_id=case.id, section=section, data=values))
        else:
            row.data = values
        case.packet = None
        if case.status in {"ready_for_export", "exported"}:
            case.status = "needs_review"
        event(case, f"{user['username']} updated the {section} worksheet.")
        return values

@app.get(PREFIX + "/audit")
def audit_log(user=Depends(session_user)):
    with Session() as db:
        rows = db.scalars(select(Case).where(scope(user)))
        events = [{"case_id": case.id, "title": case.title, "event": value} for case in rows for value in case.events]
        return sorted(events, key=lambda row: row["event"], reverse=True)

def organization_settings(organization, user):
    configured = bool(os.getenv("VISION_ENDPOINT") and os.getenv("VISION_MODEL"))
    return {"organization": user["organization"], "role": user["role"], "upload_limit_mib": 10,
            "page_limit": 30, "vision_configured": configured,
            "document_vision": organization.document_vision,
            "vision_enabled": configured and organization.document_vision,
            "database": engine.dialect.name}

@app.get(PREFIX + "/settings")
def processing_settings(user=Depends(session_user)):
    with Session() as db:
        return organization_settings(db.get(Organization, user["organization"]), user)

class ProcessingPreference(BaseModel):
    document_vision: bool

@app.put(PREFIX + "/settings")
def save_processing_settings(data: ProcessingPreference, user=Depends(admin)):
    with Session.begin() as db:
        organization = db.get(Organization, user["organization"], with_for_update=True)
        organization.document_vision = data.document_vision
        return organization_settings(organization, user)

@app.get(PREFIX + "/benchmark")
def benchmark_metadata(user=Depends(session_user)):
    from benchmarks.suite import CONDITIONS, LOCAL_MODES, VISION_MODES, vision_available
    return {"conditions": CONDITIONS, "document_types": list(SCHEMAS),
            "modes": LOCAL_MODES + VISION_MODES if vision_available() else LOCAL_MODES,
            "vision_enabled": vision_available()}

class BenchmarkRequest(Evaluation):
    vision: bool = False

def serialize_run(row, include_report=False):
    summary = {"id": row.id, "created_at": row.created_at, "seed": row.report["seed"], "status": row.status}
    if include_report:
        summary["report"] = row.report
    return summary

@app.post(PREFIX + "/benchmark/runs", status_code=202)
def enqueue_benchmark(data: BenchmarkRequest, user=Depends(session_user)):
    from benchmarks.suite import vision_available
    if data.vision and not vision_available():
        raise HTTPException(409, "Configure the vision endpoint and model before running hosted comparisons.")
    with Session.begin() as db:
        db.get(Organization, user["organization"], with_for_update=True)
        active = db.scalar(select(BenchmarkRun.id).where(BenchmarkRun.organization == user["organization"],
                           BenchmarkRun.status.in_(("queued", "running"))).limit(1))
        if active:
            raise HTTPException(409, "An evaluation is already queued or running for this organization.")
        row = BenchmarkRun(id=uuid4().hex, organization=user["organization"], status="queued",
                           created_at=datetime.now(timezone.utc).isoformat(), report={"seed": data.seed, "vision": data.vision})
        db.add(row)
        return serialize_run(row, include_report=True)

@app.get(PREFIX + "/benchmark/runs")
def benchmark_history(user=Depends(session_user)):
    with Session() as db:
        rows = db.scalars(select(BenchmarkRun).where(BenchmarkRun.organization == user["organization"])
                          .order_by(BenchmarkRun.created_at.desc()).limit(25))
        return [serialize_run(row) for row in rows]

@app.get(PREFIX + "/benchmark/runs/{run_id}")
def benchmark_report(run_id: str, user=Depends(session_user)):
    with Session() as db:
        row = db.scalar(select(BenchmarkRun).where(BenchmarkRun.id == run_id, BenchmarkRun.organization == user["organization"]))
        if row is None:
            raise HTTPException(404, "Record not found.")
        return serialize_run(row, include_report=True)

class AccountUpdate(BaseModel):
    role: Literal["processor", "reviewer", "admin"]
    active: bool

@app.put(PREFIX + "/users/{username}")
def update_account(username: str, data: AccountUpdate, user=Depends(admin)):
    if username == user["username"]:
        raise HTTPException(409, "An administrator cannot change their own account here.")
    with Session.begin() as db:
        db.get(Organization, user["organization"], with_for_update=True)
        acting = db.get(Account, user["username"])
        if not acting or acting.role != "admin" or not acting.active:
            raise HTTPException(403, "Administrator access required.")
        account = db.scalar(select(Account).where(Account.username == username,
                            Account.organization == user["organization"]).with_for_update())
        if account is None:
            raise HTTPException(404, "User not found in this organization.")
        account.role, account.active = data.role, data.active
        return user_info(account)
