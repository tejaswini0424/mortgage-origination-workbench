import logging
import os
import time

from sqlalchemy import select, update

from .extraction import extract
from .layout import extract_layout
from .storage import Base, BenchmarkRun, Case, DATA, Document, Organization, Session, documents, engine, event, read_document

def process_one():
    with Session.begin() as db:
        doc_id = db.scalar(select(Document.id).where(Document.status == "queued").order_by(Document.id).limit(1))
        if not doc_id:
            return False
        claim = db.execute(update(Document).where(Document.id == doc_id, Document.status == "queued").values(status="running"))
        if not claim.rowcount:
            return True
        doc = db.get(Document, doc_id)
        media, kind = doc.media, doc.kind
        organization = db.get(Organization, db.get(Case, doc.case_id).organization)
        document_vision = organization.document_vision
    try:
        with Session() as db:
            content = read_document(db, doc_id)
        forced_kind = None if kind == "unknown" else kind
        if document_vision and os.getenv("VISION_ENDPOINT") and os.getenv("VISION_MODEL"):
            kind, fields = extract(content, media, forced_kind=forced_kind)
        else:
            kind, fields = extract_layout(content, media, verify=True, forced_kind=forced_kind)
        status, error = "completed", ""
    except Exception as exc:
        logging.error("Document %s failed (%s)", doc_id, type(exc).__name__)
        kind, fields, status, error = kind, [], "failed", "Extraction failed. Check file validity, OCR installation, or configured vision service."
    with Session.begin() as db:
        doc = db.get(Document, doc_id)
        case = db.get(Case, doc.case_id, with_for_update=True)
        doc.kind, doc.fields, doc.status, doc.error = kind, fields, status, error
        db.flush()
        if not any(d.status in {"queued", "running"} for d in documents(db, case.id)):
            case.status = "needs_review"
        event(case, f"Processing {status} for {doc.name}.")
    return True

def process_benchmark(heartbeat=None):
    from benchmarks.suite import LOCAL_MODES, VISION_MODES, run_suite
    with Session.begin() as db:
        row_id = db.scalar(select(BenchmarkRun.id).where(BenchmarkRun.status == "queued")
                           .order_by(BenchmarkRun.created_at).limit(1))
        if not row_id:
            return False
        claimed = db.execute(update(BenchmarkRun).where(BenchmarkRun.id == row_id, BenchmarkRun.status == "queued")
                             .values(status="running"))
        if not claimed.rowcount:
            return True
        config = db.get(BenchmarkRun, row_id).report
    try:
        modes = LOCAL_MODES + VISION_MODES if config["vision"] else LOCAL_MODES
        report, status = run_suite(config["seed"], modes, progress=heartbeat), "completed"
    except Exception:
        logging.exception("Benchmark %s failed", row_id)
        report, status = {**config, "error": "Evaluation failed. Check the worker configuration."}, "failed"
    with Session.begin() as db:
        row = db.get(BenchmarkRun, row_id)
        row.status, row.report = status, report
    return True

def main():
    if os.getenv("AUTO_CREATE_SCHEMA", "1") == "1":
        Base.metadata.create_all(engine)
    with Session.begin() as db:
        db.execute(update(Document).where(Document.status == "running").values(status="queued"))
        db.execute(update(BenchmarkRun).where(BenchmarkRun.status == "running").values(status="queued"))
    heartbeat = DATA / "worker.heartbeat"
    next_heartbeat = 0.0
    while True:
        try:
            if time.monotonic() >= next_heartbeat:
                heartbeat.touch()
                next_heartbeat = time.monotonic() + 5
            if not process_one() and not process_benchmark(heartbeat.touch):
                time.sleep(1)
        except Exception:
            logging.exception("Worker database operation failed")
            time.sleep(3)

if __name__ == "__main__":
    main()

