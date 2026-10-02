# Attendance OCR App — Current Status and Future Work

This document describes the application as implemented in the repository, using `main.py` as the entry point. It reconciles the older descriptions in `APP_OVERVIEW_MVP.md`, `MVP_ROADMAP.md`, `PROJECT_STRUCTURE.md`, and `Attendance-OCR-App-Roadmap.md` with the current code. The roadmap documents are useful planning notes, but some of their status labels and file descriptions are stale.

## At a glance

The app is a Python PDF attendance-sheet processor. Its core `OCRPipeline` renders the pages of a selected PDF, detects table lines, extracts names with Tesseract, classifies attendance marks from their color, fuzzy-matches names against a text roster, and returns a pandas DataFrame. The entry point prints that DataFrame and attempts to export it to an Excel workbook.

**Current user workflow is not yet the intended one-click experience:** `main.py` opens a file picker for one PDF. The date prompt exists but is commented out. The app does not currently select a folder or process a folder batch. The imported GitHub updater is not called. A desktop date-entry form, folder picker, progress display, and tested release/update flow remain future work.

## Current execution path (`main.py`)

When run as a Python script (or packaged executable):

1. `python-dotenv` loads values from `.env` before the OCR modules are imported.
2. `prompt_for_pdf_path()` opens a Tkinter dialog for a single PDF. Canceling raises `ValueError`.
3. A timer starts, and `build_roster()` reads the roster file configured in `io_utils/roster_input.py` (`data/SONYC2_roster.txt`).
4. `PipelineConfig` is created with that roster, and `OCRPipeline.run(pdf_path)` processes the selected PDF.
5. The resulting DataFrame is printed in full.
6. `build_excel_output()` creates `./output` relative to the current working directory and forms an `attendance_<date>.xlsx` path. `export_attendance()` writes the DataFrame with pandas/openpyxl.
7. The app prints a row-count/output message and elapsed time.

The `prompt_for_date()` function validates `MM/DD/YYYY`, but its call is commented out. Instead, `pipeline.py` may set `DailySheet.sheet_date` by OCR when it identifies a sufficiently tall first-page header. `main.py` then uses that class attribute to name the export. The `pdf_path` parameter to `build_excel_output()` is currently unused.

### Important current blocker

`DailySheet` is a dataclass whose `sheet_date` field has no class-level default. `main.py` accesses `DailySheet.sheet_date` as a class attribute after pipeline execution, while `pipeline.py` only assigns it when it detects the main-page header and successfully parses the printed date. Therefore, on PDFs/pages for which that assignment does not happen (or date OCR/parsing fails), export-path creation can fail rather than prompting for a date. The intended reliable flow is to collect/validate the date from the user and pass it explicitly through the run/output path, or consistently return the detected date as pipeline data with a well-defined fallback.

## Processing pipeline

### Current data flow

```
main.py starts
   |
   +--> Load environment variables from .env
   |
   +--> Open Tkinter file picker and select one PDF
   |
   +--> Load data/SONYC2_roster.txt
   |
   +--> Create PipelineConfig and OCRPipeline
   |
   +--> OCRPipeline.run(pdf_path)
		  |
		  +--> Render every PDF page at configured DPI (PyMuPDF)
		  |
		  +--> For each page:
		  |      Convert to grayscale and estimate/correct skew
		  |      Detect vertical table lines and crop to table columns
		  |      Detect horizontal row lines and inspect page header
		  |      Read the printed date from a detected main-page header
		  |      For each row:
		  |         Crop name cell --> preprocess and read with Tesseract
		  |         Crop attendance cell --> classify ink color
		  |      OCR-check the handwritten section at the bottom
		  |
		  +--> Clean OCR names and fuzzy-match them against the roster
		  |
		  +--> Build reconciled DataFrame and add Date column
   |
   +--> Return DataFrame to main.py and print it
   |
   +--> Build output path under ./output
   |
   +--> Export DataFrame to .xlsx (pandas/openpyxl)
   |
   +--> Print row count and elapsed time
```

The diagram follows the current single-PDF runtime path from selection through Excel export. The roster is loaded by `main.py` and passed into the pipeline configuration; the pipeline returns the reconciled DataFrame for export.

`OCRPipeline.run(pdf_path)` is the orchestrator in `ocr_pipeline/pipeline.py`:

1. **PDF ingestion:** `ingestion.pdf_to_image()` opens the PDF with PyMuPDF and renders every page at configured `DPI` (default 300) into RGB NumPy arrays.
2. **Deskew:** each page is converted to grayscale, estimated for skew with a Hough-line approach, and rotated if the angle is nonzero. Deskew is implemented and currently called; it is not merely an empty placeholder. Orientation correction via `rotate.py` is imported but commented out.
3. **Table detection and crop:** OpenCV-based helpers detect vertical lines. The pipeline validates the line count and crops the page to the configured table columns. It then detects horizontal lines and checks that at least one row can be established.
4. **Header and page handling:** the pipeline removes a leading line in a specific edge case, examines the header region, and skips configured header rows for a main page. For a tall header it calls `detect_date.detect_sheet_date()` and assigns the result to `DailySheet.sheet_date`. A large final row gap is treated as a DYCD logo/written-name section boundary.
5. **Row extraction:** each detected row is cropped. The name cell is converted to grayscale and sent to Tesseract; the attendance area remains RGB and is passed to `classification.classify_attendance()`.
6. **Handwritten-name detection:** the area below the last detected table row is OCR-checked. If text is detected, the pipeline appends a `WRITTEN NAME DETECTED` row with attendance `Present` for manual follow-up.
7. **Name reconciliation:** a DataFrame is built with `ocr_raw` and `attendance`; `reconciliation.fuzzy_match_names()` adds `cleaned_name`, `matched_name`, `matched_score`, and `flag`. It uses RapidFuzz `token_sort_ratio`, with defaults of 80 for a strong match and 30 for the low-match floor.
8. **Date column:** the pipeline inserts `Date` as the first DataFrame column using `DailySheet.sheet_date`, then returns the DataFrame.

The expected result is an extracted/reconciled attendance table. The code does not currently add a source filename column or combine multiple selected PDFs into one workbook.

## Main modules and responsibilities

| Area | Implemented responsibility |
| --- | --- |
| `main.py` | Single-PDF Tkinter file picker, roster/config setup, pipeline call, console output, Excel export, timing. The date prompt and updater call are present only as unused/commented functionality. |
| `ocr_pipeline/pipeline.py` | Coordinates multi-page processing, geometry, OCR, attendance classification, name matching, and date insertion. |
| `ocr_pipeline/ingestion.py` | Renders all PDF pages as RGB arrays using PyMuPDF and `DPI`. |
| `ocr_pipeline/table_detection.py`, `img_cropping.py` | Detect table grid coordinates and crop image regions. |
| `ocr_pipeline/deskew.py` | Estimates and corrects page skew; called by the pipeline. |
| `ocr_pipeline/rotate.py` | Orientation correction utility; currently not invoked (calls are commented out). |
| `ocr_pipeline/ocr.py` | Image preprocessing, Tesseract OCR, empty-result retry, and handwritten-section text detection. `TESSERACT_CMD` can override the executable path; otherwise Tesseract must be discoverable on `PATH`. |
| `ocr_pipeline/classification.py` | Uses HSV and RGB channel comparisons to classify marks as `Present`, `Absent`, or `EMPTY CELL`. |
| `ocr_pipeline/reconciliation.py` | Cleans OCR text, fuzzy-matches the roster, and adds match scores and review/error flags. |
| `ocr_pipeline/detect_date.py` | Attempts to OCR and parse a printed date from a page header. This is used conditionally and is not a reliable user-input replacement yet. |
| `ocr_pipeline/config.py` | Pipeline column boundaries, roster, fuzzy-match thresholds, and environment-derived `DPI`, `S3_BUCKET`, and `OUTPUT_DIR`. In current code, `DPI` is used; `S3_BUCKET` and `OUTPUT_DIR` are not wired into the processing/export path. |
| `ocr_pipeline/models.py` | Declares `AttendanceRecord` and `DailySheet` dataclasses. Current pipeline output is a DataFrame, not a list of these record instances. |
| `io_utils/roster_input.py` | Loads and strips lines from the configured local roster text file. It does not currently accept a user-selected roster path or validate an empty/duplicate roster. |
| `io_utils/excel_output.py` | Writes the DataFrame to `.xlsx` via `to_excel`; no formatting or styling is applied. |
| `updater.py` | Queries the GitHub latest-release API, compares versions, prompts, and can replace/relaunch a frozen executable. Its implementation exists, but `main.py` currently imports `check_for_update` without invoking it. |
| `reporting/summary.py`, `reporting/logger.py` | Empty modules; no summary or audit log is generated by these modules. |

## Configuration and runtime requirements

- `DPI` defaults to 300 and controls PDF render resolution.
- `TESSERACT_CMD` may be set in the environment or `.env`; without it, the Tesseract executable must be on `PATH`.
- The roster is currently loaded from `data/SONYC2_roster.txt` relative to the project, not selected at runtime.
- Excel output is written beneath `./output`, relative to the process's working directory. `OUTPUT_DIR` is currently not used by `main.py`.
- Runtime dependencies include the Python packages used by the code (including PyMuPDF, OpenCV, NumPy, pandas, pytesseract, RapidFuzz, python-dotenv, and openpyxl) plus the Tesseract executable.
- The docs mention a PyInstaller spec/build path, but a successful packaged build and the required bundled/external Tesseract setup are not verified by this status review.

## Known limitations and risks

- The app accepts one PDF, not a scan folder or a batch of PDFs.
- The intended user-entered date is not currently requested. Date extraction only occurs on a particular detected page-header path and can raise a parsing error.
- The date is stored on a dataclass type rather than passed as explicit per-run data. This creates fragile state and can make the output path or date column fail, especially when processing another document in the same process.
- `check_for_update()` is imported but not called, so current launches do not check for updates.
- The updater's prompt uses `input()`, which is not an appropriate user interaction in a windowed GUI/subsystem build; update confirmation and failure reporting should use the eventual UI. The update mechanism also needs end-to-end testing on the target Windows executable before distribution.
- Tesseract is an external executable and must be available on staff computers or deliberately bundled and configured.
- The pipeline's output schema uses `ocr_raw`, `attendance`, and `matched_score`; some older docs describe different names such as `ocr_name`, `status`, or `match_score`.
- Classification, OCR, date detection, line detection, and deskew can be sensitive to scan quality/layout. Human review of low-confidence and handwritten-name rows remains necessary.
- A date OCR/parsing exception currently has no documented recovery flow, and pipeline failures are not caught by a user-facing error handler in `main.py`.
- There is no folder-batch summary, persistent run log, or configurable output location in the current entry point.

## Future work (not implemented or not complete)

These items consolidate unfinished work noted across the docs and compare them with the current code. “Partial” means a related implementation exists, but the described feature is not complete end-to-end.

### Priority 1 — Make the current single-run workflow reliable

- [ ] Restore a validated date prompt as the reliable fallback; pass the date explicitly instead of relying on mutable `DailySheet.sheet_date` class state.
- [ ] Define a clear date policy: use the detected date when OCR succeeds, and provide a manual-entry fallback when date detection fails. Add tests for invalid/missing date and multi-page PDFs.
- [ ] Fix and test output-path generation so export always works, and decide whether output is relative to the executable/project or a user-selected folder. Wire `OUTPUT_DIR` or remove/document it.
- [ ] Verify the actual DataFrame schema and workbook output with a sample PDF; update consumer expectations to the implemented column names.
- [ ] Add a friendly error path for canceled selection, bad/corrupt PDFs, missing roster, missing Tesseract, table-detection failures, date failures, and Excel write failures.
- [ ] Validate the roster (file exists, non-empty entries, duplicates) and surface configuration/dependency problems before processing.
- [ ] Add a maximum-skew threshold: reject PDFs whose detected skew is too large for reliable correction, with a clear error explaining that excessive skew can cause vertical-line detection to fail.
- [ ] Add persistent roster storage or a cache so the student roster is retained between runs, with a clear way to refresh it when the source roster changes.
- [ ] Fully integrate `AttendanceRecord` and `DailySheet` into the pipeline's inputs/outputs instead of declaring the dataclasses while returning only a DataFrame.
- [ ] Add/finish focused tests for `classification`, `reconciliation`, `pipeline`, date handling, output generation, and failure cases; run a manual end-to-end audit against a known sheet.

### Priority 2 — Deliver the intended desktop staff workflow

- [ ] Integrate the Activity Level Audit script into this project and define how it fits into the attendance-processing workflow.
- [ ] Replace the single-PDF picker with a folder picker and collect/sort all PDFs in that folder; handle an empty folder and define file ordering.
- [ ] Provide date entry in the UI (at minimum a validated date field) and decide whether one date applies to a batch or each sheet can have its own date.
- [ ] Add processing feedback (selected folder/files, progress, completion, output location) and user-friendly error messages.
- [ ] Write all processed PDFs into one combined workbook; include `source_file` per row and decide how to handle individual PDF failures.
- [ ] Maintain one persistent Excel workbook and update it on each run instead of creating a new workbook each time; define how new rows are appended or existing records are updated without duplicating attendance data.
- [ ] Show a GUI popup when handwritten names are detected, identifying the affected sheet and prompting staff to review or manually enter the name.
- [ ] Implement `reporting.summary` and `reporting.logger` for row/match/flag counts, run metadata, errors, and output path.
- [ ] Choose and implement the desktop UI approach (Tkinter is already used for file selection); package and test the actual one-click Windows executable, including Tesseract and roster placement/configuration.

### Priority 3 — Safe GitHub releases and auto-update

- [ ] Call the updater from application startup only after defining a UI-safe update/skip/error experience; do not block or crash the attendance workflow when GitHub is unreachable.
- [ ] Ensure the `VERSION` file is bundled and readable in the packaged application, and verify that release tags/assets follow the updater's expected format (semantic version tag and `.exe` asset).
- [ ] Test latest-release lookup, no-update path, declined update, accepted update, network failure, download failure, and Windows replacement/relaunch on a disposable test executable.
- [ ] Make update confirmation and progress compatible with the desktop UI rather than relying on console `input()`.
- [ ] Add GitHub Actions CI for dependency installation and tests; add a tag-triggered release workflow to build the Windows executable and attach it to a GitHub Release only after tests pass. Confirm the build runner and Tesseract packaging strategy.
- [ ] Document developer release steps (version bump, tag, release asset, rollback) and the staff update behavior.

### Longer-term roadmap

- [ ] Resolve roster names to DYCD database names/student IDs using a reviewed mapping table, then implement separate database cleaning and sheet-vs-database reconciliation modules. This is distinct from the existing OCR-name-to-roster fuzzy match.
- [ ] Evaluate orientation correction (`rotate.py`) and keep/tune deskew only after validation against representative scans.
- [ ] Improve Excel presentation (review highlighting, useful column order, filters, and/or separate summary sheet) after the plain export is reliable.
- [ ] Add a local web interface that runs on localhost and calls the same pipeline; keep web routes/UI code separate from OCR processing.
- [ ] If needed, add an API/job interface and background processing after a GUI/web workflow is stable.
- [ ] Explore Docker/CI infrastructure and later AWS services (S3, container-based Lambda, API Gateway, SQS, DynamoDB, IAM) as explicitly later learning/deployment phases, not current app capabilities.

## Documentation reconciliation notes

- `MVP_ROADMAP.md` and `PROJECT_STRUCTURE.md` contain stale “placeholder/not implemented” statuses for features now present, including classification, reconciliation, pipeline orchestration, roster loading, and Excel export. They also describe older package paths such as `io/` instead of the current `io_utils/`.
- `Attendance-OCR-App-Roadmap.md` marks some MVP steps complete, but the current `main.py` contradicts its claim that a validated manual date prompt is active and that the end-to-end CLI flow is complete. Treat the checklist as historical planning, not proof of current behavior.
- `APP_OVERVIEW_MVP.md` contains useful architecture and future-phase material, but its workflow/schema descriptions are not fully aligned with the current code. This document records the code-backed status as reviewed.
- The notes in `auto-update-and-phases.txt` describe the intended executable/release/update path; the updater code exists, but the entry point does not currently activate it and packaging/release automation remains to be validated.
- `rosterName_dbName_Issue.txt` describes future roster-to-database/student-ID mapping. That mapping and the separate database reconciliation stage are not implemented in this app.
