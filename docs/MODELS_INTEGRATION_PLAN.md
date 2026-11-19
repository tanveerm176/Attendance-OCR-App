# Models Integration Plan

## Status

The pipeline, manual review, batch entry points, and Excel export now pass
dataclasses rather than DataFrames between stages. This document records the
implemented behavior and the remaining work; the original plan's proposed
design is not complete in every respect.

## Implemented

- `ocr_pipeline/models.py` defines `AttendanceRecord`, `DailyAttendance`, and
  `AttendanceBatch`. A batch owns an ordered list of sheets, each sheet owns
  its records, and each record carries page and record indexes, OCR text,
  attendance, match details, and review state. Dates are stored per sheet and
  may be `None`. `source_pdf_display_path` allows the headless workflow to
  preserve a host-visible path separately from the input PDF path.
- `review_crop` is excluded from dataclass equality and representation.
  `needs_review` depends on the review flags and the `reviewed` field.
- `ocr_pipeline/constants.py` centralizes the match and review flags.
  `reconciliation.match_name` reconciles one row at a time; the older
  `fuzzy_match_names` DataFrame wrapper is still present and tested.
- `OCRPipeline.run` returns `DailyAttendance`. It matches each normal row
  immediately, validates its attendance status, and copies a grayscale crop
  only for a review flag. Handwritten detections become separate flagged
  records with a copied RGB crop. The sheet date is local to each run.
- Manual review mutates the selected records in place. A confirmed choice
  updates the name, sets the flag to `Resolved - Manual Review`, marks the
  record reviewed, and clears its crop. A skipped record keeps its flag and
  crop for later review. The callback remains injectable.
- The desktop and headless workflows each implement PDF discovery and return
  an `AttendanceBatch`. Desktop review runs between PDFs; the headless workflow
  clears review crops and sets host-visible paths without invoking the GUI.
- `export_attendance` accepts a batch and builds its DataFrame internally from
  column lists. It maps the model fields to the existing workbook headers,
  groups and formats rows by date, rejects empty data or missing dates, and
  writes source hyperlinks when display paths are supplied. Crop arrays are
  not exported.
- Model-based export, review, desktop and headless tests cover these hand-offs.
  Pipeline tests exercise per-run dates, record ordering, normal and
  handwritten review crops, and array-safe model equality.

See [OCR_DATA_FLOW.md](./OCR_DATA_FLOW.md) for the current processing flow.

## Remaining work and deviations

- **Shared batch workflow:** desktop and CLI discovery remain separate; the
  proposed `ocr_pipeline/batch.py` has not been introduced.
- **Date policy:** a missing date remains `None` and export raises an error.
  The planned GUI prompt for a missing date has not been implemented.
- **Memory:** `pdf_to_image` still renders all pages into a list. A lazy page
  iterator and grayscale handwritten crops remain future improvements.
  Skipped desktop-review crops stay on their records; the headless workflow
  discards crops because it does not offer interactive review.
- **Review flag history:** the implementation replaces the original flag upon
  confirmation rather than preserving it and deriving the exported flag from
  `reviewed`. Changing this requires a deliberate behavior decision.
- **Compatibility and cleanup:** the DataFrame reconciliation wrapper remains;
  commented legacy code and unused imports remain in the pipeline/exporter.
  `matplotlib` is still declared and imported.
- **Documentation:** `PROJECT_STRUCTURE.md` has broader pre-existing
  inaccuracies and needs a separate refresh.
- **Headless packaging:** verify the Docker image and CLI in an environment
  with Docker before claiming packaging validation. The batch entry point must
  remain independent of Tkinter and the manual-review module.
- **Future capabilities:** database export and per-page dates remain out of
  scope. If PDFs can contain mixed dates, introduce a page-level date model
  before relying on one date per PDF.
