# Attendance OCR App — Current Status and Future Work

This document describes the application as implemented in the repository, using `main.py` as the entry point. It reconciles the older descriptions in `APP_OVERVIEW_MVP.md`, `MVP_ROADMAP.md`, `PROJECT_STRUCTURE.md`, and `Attendance-OCR-App-Roadmap.md` with the current code. The roadmap documents are useful planning notes, but some of their status labels and file descriptions are stale.

## At a glance

The app is a Python PDF attendance-sheet processor. Its core `OCRPipeline` renders PDF pages, detects table lines, cleans red strikethroughs from printed-name crops, extracts names with Tesseract, classifies attendance marks by color, and fuzzy-matches names against a roster. It filters detected table intervals using typical row height and reserves a bounded region for possible write-in names.

`main.py` opens a folder picker and processes PDF files directly inside the selected folder in case-insensitive filename order. It concatenates their DataFrames into one result and writes one Excel workbook named `<folder>_MM-DD-YYYY.xlsx`, using the current date for the filename. The workbook contains one worksheet per detected sheet date, with styled headers and rows, formatted date cells, and consistent auto-sized column widths. The date prompt exists but is not part of this workflow. The imported GitHub updater is not called; a progress display and tested release/update flow remain future work.

### Work completed in this session

- Added HSV-based red-ink detection and inpainting for printed-name image crops before grayscale OCR, preserving the original image for attendance classification.
- Added OCR-result cleanup for the common strikethrough artifacts `™`, `~`, `-`, `—`, and `.`, for both primary and fallback Tesseract results.
- Added median-row-height segmentation to ignore unusually short line artifacts and oversized/footer intervals as student rows. A large gap after the last normal row is used as a bounded write-in crop; otherwise a limited region below the last detected line is checked.
- Added folder-based PDF batch processing, concatenation, and an output filename based on the selected folder name and processing date.
- Added per-date Excel worksheets. Worksheet names use `MM-DD-YYYY` because Excel does not permit `/` in worksheet names; date cells display as `MM/DD/YYYY`.
- Added workbook styling: centered values, a distinct header, thin borders on populated cells, content-based column widths shared across date sheets, and row highlights. Present is blue (`#8DB4E2`), Absent is red (`#DA9694`), and low-match/manual-entry rows are gold (`#FFC000`). Cells do not wrap and row heights are not manually adjusted.
- Added focused tests for OCR cleanup, row segmentation, folder batching, workbook sheets, styles, and input validation.

### Validation performed

- `tests/test_ocr.py` with `tests/test_reconciliation.py`: 9 passed.
- Focused row-segmentation tests: 3 passed.
- `tests/test_main_batch.py`: 3 passed.
- `tests/test_excel_output.py`: 4 passed, including date sheets, formatting, colors, and shared column widths.
- A sample workbook/PDF comparison confirmed that typical-row filtering removed the two blank trailing rows and the footer-triggered false write-in marker; the remaining 85 extracted rows matched the workbook's valid records.
- Pylance checks reported no errors for the changed Python files, and `git diff --check` passed.
- The entire `test_table_detection.py` module is not cleanly runnable as-is: 8 existing image-based tests refer to a `sample_image` fixture that is not defined; the 3 new row-splitting tests pass independently.

## Current execution path (`main.py`)

When run as a Python script (or packaged executable):

1. `python-dotenv` loads values from `.env` before the OCR modules are imported.
2. `prompt_for_pdf_folder()` opens a Tkinter dialog to select a folder. Canceling raises `ValueError`.
3. A timer starts, and `build_roster()` reads the roster file configured in `io_utils/roster_input.py` (`data/SONYC2_roster.txt`).
4. `PipelineConfig` is created with that roster. `process_pdf_folder()` finds PDFs directly inside the selected folder in case-insensitive filename order, runs each through `OCRPipeline.run(pdf_path)`, and concatenates the resulting DataFrames. Nested folders are not scanned.
5. If the folder contains no PDFs, processing stops with a `ValueError`. Otherwise, the combined DataFrame is printed in full.
6. `build_excel_output()` creates `./output` relative to the current working directory and forms a `<folder>_MM-DD-YYYY.xlsx` path using the current date. `export_attendance()` groups the combined DataFrame by its `Date` column and writes one worksheet per date. Worksheet names use `MM-DD-YYYY` because Excel forbids `/` in worksheet names; the `Date` cells are formatted as `MM/DD/YYYY`. Cells are centered without wrapping, populated cells receive thin borders, and header/attendance/review rows receive distinct fills. Column widths are sized to content and shared across all date sheets.
7. The app prints a row-count/output message and elapsed time.

The `prompt_for_date()` function validates `MM/DD/YYYY`, but its call is not part of the current workflow. The pipeline may set `DailySheet.sheet_date` by OCR when it identifies a sufficiently tall first-page header. Sheet dates remain in the combined data, while the workbook filename uses the folder name and current processing date.

### Date handling risk

`pipeline.py` stores the recognized date on the `DailySheet` class and updates it only when it detects a sufficiently tall main-page header and parses its printed date. The workbook filename no longer depends on that value, but each pipeline result still uses it for the `Date` column. If a PDF has no recognized date header or date OCR/parsing fails, a previous PDF's date may remain in shared state, or the date may be unavailable. Batch processing therefore still needs a reliable per-PDF date policy, ideally returning/setting the date explicitly with a validated manual fallback.

## Processing pipeline

### Current data flow

```
main.py starts
   |
   +--> Load environment variables from .env
   |
   +--> Open Tkinter folder picker
   |
   +--> Load data/SONYC2_roster.txt
   |
   +--> Find and sort PDFs directly in selected folder
   |
   +--> Create PipelineConfig and OCRPipeline
   |
   +--> For each PDF, call OCRPipeline.run(pdf_path)
   |      |
   |      +--> Render pages, deskew, detect table boundaries
   |      +--> Read the printed date when a main-page header is recognized
   |      +--> Filter row intervals against typical row height
   |      +--> Remove red marks from name crops, OCR names, classify attendance
   |      +--> Check a bounded write-in area and reconcile names
   |      +--> Return a dated DataFrame
   |
   +--> Concatenate per-PDF DataFrames and print result
   |
   +--> Build folder-and-current-date output path under ./output
   |
   +--> Export one worksheet per date with formatting (pandas/openpyxl)
   |
   +--> Print row count and elapsed time
```

The diagram follows the current folder-batch runtime path from selection through Excel export. The roster is loaded by `main.py` and passed into the pipeline configuration; each PDF produces a reconciled DataFrame that is concatenated before export.

`OCRPipeline.run(pdf_path)` is the orchestrator in `ocr_pipeline/pipeline.py`:

1. **PDF ingestion:** `ingestion.pdf_to_image()` opens the PDF with PyMuPDF and renders every page at configured `DPI` (default 300) into RGB NumPy arrays.
2. **Deskew:** each page is converted to grayscale, estimated for skew with a Hough-line approach, and rotated if the angle is nonzero. Deskew is implemented and currently called; it is not merely an empty placeholder. Orientation correction via `rotate.py` is imported but commented out.
3. **Table detection and crop:** OpenCV-based helpers detect vertical lines. The pipeline validates the line count and crops the page to the configured table columns. It then detects horizontal lines and checks that at least one row can be established.
4. **Header and page handling:** the pipeline removes a leading line in a specific edge case, examines the header region, and skips configured header rows for a main page. For a tall header it calls `detect_date.detect_sheet_date()` and assigns the result to `DailySheet.sheet_date`.
5. **Row extraction:** `table_detection.split_student_rows_and_handwritten_region()` estimates a typical row height from detected horizontal boundaries. It retains plausible student-row intervals and excludes short artifacts and oversized/footer gaps. For each retained row, the printed-name crop has red pixels detected in HSV and inpainted before grayscale OCR; common OCR artifacts (`™`, `~`, `-`, `—`, `.`) are stripped from primary and fallback Tesseract results. The attendance area is still read from its original RGB pixels and passed to `classification.classify_attendance()`.
6. **Handwritten-name detection:** OCR checks a bounded region reserved for possible write-in names, preferring the region before a large footer gap when present. If OCR returns any text, the pipeline appends a `WRITTEN NAME DETECTED` row with attendance `Present` for manual follow-up; printed text accidentally recognized in that crop can still be a false positive.
7. **Name reconciliation:** a DataFrame is built with `ocr_raw` and `attendance`; `reconciliation.fuzzy_match_names()` adds `cleaned_name`, `matched_name`, `matched_score`, and `flag`. It uses RapidFuzz `token_sort_ratio`, with defaults of 80 for a strong match and 30 for the low-match floor.
8. **Date column:** the pipeline inserts `Date` as the first DataFrame column using `DailySheet.sheet_date`, then returns the DataFrame.

The pipeline returns an extracted/reconciled DataFrame with `Date`, `ocr_raw`, `attendance`, `cleaned_name`, `matched_name`, `matched_score`, and `flag`. The folder workflow concatenates results from multiple PDFs, but does not currently add a source filename column.

## Main modules and responsibilities

| Area | Implemented responsibility |
| --- | --- |
| `main.py` | Tkinter folder picker, sorted direct-folder PDF batching, roster/config setup, DataFrame concatenation, console output, Excel export, and timing. The date prompt and updater call are unused. |
| `ocr_pipeline/pipeline.py` | Coordinates multi-page processing, geometry, typical-row filtering, OCR, attendance classification, name matching, bounded write-in detection, and date insertion. |
| `ocr_pipeline/ingestion.py` | Renders all PDF pages as RGB arrays using PyMuPDF and `DPI`. |
| `ocr_pipeline/table_detection.py`, `img_cropping.py` | Detect table grid coordinates, crop image regions, filter row intervals by median height, and identify bounded write-in regions. |
| `ocr_pipeline/deskew.py` | Estimates and corrects page skew; called by the pipeline. |
| `ocr_pipeline/rotate.py` | Orientation correction utility; currently not invoked (calls are commented out). |
| `ocr_pipeline/ocr.py` | Image preprocessing, red-strikethrough inpainting, OCR artifact cleanup, Tesseract OCR and empty-result retry, and handwritten-section text detection. `TESSERACT_CMD` can override the executable path; otherwise Tesseract must be discoverable on `PATH`. |
| `ocr_pipeline/classification.py` | Uses HSV and RGB channel comparisons to classify marks as `Present`, `Absent`, or `EMPTY CELL`. |
| `ocr_pipeline/reconciliation.py` | Cleans OCR text, fuzzy-matches the roster, and adds match scores and review/error flags. |
| `ocr_pipeline/detect_date.py` | Attempts to OCR and parse a printed date from a page header. This is used conditionally and is not a reliable user-input replacement yet. |
| `ocr_pipeline/config.py` | Pipeline column boundaries, roster, fuzzy-match thresholds, and environment-derived `DPI`, `S3_BUCKET`, and `OUTPUT_DIR`. In current code, `DPI` is used; `S3_BUCKET` and `OUTPUT_DIR` are not wired into the processing/export path. |
| `ocr_pipeline/models.py` | Declares `AttendanceRecord` and `DailySheet` dataclasses. Current pipeline output is a DataFrame, not a list of these record instances. |
| `io_utils/roster_input.py` | Loads and strips lines from the configured local roster text file. It does not currently accept a user-selected roster path or validate an empty/duplicate roster. |
| `io_utils/excel_output.py` | Groups concatenated attendance rows by date into separate worksheets, formats the `Date` column, and applies shared column widths across sheets. |
| `io_utils/excel_formatting.py` | Applies centered alignment, distinct headers, thin borders on populated cells, content-based column widths, and Present/Absent/review row colors. |
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

- The folder picker processes PDFs directly in the selected folder only, not nested subfolders. A single PDF processing failure currently stops the batch.
- The intended user-entered date is not currently requested. Date extraction occurs only when a sufficiently tall main-page header is detected and can raise a parsing error.
- The date is stored on the `DailySheet` dataclass type rather than passed as explicit per-run data. Because the attribute may not be refreshed for every PDF, a later sheet can inherit an earlier date; the workbook may then group those records on the wrong date tab.
- `check_for_update()` is imported but not called, so current launches do not check for updates.
- The updater's prompt uses `input()`, which is not an appropriate user interaction in a windowed GUI/subsystem build; update confirmation and failure reporting should use the eventual UI. The update mechanism also needs end-to-end testing on the target Windows executable before distribution.
- Tesseract is an external executable and must be available on staff computers or deliberately bundled and configured.
- OCR cleanup intentionally removes periods and hyphens as requested; that can also remove legitimate punctuation in names (for example initials or hyphenated surnames).
- The pipeline's output schema uses `Date`, `ocr_raw`, `attendance`, `cleaned_name`, `matched_name`, `matched_score`, and `flag`; some older docs describe different names such as `ocr_name`, `status`, or `match_score`.
- Classification, OCR, date detection, line detection, and deskew can be sensitive to scan quality/layout. Human review of low-confidence and handwritten-name rows remains necessary.
- A date OCR/parsing exception currently has no documented recovery flow, and pipeline failures are not caught by a user-facing error handler in `main.py`.
- The combined workbook does not include a source-filename column, and there is no folder-batch summary, persistent run log, or configurable output location in the current entry point.
- Handwritten-name detection treats any non-empty OCR output in its reserved crop as a write-in, so footer/printed marks that enter that crop may still cause a false positive.

## Future work (not implemented or not complete)

These items consolidate unfinished work noted across the docs and compare them with the current code. “Partial” means a related implementation exists, but the described feature is not complete end-to-end.

### Priority 1 — Make date and batch processing reliable

- [ ] Implement multi core processing  
- [ ] Restore a validated date prompt as the reliable fallback; pass the date explicitly instead of relying on mutable `DailySheet.sheet_date` class state.
- [ ] Define a clear date policy: use the detected date when OCR succeeds, and provide a manual-entry fallback when date detection fails. Add tests for invalid/missing date and multi-page PDFs.
- [ ] Decide whether output should be relative to the executable/project or user-selected; wire `OUTPUT_DIR` or remove/document it. Current output path and export behavior have focused tests.
- [ ] Add a friendly error path for canceled selection, bad/corrupt PDFs, missing roster, missing Tesseract, table-detection failures, date failures, and Excel write failures.
- [ ] Validate the roster (file exists, non-empty entries, duplicates) and surface configuration/dependency problems before processing.
- [ ] Add a maximum-skew threshold: reject PDFs whose detected skew is too large for reliable correction, with a clear error explaining that excessive skew can cause vertical-line detection to fail.
- [ ] Add persistent roster storage or a cache so the student roster is retained between runs, with a clear way to refresh it when the source roster changes.
- [ ] Fully integrate `AttendanceRecord` and `DailySheet` into the pipeline's inputs/outputs instead of declaring the dataclasses while returning only a DataFrame.
- [ ] Add focused tests for date parsing/state across PDFs, pipeline failures, and per-file batch failure behavior; run a repeatable manual end-to-end audit against representative scans.

### Priority 2 — Deliver the intended desktop staff workflow

- [ ] Integrate the Activity Level Audit script into this project and define how it fits into the attendance-processing workflow.
- [x] Replace the single-PDF picker with a folder picker and collect/sort PDFs directly in that folder; handle an empty folder.
- [ ] Provide date entry/fallback in the UI (at minimum a validated date field) and define how a date is selected independently for each PDF.
- [ ] Add processing feedback (selected folder/files, progress, completion, output location) and user-friendly error messages.
- [ ] Include `source_file` per row in the combined workbook and decide how to continue/report when an individual PDF fails.
- [x] Concatenate each PDF's results and export one workbook with a worksheet for each date; format dates and apply workbook styling.
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
- [x] Add Excel presentation basics: shared content-sized columns, centered cells, distinct headers, thin populated-cell borders, and status/review row highlights.
- [ ] Consider filters, a useful column order, or a separate summary sheet.
- [ ] Add a local web interface that runs on localhost and calls the same pipeline; keep web routes/UI code separate from OCR processing.
- [ ] If needed, add an API/job interface and background processing after a GUI/web workflow is stable.
- [ ] Explore Docker/CI infrastructure and later AWS services (S3, container-based Lambda, API Gateway, SQS, DynamoDB, IAM) as explicitly later learning/deployment phases, not current app capabilities.

## Documentation reconciliation notes

- `MVP_ROADMAP.md` and `PROJECT_STRUCTURE.md` contain stale “placeholder/not implemented” statuses for features now present, including classification, reconciliation, pipeline orchestration, roster loading, and Excel export. They also describe older package paths such as `io/` instead of the current `io_utils/`.
- `Attendance-OCR-App-Roadmap.md` marks some MVP steps complete, but the current `main.py` contradicts its claim that a validated manual date prompt is active and that the end-to-end CLI flow is complete. Treat the checklist as historical planning, not proof of current behavior.
- `APP_OVERVIEW_MVP.md` contains useful architecture and future-phase material, but its workflow/schema descriptions are not fully aligned with the current code. This document records the code-backed status as reviewed.
- The notes in `auto-update-and-phases.txt` describe the intended executable/release/update path; the updater code exists, but the entry point does not currently activate it and packaging/release automation remains to be validated.
- `rosterName_dbName_Issue.txt` describes future roster-to-database/student-ID mapping. That mapping and the separate database reconciliation stage are not implemented in this app.
