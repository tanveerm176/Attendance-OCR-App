# Attendance OCR App — Project Roadmap & Checklist

**Purpose of this document:** A single reference tying together the MVP build, future feature phases (GUI, web, API, cloud), and CVS ISEP-aligned infrastructure skills — sequenced so that nothing done now needs to be redone later.

**Core principle driving the sequencing:** The `OCRPipeline.run(pdf_path) -> pd.DataFrame` interface is the hinge everything else swings on. As long as that stays clean and prompt-free, Phase 2 (GUI), Phase 3 (web), and the API/cloud work bolt on without touching pipeline internals. This is why the phases below don't compete with each other for time — they're additive, not overlapping.

---

## Phase 0 — MVP (current focus, demo target)

**Goal:** A working, demoable pipeline: PDF in → Excel out, via CLI.

### Steps
- [ ] Finish `classification.py` (HSV-based attendance status detection, column 5)
- [ ] Write `pipeline.py` as a **stub/skeleton first** — lock in the data handoffs between stages before wiring in real module calls. This is the step that prevents rework later; get the shape of `OCRPipeline.run()` right before filling in logic.
- [ ] Write `models.py` — dataclasses: `AttendanceRecord`, `ReconciliationResult`
- [ ] Write `exceptions.py` — custom exceptions for pipeline failure modes (e.g. malformed PDF, no columns detected, no rows detected)
- [ ] Wire `pipeline.py` to call the real modules in order:
  1. PDF ingest (`fitz`, 300 DPI)
  2. Vertical morphological kernels → column detection → crop to first 5 columns
  3. Horizontal kernels → row detection
  4. Per-row: OCR name (Tesseract, column 2) + classify attendance (HSV, column 5)
  5. `clean_ocr_name`
  6. Fuzzy match against roster (`rapidfuzz`) — **carry resolved student IDs forward, not just matched name strings**, so downstream reconciliation errors aren't conflated with fuzzy-match errors
  7. Excel export
- [ ] CLI entrypoint: prompt for date (`MM/DD/YYYY`, validated via `pd.to_datetime`), call `OCRPipeline.run()`, write Excel
- [ ] Confirm `OCRPipeline.run(pdf_path) -> pd.DataFrame` has **no interactive prompts inside it** — prompts belong in the CLI layer only, so the same call can later be invoked from a GUI, web route, or API without modification
- [ ] Pass DataFrames between internal pipeline stages (not repeated Excel I/O) to avoid unnecessary disk round-trips
- [ ] End-to-end test: real scanned PDF → correct Excel output

### Explicitly deferred (not MVP blockers)
- Deskew (implemented in notebook but degrades OCR accuracy; not validated end-to-end)
- Automated date extraction (unreliable due to stylized font — CLI prompt is the accepted workaround)

### Guardrail reminder
Your primary constraint is **exe file size**, not OCR accuracy. Don't let accuracy-improvement rabbit holes (e.g. swapping OCR engines) eat MVP time — that's a different goal. (This is also why EasyOCR was rejected — PyTorch dependency bloats the exe.)

---

## Phase 0.5 — ISEP-Aligned Infrastructure (do right after MVP, before or alongside Phase 2)

**Goal:** Demonstrate automation-engineering fundamentals (Bash, Linux, Docker, YAML/CI) — the skills ISEP explicitly trains on (their own postings mention Ansible/YAML-driven automation across infra). This phase wraps the finished MVP; it doesn't require touching pipeline logic.

### Steps, in order
- [ ] **Dockerfile** — containerize the app. This solves a real problem: Tesseract + OpenCV + PyMuPDF as system-level dependencies are exactly what makes local setup painful.
  - [ ] Base image (slim Python)
  - [ ] `apt-get install tesseract-ocr` and any OpenCV system deps
  - [ ] `pip install` from `requirements.txt`
  - [ ] Entrypoint runs the CLI (or later, the API)
  - [ ] Test: `docker build` + `docker run` against a sample PDF, confirm Excel output
- [ ] **GitHub Actions YAML** — CI pipeline, hooks naturally into your existing Git Flow branching
  - [ ] Trigger on push/PR to `dev` and `main`
  - [ ] Steps: checkout → install deps (or build Docker image) → run `pytest`
  - [ ] Optional: lint step (flake8/black)
- [ ] **Bash wrapper** — shell script around the CLI entrypoint
  - [ ] Env setup / dependency checks
  - [ ] Arg parsing (PDF path, date)
  - [ ] Logging output to file
- [ ] Be able to articulate (for ISEP interviews/demo): why Tesseract as a system dependency matters for deployment, what the Dockerfile buys you over local setup, what the CI pipeline catches automatically

---

## Phase 1 (Recap) — Fuzzy Matching + Data Integrity (already scoped into MVP above)
Included in Phase 0 steps — called out separately here because it's a design principle, not just a step: **resolved student IDs must be carried through the pipeline, not just matched name strings.** This is what prevents fuzzy-match errors from masquerading as reconciliation errors in the future DB reconciliation stage.

---

## Phase 2 — GUI

**Goal:** Desktop GUI (`gui/app.py`) invoking `OCRPipeline.run()` directly.

### Why this is low-friction if Phase 0 is done right
The GUI is just a new caller of the same interface. No pipeline changes needed — only:
- [ ] Build `gui/app.py` (framework TBD — Tkinter for simplicity if exe size matters, given your stated constraint)
- [ ] File picker → calls `OCRPipeline.run(pdf_path)` → displays result / triggers Excel export
- [ ] Date input via GUI form instead of CLI prompt
- [ ] Package as `.exe` (this is where the size constraint becomes central — revisit dependency footprint here, especially Tesseract bundling)

---

## Phase 3 — Local Web Interface

**Goal:** `routes.py` invoking the same `OCRPipeline.run()` interface, served locally.

- [ ] Choose framework (Flask for simplicity, or FastAPI if you want it to double as API prep — see below)
- [ ] Upload form → temp file → `OCRPipeline.run()` → download link for Excel
- [ ] No pipeline logic in routes — routes stay thin, orchestration stays in `pipeline.py`

---

## Phase 3.5 — API Layer (skill-building, not immediate priority)

**Goal:** FastAPI-based endpoints, async job handling. This is effectively Phase 3 formalized as a real API rather than a simple web form.

- [ ] `POST /attendance/jobs` — upload PDF, kick off processing (background task)
- [ ] `GET /attendance/jobs/{id}` — poll status/result
- [ ] `GET /attendance/jobs/{id}/export` — return Excel file
- [ ] Background task handling (FastAPI `BackgroundTasks`, or Celery if you want queue practice)
- [ ] Job state tracking (in-memory dict for MVP of this phase; DB or DynamoDB later)

**Note:** Practice target here, not urgent — sequence this after Phase 2 GUI is stable and Phase 0.5 infra is in place.

---

## Phase 4 — Cloud / AWS Integration

**Goal:** Learn AWS SA Associate material by applying it to this project, not toy examples. Treat this as an extension of the API layer — moving *where* pipeline steps run, not rewriting logic.

### Mapping (build in roughly this order)
- [ ] **S3** — landing zone for uploaded PDFs, destination for exported Excel files (easiest starting point: file ingestion → S3 trigger)
- [ ] **Lambda** — run the pipeline itself
  - [ ] Note: Tesseract + OpenCV are too heavy for a plain zip-based Lambda — plan for **container-image Lambda (ECR)** from the start. This mirrors the exe-size lesson: dependency weight matters everywhere, not just desktop packaging.
- [ ] **API Gateway** — fronts the Lambda, same `/attendance/jobs` shape as Phase 3.5, now serverless
- [ ] **SQS** — decouples upload from processing so a large scanned sheet doesn't block the request
- [ ] **DynamoDB** — job status/results tracking, replaces local job-state dict
- [ ] **IAM** — practice least-privilege roles between these services (core SA exam material, easy to under-practice without a real project)

### Concepts to be able to articulate (cert-relevant, not just implementation)
- Compute models: VMs vs containers vs serverless — tradeoffs (cold starts, scaling, cost per request vs per hour)
- Storage models: object vs block vs file storage
- Managed vs self-hosted tradeoffs (e.g. DynamoDB vs self-run Postgres on EC2)
- Elasticity & pay-for-use cost model

---

## Phase 5 — Full Four-Stage Pipeline (long-term)

- [ ] OCR extraction (done in MVP)
- [ ] Fuzzy name matching (done in MVP)
- [ ] DB export cleaning (`db_cleaning.py`)
- [ ] Reconciliation against cleaned DB (`db_reconciliation.py` — name reserved, distinct from current fuzzy-match `reconciliation.py`), with the sign-in sheet as ground truth

---

## Design Principles to Hold Constant Across All Phases

These aren't phase-specific — they're what keeps every phase above from requiring rework of the last:

1. **Interface-first sequencing** — design `OCRPipeline.run()` boundaries before implementing modules, to avoid ambiguities (this is exactly how the `reconciliation.py` / `db_reconciliation.py` naming conflict was avoided)
2. **Stateless functions vs. classes** — pipeline utility functions stay plain functions; classes are reserved for the orchestrator (`OCRPipeline`) and data-shape enforcement (`models.py` dataclasses)
3. **Data integrity by design** — resolved IDs, not just strings, flow through the pipeline
4. **Pass DataFrames internally** — avoid repeated Excel I/O between stages
5. **Don't conflate goals** — exe size ≠ OCR accuracy; MVP speed ≠ architectural correctness. Know which constraint you're solving for at each step.
6. **Notebook stays the source of truth for validated logic** — modular code ports from it, doesn't diverge from it without re-validation

---

## Immediate Next Action

Right now, the only unblocking step is: **write the `pipeline.py` stub with agreed data handoffs**, then fill in calls to `classification.py` and the other modules. Everything else in this document — Docker, CI, GUI, API, AWS — is sequenced *after* that and does not need to be thought about again until Phase 0 is demoable.
