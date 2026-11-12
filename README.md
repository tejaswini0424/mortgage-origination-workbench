# Mortgage Origination Workbench

Research application for **A Multimodal Agentic AI Framework for Automated Mortgage Document Processing and Loan Origination Assistance**. Use fictional case data and synthetic documents. The workbench supports processing and human review of mortgage evidence. Authorized humans make lending decisions.

## Run with Docker Compose

Copy `.env.example` to `.env` and set distinct values for `POSTGRES_PASSWORD`, `SESSION_SECRET`, and `REVIEWER_PASSWORD`. Set `ADMIN_PASSWORD` to enable the demonstration organization administrator and `PROCESSOR_PASSWORD` to exercise case assignment. Use a long random session secret and strong passwords.

```text
docker compose up --build --wait
```

Open [the workbench](http://localhost:8080) and sign in as `reviewer`, `admin`, or `processor` for the corresponding configured account. PostgreSQL and uploaded files have separate persistent volumes. Docker runs migrations on startup and includes English Tesseract.

## Run on Windows with SQLite

Install Python 3.12 or newer, Node 22 or newer, and Tesseract for scanned documents and the research suite. Run these commands from the repository root.

```powershell
python -m pip install -r backend/requirements.txt
npm.cmd --prefix frontend ci
$env:REVIEWER_PASSWORD = Read-Host "Choose a local reviewer password"
$env:ADMIN_PASSWORD = Read-Host "Choose a local admin password"
$env:SESSION_SECRET = python -c "import secrets; print(secrets.token_hex(32))"
$env:AUTO_CREATE_SCHEMA = "0"
python -m backend.app.migrate
python -m uvicorn backend.app.main:app --port 8000
```

Start the worker and frontend in separate terminals from the repository root.

```powershell
python -m backend.app.worker
```

```powershell
npm.cmd --prefix frontend run dev
```

Open [the local workbench](http://localhost:5173). If port 8000 is in use, choose another Uvicorn port and set `MORTGAGE_API_TARGET` to its URL in the frontend terminal. Set `TESSERACT_CMD` in the worker and API terminals if Tesseract is installed outside PATH or the standard Windows installation location. Run one worker for each database.

For an existing workbench, stop the API and worker and back up the database before applying `python -m backend.app.migrate`. Cases created under the earlier schema migrate to the demonstration organization, with `reviewer` as owner. An administrator can assign access from the case workspace. Bootstrap passwords create accounts on first startup and do not reset existing passwords.

## Demonstrate a case

```powershell
python -m benchmarks.samples
```

1. Create a case for **Fictional Borrower 10000** and upload the four PDFs from `runtime/samples/`.
2. If you created the case as a processor, assign the reviewer from **Case access** and sign in as that reviewer.
3. Confirm or correct fields using **Field review** and source pages. Check the document checklist and record a review note for unresolved exceptions.
4. Save worksheet inputs and calculate an indicative loan scenario. DTI divides monthly debt including the proposed payment by gross monthly income. LTV divides the loan amount by property value.
5. Release the case and download its JSON packet. New evidence or edits invalidate the current release and preserve earlier packets in **Exports**.

## Organizations and roles

An organization administrator can create and deactivate accounts, update roles, and view or assign cases within that organization. Processors and reviewers can access cases they own or have been assigned. Reviewers and administrators can confirm fields, correct classification, and release a case. Accounts outside the case organization receive a missing-record response even if they know its identifiers.

Provision a separate organization administrator after applying migrations. The command prompts for a password.

```powershell
python -m backend.app.access partner-lab partner-admin
```

In Compose, run the same command with `docker compose exec api` before `python`.

## Reproduce the benchmark

Open **Evaluation runs** or run the CLI. The evaluation compares text and OCR rules, positioned-word layout extraction, and layout extraction with conflict verification. Each pipeline receives the same synthetic fixtures. Reports include per-condition field accuracy, coverage, unsupported values, conflict metrics, evidence-page accuracy, classification macro-F1, and latency.

```powershell
python -m benchmarks.suite --seed 81
```

To include generative vision, configure `VISION_ENDPOINT` with the full chat-completions URL and set `VISION_MODEL`. Set `VISION_API_KEY` when required. The application sends rendered pages and extracted text to the configured service. For a local server, bind it to loopback and use synthetic data. The CLI flag `--vision` adds vision-only and vision-plus-verification runs. The research UI queues runs in the worker, then saves reports by organization. For a CPU-only model, reduce `VISION_IMAGE_EDGE` to trade image detail for inference speed. Set `VISION_JSON_SCHEMA=1` when the endpoint supports schema-constrained responses. Organization administrators can switch case documents back to local layout and OCR in Settings.

```powershell
python -m benchmarks.suite --seed 81 --vision
```

## Verification

```powershell
python -m pip install pytest
python -m pytest -q --basetemp runtime/test-data
npm.cmd --prefix frontend run build
Set-Location frontend
npx.cmd playwright install chromium
npx.cmd playwright test
```

To rerun the API suite against PostgreSQL, point `TEST_DATABASE_URL` to an empty, disposable database using a `postgresql+psycopg` URL. The test harness applies the migrations.

The [Compose workflow](.github/workflows/verify.yml) builds the stack, tests it through Nginx, and checks that a released packet remains available after restarting the API and worker. To run the smoke test manually after startup, set `REVIEWER_PASSWORD` in your terminal, then run `python -m tests.compose_smoke`.

See [architecture and limitations](docs/ARCHITECTURE.md) for details.

For the tested local model and exact benchmark settings, see [Reproducing the generative benchmark](docs/BENCHMARK.md).

The final build and all three Chrome tests passed. Ten Python tests passed on SQLite and PostgreSQL 16. The PostgreSQL API, frontend proxy, and separate worker preserved a released packet after a service restart. Docker Compose configuration validation passed. Container execution requires a Docker daemon, which was unavailable on the verification workstation.

The measured five-pipeline result is available in [the seed 81 benchmark report](docs/benchmark-seed-81.json).
