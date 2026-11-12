import os
from pathlib import Path

from sqlalchemy import LargeBinary, URL, ForeignKey, String, Text, JSON, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

DATA = Path(os.getenv("MORTGAGE_DATA", "runtime")).resolve()
DATA.mkdir(parents=True, exist_ok=True)
def database_url():
    if configured := os.getenv("DATABASE_URL"):
        url = make_url(configured)
        if url.drivername in {"postgres", "postgresql"}:
            return url.set(drivername="postgresql+psycopg")
        return url
    if os.getenv("POSTGRES_HOST"):
        return URL.create("postgresql+psycopg", username="mortgage", password=os.environ["POSTGRES_PASSWORD"],
                          host=os.environ["POSTGRES_HOST"], database="mortgage")
    return f"sqlite:///{(DATA / 'workbench.db').as_posix()}"

engine = create_engine(database_url(), pool_pre_ping=True)
Session = sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

class Case(Base):
    __tablename__ = "cases"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    organization: Mapped[str] = mapped_column(ForeignKey("organizations.slug"), index=True)
    owner: Mapped[str] = mapped_column(String(120))
    title: Mapped[str] = mapped_column(String(120))
    borrower: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(32), default="draft")
    events: Mapped[list] = mapped_column(JSON, default=list)
    calculation: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    packet: Mapped[dict | None] = mapped_column(JSON, nullable=True)

class Document(Base):
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    media: Mapped[str] = mapped_column(String(32))
    digest: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(32), default="unknown")
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    fields: Mapped[list] = mapped_column(JSON, default=list)
    error: Mapped[str] = mapped_column(Text, default="")

def documents(db, case_id):
    from sqlalchemy import select
    return list(db.scalars(select(Document).where(Document.case_id == case_id)))

def document_json(doc):
    return {key: getattr(doc, key) for key in ("id", "name", "kind", "status", "fields", "error")}

def event(case, message):
    from datetime import datetime, timezone
    case.events = [*case.events, f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} {message}"]

class CaseExport(Base):
    __tablename__ = "case_exports"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    created_at: Mapped[str] = mapped_column(String(40))
    packet: Mapped[dict] = mapped_column(JSON)

class Organization(Base):
    __tablename__ = "organizations"
    slug: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    document_vision: Mapped[bool] = mapped_column(default=True)

class Account(Base):
    __tablename__ = "accounts"
    username: Mapped[str] = mapped_column(String(120), primary_key=True)
    organization: Mapped[str] = mapped_column(ForeignKey("organizations.slug"), index=True)
    role: Mapped[str] = mapped_column(String(20))
    password_hash: Mapped[str] = mapped_column(String(200))
    active: Mapped[bool] = mapped_column(default=True)

class CaseGrant(Base):
    __tablename__ = "case_grants"
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), primary_key=True)
    username: Mapped[str] = mapped_column(ForeignKey("accounts.username"), primary_key=True)

class CaseWorksheet(Base):
    __tablename__ = "case_worksheets"
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), primary_key=True)
    section: Mapped[str] = mapped_column(String(32), primary_key=True)
    data: Mapped[dict] = mapped_column(JSON)

class BenchmarkRun(Base):
    __tablename__ = "benchmark_runs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    organization: Mapped[str] = mapped_column(ForeignKey("organizations.slug"), index=True)
    created_at: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20), index=True, default="queued")
    report: Mapped[dict] = mapped_column(JSON)

class DocumentContent(Base):
    __tablename__ = "document_contents"
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    content: Mapped[bytes] = mapped_column(LargeBinary)

def read_document(db, document_id):
    saved = db.get(DocumentContent, document_id)
    return saved.content if saved is not None else (DATA / document_id).read_bytes()
