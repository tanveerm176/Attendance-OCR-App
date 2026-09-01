# Attendance OCR App — Claude Working Notes

## Project purpose

This project automates processing for scanned attendance sheets: it renders PDFs to images, detects the table grid, extracts text via OCR, classifies attendance marks, reconciles names against a roster, and exports the final results to Excel.

The architecture is intentionally built around a clean pipeline boundary:

- `OCRPipeline.run(pdf_path) -> pd.DataFrame` is the core interface.
- The CLI layer is responsible for prompts and output handling.
- GUI, web, and API layers should call the same pipeline without modifying pipeline internals.

## Current MVP status

As of the current roadmap review, the project is past Step 2 of the MVP sequence.

Current interpretation of the roadmap:

- Step 1: `ocr_pipeline/classification.py` — in progress / completed enough to unblock the next stage
- Step 2: `ocr_pipeline/reconciliation.py` — finished
- Next: Step 3 (`ocr_pipeline/exceptions.py`), then Step 4 (`ocr_pipeline/models.py`), then Step 5 onward through the orchestrator and CLI wiring

This means the project is no longer at a pure “all placeholders” stage. It has moved past the name-cleaning and fuzzy-match layer and is ready for the structured error-handling and orchestration layer that sits immediately after.

## Architecture summary

### Core pipeline

- `ocr_pipeline/ingestion.py`: PDF to image rendering
- `ocr_pipeline/table_detection.py`: table boundary detection using vertical/horizontal kernel-based line detection
- `ocr_pipeline/img_cropping.py`: crop helpers for cells/regions
- `ocr_pipeline/ocr.py`: OCR extraction for table cells
- `ocr_pipeline/classification.py`: attendance classification from the sign-in cell
- `ocr_pipeline/reconciliation.py`: OCR name cleaning and roster fuzzy matching

### Data and orchestration

- `ocr_pipeline/exceptions.py`: expected to hold a small MVP exception hierarchy
- `ocr_pipeline/models.py`: expected to define data classes for pipeline outputs
- `ocr_pipeline/pipeline.py`: orchestrator that should be built in two passes: skeleton first, then real module wiring
- `main.py`: CLI entry point that should call the pipeline, prompt for date, and export Excel output

### I/O and reporting

- `io/roster_input.py`: load and validate roster data from `data/student_roster.txt`
- `io/excel_output.py`: export results to `.xlsx`
- `reporting/summary.py` and `reporting/logger.py`: run summary and logging

## Recommended execution order for next work

1. Finish the MVP exception definitions.
2. Add the MVP dataclasses for pipeline records.
3. Add the `PipelineConfig` dataclass and roster-loading utility.
4. Build the `OCRPipeline` orchestrator skeleton and then wire the real calls.
5. Finalize `main.py` orchestration.
6. Add export and summary/reporting support.
7. Only after the end-to-end path is demoable, move to GUI/web/API/cloud phases.

## Guardrails from the roadmap

- Keep `OCRPipeline.run(pdf_path) -> pd.DataFrame` as the core, prompt-free interface.
- Do not put interactive prompts inside the pipeline itself.
- Keep data transfer as in-memory DataFrames between stages; avoid repeated Excel I/O.
- Keep the model/logic scoped to outlined MVP tasks; do not prematurely overbuild the cloud/API layers.
- The repo’s long-term phases should be additive, not competing with the MVP.

## Known discrepancies across the docs

The three documents are aligned on the long-term project direction, but they are not equally current or equally detailed.

### 1. Different levels of granularity

- [docs/Attendance-OCR-App-Roadmap.md](docs/Attendance-OCR-App-Roadmap.md) is a broad strategic roadmap and phase tracker.
- [docs/MVP_ROADMAP.md](docs/MVP_ROADMAP.md) is the detailed execution checklist for the current MVP.
- [docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md) is a repository inventory and architecture summary, not a task tracker.

This means the roadmap docs are more actionable than the project-structure doc, and the project-structure doc is more archival than current-state.

### 2. Phase naming and sequencing are not perfectly aligned

- The larger roadmap refers to “Phase 0 — MVP (current focus)” and then later “Phase 0.5 — ISEP-Aligned Infrastructure.”
- The MVP roadmap describes a more concrete step-by-step sequence: Step 1 through Step 10, with clear dependency order.

These are compatible, but the broader roadmap is higher level while the MVP roadmap is the operational plan.

### 3. `PROJECT_STRUCTURE.md` is partly stale relative to the current roadmap

The project structure document describes the repo as if several components are still just placeholders, which is fine for a project inventory. However, it is less current than the detailed roadmap because it does not reflect the MVP step progression or the fact that `reconciliation.py` is now a current target and not simply a reserved placeholder.

### 4. Example/sample asset naming mismatch

[docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md) mentions:

- `tests/sample_scans/sonyc-test.pdf`

But the workspace structure shown in the session lists sample files like:

- `tests/sample_scans/df_fuzzy_names.csv`
- `tests/sample_scans/OCR_Name_Attendance.csv`

This suggests the project structure doc is either stale or references an older sample asset that has since been replaced.

### 5. `main.py` status is described differently across docs

- [docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md) says `main.py` “currently performs the update check and documents the planned end-to-end batch workflow.”
- [docs/MVP_ROADMAP.md](docs/MVP_ROADMAP.md) says Step 9 is to rewrite `main.py` to use the orchestrator and actual pipeline flow.

These are not contradictory so much as they describe different stages: the project structure doc captures the repo as it exists today, while the roadmap describes the intended next revision.

## Working principle for future agent work

When implementing or editing in this repo, follow the detailed MVP roadmap as the primary source of truth for sequence and scope. Treat [docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md) as context for the repo layout, but not as the authoritative status update for execution order.

If a new task is being planned, prefer:

- [docs/MVP_ROADMAP.md](docs/MVP_ROADMAP.md) for exact remaining steps
- [docs/Attendance-OCR-App-Roadmap.md](docs/Attendance-OCR-App-Roadmap.md) for strategic/phased context
- [docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md) for file organization and current repo shape
