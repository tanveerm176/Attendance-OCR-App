# Models Integration Plan

This plan replaces DataFrame hand-offs between pipeline stages with the dataclasses in `ocr_pipeline/models.py`. Records and sheets carry the data through the run, and DataFrames exist only inside the Excel exporter. A database writer is deferred; it can be added later as a sibling of `io_utils/excel_output.py`.

## Goals

- Pass typed objects (`DailyAttendance`, `AttendanceRecord`) between stages instead of DataFrames.
- Reduce memory: keep image crops only for records that need manual review.
- Remove shared mutable state (`DailySheet.sheet_date` is currently written on the class, so one PDF's date can leak into the next).
- Keep Tkinter out of the models, the batch workflow, and anything the headless Docker image imports.

## Non-goals (for now)

- Database export.
- New subpackages (`stages/`, `application/`) or a `src/` layout.
- Changing Docker, `pyproject.toml` packaging, or `main.spec`. All new code stays in `ocr_pipeline/` and `io_utils/`, which are already copied and packaged.

## Target `models.py`

```python
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

import numpy as np


@dataclass
class AttendanceRecord:
    page_index: int
    ocr_name: str
    cleaned_name: str
    matched_name: str | None
    match_score: float
    match_flag: str
    attendance_status: Literal["Present", "Absent", "EMPTY CELL"]
    is_handwritten: bool = False
    reviewed: bool = False
    # Only populated for records that need manual review; cleared afterwards.
    review_crop: np.ndarray | None = field(default=None, repr=False, compare=False)


@dataclass
class DailyAttendance:
    source_pdf: Path
    sheet_date: datetime | None = None
    # Path written to Excel hyperlinks (e.g. a host path when running in Docker).
    source_pdf_display_path: str | None = None
    records: list[AttendanceRecord] = field(default_factory=list)
```

Design notes:

- `review_crop` uses `repr=False, compare=False`. Dataclass `==` on NumPy arrays raises `ValueError` (ambiguous truth value), and printing pixel data is expensive.
- Records are mutable because manual review updates `matched_name`, `match_flag`, and `reviewed`.
- `sheet_date` is optional so a missing or unparseable date is an explicit state.
- `source_pdf_display_path` keeps the container path separate from the path shown to users (`--source-path-root`).
- `reviewed` preserves the original `match_flag` after a manual decision. The exporter writes `Resolved - Manual Review` for reviewed records instead of overwriting the flag.
- Per-page dates are not modeled. If a single PDF can contain pages with different dates, add `sheet_date` to a page-level object later.

Open naming decision: the current DataFrame columns are `ocr_raw`, `matched_score`, `flag`, `attendance`. The model uses `ocr_name`, `match_score`, `match_flag`, `attendance_status`. Use the model names everywhere in code and map to the existing Excel headers in one place (`OUTPUT_COLUMNS` in `io_utils/excel_output.py`).

## Shared constants

Create `ocr_pipeline/constants.py` (or add to `reconciliation.py`) with the flag values currently scattered across modules:

- `STRONG_MATCH_LABEL`, `LOW_MATCH_LABEL`, `EMPTY_ROW_LABEL`, `RESOLVED_MANUALLY_FLAG`
- `NEED_MANUAL_ENTRY_FLAG = "NEED-MANUAL-ENTRY"`
- `WRITTEN_NAME_MARKER = "WRITTEN NAME DETECTED"`
- `REVIEW_FLAGS`: the set of flags that require review (`OCRExtractionError`, `NoMatchFoundError`, `LOW_MATCH_LABEL`, `NEED-MANUAL-ENTRY`). Currently defined in `manual_review.py`.

`EMPTY CELL` and `Strong Match` do not require review, so they never keep a crop.

## Memory strategy

Most of the saving comes from reconciling each record immediately, not from the model shape alone.

1. **Reconcile per record, right after OCR.** Match each name inside the row loop so the flag is known immediately. Store the crop only when `match_flag in REVIEW_FLAGS`; otherwise drop it.
2. **Handwritten regions follow the same rule.** They are always `NEED-MANUAL-ENTRY`, so their crops are kept for review.
3. **Always `.copy()` a kept crop.** A NumPy slice is a view that keeps the whole table image alive. This includes the handwritten crop, which currently holds `written_names.copy()` only for the review list.
4. **Store grayscale crops.** The handwritten crop is currently RGB (three times the size). The review UI converts for display.
5. **Clear after review.** Set `review_crop = None` and `reviewed = True` once a record is resolved. Skipped records lose their crop once the review window closes.
6. **Render pages lazily.** Add `iter_pdf_pages(pdf_path)` to `ocr_pipeline/ingestion.py` as a generator so only one full-page image exists at a time. Keep `pdf_to_image()` as a list wrapper so `tests/test_ingestion.py` keeps passing.

Expected peak memory: one page image plus that page's table crops, plus a handful of small review crops, rather than every crop for the whole PDF.

## Integration steps

Each step should be its own commit, with the test suite passing after each one.

### 1. Update `models.py` and add constants

- Replace `models.py` with the target above.
- Add the shared constants and import them from `reconciliation.py` and `manual_review.py`.
- Remove the duplicate `LOW_MATCH_SCORE_FLOOR` in `reconciliation.py`; `PipelineConfig.low_match_floor` is the single source of truth.

### 2. Make reconciliation per-record

- Add `match_name(raw_name, attendance_status, roster, threshold, low_match_floor)` in `reconciliation.py`. It returns the cleaned name, matched name, score, and flag.
- Preserve existing behavior: the handwritten marker returns `NEED-MANUAL-ENTRY`; a blank name in an `EMPTY CELL` row returns `EMPTY CELL`; blank or very short names return `OCRExtractionError`; an empty roster result returns `NoMatchFoundError`.
- Keep `fuzzy_match_names(df, ...)` as a thin wrapper that calls `match_name` until its callers and tests are migrated; remove it at the end.

### 3. Convert `OCRPipeline.run` to return `DailyAttendance`

- Build one `AttendanceRecord` per row (replaces the parallel `ocr_names`, `attendance_statuses`, and `review_crops` lists, which could fall out of step).
- Call `match_name` per row and keep the crop only for review flags.
- Replace `DailySheet.sheet_date = ...` with a local `sheet_date`, and return it on `DailyAttendance`. Decide a policy for PDFs where no date is detected (leave `None` and let the caller fail or fall back).
- Remove unused imports (`matplotlib`, `mpimg`, `rotate`) and drop `matplotlib` from `pyproject.toml` if nothing else uses it.
- Optionally switch the page loop to `ingestion.iter_pdf_pages`.

### 4. Convert manual review

- `review_flagged_records` takes and returns `list[AttendanceRecord]` (or a `DailyAttendance`), selecting records with `match_flag in REVIEW_FLAGS and not reviewed`.
- Replace positional `iat` lookups with attribute access.
- On confirmation set `matched_name`, `reviewed = True`, and `review_crop = None`.
- Keep the injectable `dialog` parameter used by tests. Tkinter stays in this module for now.

### 5. Add the shared batch workflow

- Create `ocr_pipeline/batch.py` with a function such as `process_pdf_folder(folder, pipeline, *, review_callback=None, source_path_root=None) -> list[DailyAttendance]`.
- It handles PDF discovery (case-insensitive sort), running the pipeline, the optional review callback, and setting `source_pdf_display_path`.
- It must not import Tkinter or `manual_review`; review is passed in as a callback so the headless image keeps working.
- `main.py` supplies the folder picker and review callback; `ocr_pipeline/batch_cli.py` supplies argparse and no review. Keep `batch_cli.main` in place so the `attendance-ocr-batch` entry point is unchanged.

### 6. Update the Excel exporter

- `export_attendance` accepts `list[DailyAttendance]` and flattens it to a DataFrame internally, so formatting code is unchanged.
- Map model fields to the existing output headers in `OUTPUT_COLUMNS`.
- Write `Resolved - Manual Review` for reviewed records.
- Keep the existing validation (missing date, empty data).

### 7. Update tests and docs

- Update tests that build DataFrames: `test_reconciliation.py`, `test_manual_review.py`, `test_batch_cli.py`, `test_main_batch.py`, `test_excel_output.py`.
- Add tests for: crops kept only for review flags, handwritten records keep crops, crops cleared after review, per-PDF dates not leaking between PDFs, and `DailyAttendance == DailyAttendance` not raising.
- Update `docs/OCR_DATA_FLOW.md` (its DataFrame flow and memory notes) and `docs/PROJECT_STRUCTURE.md`, which is already out of date.

## Docker and packaging checks

No Dockerfile or packaging change is required, since everything stays in `ocr_pipeline/` and `io_utils/`. After step 5 and again at the end:

```powershell
docker build -t attendance-ocr:local .
docker run --rm attendance-ocr:local --help
```

The headless image does not install Tkinter, so confirm nothing imported by `batch.py` or `batch_cli.py` pulls in `manual_review` at import time.

## Risks and things to watch

- **Behavior parity.** The per-record reconciliation must produce the same flags and scores as `fuzzy_match_names` for the same inputs; port the existing tests first.
- **Date policy.** Today a missing date silently reuses the previous PDF's date. After the change the date may be `None`, so the exporter and batch loop need an explicit decision.
- **Crop views.** Forgetting `.copy()` on a kept crop pins an entire page image in memory and defeats the optimization.
- **Roster-dependent review.** The review dialog needs the roster; pass it from the caller rather than storing it on records.

Design points
Validate the status and flag values at the edges. Literal is only checked by a type checker. The classifier and reconciliation return plain strings, so a typo like "Presnt" would reach the exporter at runtime. Consider an Enum (AttendanceStatus(str, Enum)) so values are fixed and still compare equal to strings, or keep Literal and add a test that asserts the classifier only returns those three values.

reviewed and match_flag together can contradict each other. A record could be reviewed=True with a Strong Match flag, or reviewed=False with a resolved flag. Pick one rule, for example "the exporter derives the final flag from reviewed", and document it so the Excel highlighting (which keys on the flag text) stays consistent. The current row colors depend on Low Match - Needs Review and NEED-MANUAL-ENTRY; a reviewed record should no longer get the gold highlight.

Skipped records are different from untouched ones. Skipping in the review UI currently leaves the flag unchanged. With the new model that means reviewed stays False but the crop is cleared. That's fine for export, but don't use review_crop is None as a "needs review" test. Use the flag plus reviewed.

Don't store the roster or config on the model. Pass them in, as the plan says. Keeping the models as plain data makes them easy to build in tests.

Add a convenience property rather than repeating logic. For example needs_review on AttendanceRecord, defined as match_flag in REVIEW_FLAGS and not reviewed. It prevents the review step, batch loop and tests from each reimplementing it. If you do this, REVIEW_FLAGS must live in a module that models.py can import without a cycle (constants, not manual_review).

Practical pitfalls
datetime vs date. sheet_date is a datetime from strptime. The exporter normalizes to midnight, so that's fine, but mixing in a date later will break the groupby.
Mutable default and shared records. field(default_factory=list) is correct. Don't share one list between DailyAttendance objects.
Pickling and multiprocessing. If you ever parallelize PDFs, records carrying NumPy crops pickle fine, but large crops make that slow. The memory strategy helps here too.
Row order. The flat export relies on records being in sheet order. Keep records in a list and don't reorder them during review.
Page index. It's currently only informational. Use it in a "source page" column if you later want a trace back to the scan.
Database later. The model fields map directly to columns, and review_crop should be excluded. A SQLAlchemy or dataclasses.asdict conversion would copy the array, so write an explicit conversion that skips it, since asdict deep-copies NumPy arrays.
Tests. Add small builders or a factory fixture in tests/conftest.py so tests aren't repeating all nine fields for every record.
Not needed yet
A separate ReviewDecision object, per-page models, and an enum for flags are reasonable later, but none is required for this migration.

I'd add the needs_review property and the status check (points 1 and 5) to the plan, as they affect how steps 3 and 4 are written. I can update the plan file if you'd like.

## Future work (not in this plan)

- Database writer alongside `excel_output` (choice of database undecided).
- Per-page date or page-level models if a PDF can mix dates.
- Moving `manual_review.py` out of `ocr_pipeline/` once a second UI exists.
