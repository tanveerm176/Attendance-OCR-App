# Attendance OCR App — Claude Working Notes

## Project Purpose

The **Attendance OCR App** automates the processing of scanned attendance sheets from educational activities:

1. **Renders PDFs** to high-resolution images (300 DPI)
2. **Detects table grids** using morphological computer vision (vertical/horizontal line detection)
3. **Extracts names** via Tesseract OCR from name cells
4. **Classifies attendance** by analyzing ink color in mark cells (HSV-based: red=Absent, blue=Present)
5. **Reconciles names** against student roster using fuzzy matching (rapidfuzz token_sort_ratio)
6. **Exports results** to Excel with match scores and confidence flags

**Target Use Cases:**
- Automating DYCD Activity-Day audit workflow (outputs compared against DYCD Excel for data accuracy)
- Reducing manual data entry and transcription errors into DYCD Connect

**Version:** 0.1.0 (MVP)

### Core Architecture

The architecture is built around a clean pipeline boundary:

- **`OCRPipeline.run(pdf_path) → pd.DataFrame`** is the core interface (prompt-free, I/O-free)
- **CLI/UI layers** handle user interaction and output separately
- **Separation of concerns:** `ocr_pipeline/` (processing only), `main.py` (CLI), future GUI/web/API (independent layers)
- **In-memory data transfer:** Stages pass numpy arrays and DataFrames; no repeated disk I/O
- **Stateless functions:** Most functions are pure (input → output, no side effects)

## Current MVP Status

**Phase 0 — MVP (Current Focus)** — The project is past Step 2 and ready for structured error handling and orchestration.

### Completed
- **Step 1:** `ocr_pipeline/classification.py` ✓ — HSV-based attendance mark classification (Present/Absent/EMPTY_CELL)
- **Step 2:** `ocr_pipeline/reconciliation.py` ✓ — Name cleaning (regex) and fuzzy roster matching (rapidfuzz token_sort_ratio)

### Next Steps (in order)
1. **Step 3:** `ocr_pipeline/exceptions.py` — Custom exception hierarchy (TableDetectionError, OCRExtractionError, NoMatchFoundError)
2. **Step 4:** `ocr_pipeline/models.py` — AttendanceRecord and DailySheet dataclasses
3. **Step 5:** `ocr_pipeline/config.py` + `io_utils/roster_input.py` — PipelineConfig and roster loading
4. **Step 6:** `ocr_pipeline/pipeline.py` — OCRPipeline orchestrator (skeleton → real calls)
5. **Step 7:** `main.py` — CLI with batch processing and date prompts
6. **Step 8:** `io_utils/excel_output.py` — Export to `.xlsx`
7. **Step 9:** `reporting/summary.py` + `reporting/logger.py` — Statistics and audit logging
8. **Step 10:** End-to-end testing and demoability

After Step 10, move to Phase 2 (GUI) and Phase 3 (web/cloud).

## Module Breakdown

### Core Pipeline (`ocr_pipeline/`)

#### **`ingestion.py`**
- **Function:** `pdf_to_image(pdf_path) → np.ndarray`
- **Details:** Uses PyMuPDF to render first PDF page at 300 DPI as RGB array (height × width × 3)
- **Deps:** PyMuPDF, numpy

#### **`table_detection.py`**
- **Functions:** `get_vertical_line_positions(gray_img)`, `get_horizontal_line_positions(gray_img)`
- **Algorithm:** Binary threshold → invert → morphological opening (1×100 or 100×1 kernel) → sum columns/rows → peak detection → cluster peaks (within 5px)
- **Returns:** Sorted lists of pixel coordinates
- **Deps:** OpenCV, numpy

#### **`img_cropping.py`**
- **Functions:** `vertical_img_crop(img, x_start, x_end)`, `horizontal_img_crop(img, y_start, y_end)`
- **Details:** Simple NumPy array slicing with boundary validation
- **Deps:** numpy

#### **`ocr.py`**
- **Functions:** `preprocess_for_ocr(gray_img)`, `tesseract_ocr(image_cell_gray) → str`
- **Preprocessing:** Threshold (180) → dilate (2×2 kernel) → invert to black-on-white
- **Details:** Tesseract path hardcoded for Windows
- **Deps:** OpenCV, pytesseract, Tesseract binary

#### **`classification.py`** ✓ Completed
- **Function:** `classify_attendance(cell_img_rgb) → str`
- **Returns:** `"Present"`, `"Absent"`, or `"EMPTY CELL"`
- **Logic:** RGB → HSV → mask background → count red (hue 0–12, 158–180) vs. blue (hue 90–140) pixels
- **Fallback:** R−B channel difference if saturation too low; default to "Absent" if ambiguous
- **Deps:** OpenCV, numpy

#### **`reconciliation.py`** ✓ Completed
- **Functions:** `clean_ocr_name(name) → str`, `fuzzy_match_names(df, roster, name_col, threshold, low_match_floor)`
- **Cleaning:** Regex strips non-letter/space/hyphen/apostrophe chars
- **Matching:** rapidfuzz token_sort_ratio (default threshold 80)
- **Flags:** `"Low Match - Needs Review"` (score < 30), `"OCRExtractionError"`, `"NoMatchFoundError"`
- **Appends:** cleaned_name, matched_name, match_score, flag columns
- **Deps:** pandas, rapidfuzz

#### **`config.py`**
- **Class:** `PipelineConfig` (dataclass)
- **Key Fields:** roster, img_crop_start/end, skip_header_start_row, name_col_start/end, attendance_col_start/end, fuzzy_match_threshold, low_match_floor
- **Env Vars:** DPI (300), S3_BUCKET (None), OUTPUT_DIR ("./output")
- **Deps:** dataclasses

#### **`exceptions.py`** (Step 3 — Next)
- **Classes:** `OCRPipelineError`, `TableDetectionError`, `OCRExtractionError`, `NoMatchFoundError`
- **Usage:** Caught in orchestrator for graceful error handling

#### **`models.py`** (Step 4 — Next)
- **Classes:** `AttendanceRecord` (date, ocr_name, cleaned_name, matched_name, match_score, status, flag)
- **Classes:** `DailySheet` (sheet_date, source_pdf, records list)

#### **`pipeline.py`** (Step 6 — Next)
- **Class:** `OCRPipeline`
- **Main Method:** `run(pdf_path) → pd.DataFrame`
- **Workflow:** PDF → RGB image → detect vertical lines → crop table → detect horizontal lines → iterate rows (OCR name + classify attendance) → fuzzy match → return DataFrame

#### **`deskew.py`**
- **Status:** Empty placeholder for future image rotation correction

### I/O and Reporting

#### **`io_utils/roster_input.py`**
- **Function:** `build_roster() → list[str]`
- **Details:** Loads `data/student_roster.txt`, strips commas/whitespace, returns canonical names
- **File Format:** Plain text, one name per line

#### **`io_utils/excel_output.py`**
- **Function:** `export_attendance(df, output_path) → None`
- **Details:** Writes DataFrame as `.xlsx` using openpyxl engine
- **Output Columns:** ocr_name, cleaned_name, matched_name, match_score, status, flag, date

#### **`reporting/logger.py`**
- **Status:** Stub (empty, for audit trail logging)

#### **`reporting/summary.py`**
- **Status:** Stub (empty, for statistics display)

### CLI and Updates

#### **`main.py`**
- **Functions:** `prompt_for_pdf_path()`, `prompt_for_date()`
- **Planned Workflow:** Check update → parse args → validate input → load roster → prompt date → collect PDFs → run pipeline on each → concatenate results → export Excel → print summary → write log
- **Status:** Partially implemented; docstring describes intended flow

#### **`updater.py`**
- **Functions:** `get_local_version()`, `get_latest_release()`, `is_newer()`, `download_and_replace()`, `check_for_update()`
- **Details:** Queries GitHub API for latest release, silently handles errors (dev mode skips replacement)
- **Source:** `tanveerm176/Attendance-OCR-App` releases on GitHub

## Data Flow (Single PDF)

```
User selects PDF → Prompt date (MM/DD/YYYY) → OCRPipeline.run()
       ↓
Render PDF at 300 DPI → RGB image
       ↓
Detect vertical lines → Crop table region (columns 0–5)
       ↓
Detect horizontal lines → Validate row count
       ↓
For each row:
  - Extract name cell → OCR → raw string
  - Extract attendance cell → Classify (Present/Absent/EMPTY_CELL)
  - Append dict to list
       ↓
Convert list to DataFrame (ocr_name, status)
       ↓
Fuzzy match names against roster → Append (cleaned_name, matched_name, match_score, flag)
       ↓
Return DataFrame
       ↓
Stamp date + source filename → Export to Excel
```

## Key Configuration Points

- **Roster File:** `data/student_roster.txt` (loaded by `io_utils/roster_input.py`)
- **PDF Rendering:** 300 DPI (tunable via `DPI` env var)
- **Table Crop:** Columns 0–5 (configurable in `PipelineConfig`)
- **Fuzzy Match Threshold:** 80 (tunable, lower = more matches but lower confidence)
- **Low Match Floor:** 30 (scores below this flagged as `"Low Match - Needs Review"`)
- **Tesseract Path:** Windows hardcoded; should be made configurable

## System Dependencies

- **Tesseract OCR** (external binary) — must be installed at: `C:\Users\mtanveer\AppData\Local\Programs\Tesseract-OCR\tesseract.exe`
- **Python Packages:** pandas, numpy, opencv-python, pytesseract, PyMuPDF, rapidfuzz, openpyxl

## Guardrails from the Roadmap

✓ Keep `OCRPipeline.run(pdf_path) → pd.DataFrame` as the core, prompt-free interface
✓ Do NOT put interactive prompts inside the pipeline itself
✓ Keep data transfer as in-memory DataFrames; avoid repeated disk I/O
✓ Keep the model/logic scoped to MVP tasks; no premature cloud/API overbuild
✓ Long-term phases should be additive, not competing with MVP
✓ Pipeline is the single source of truth; all future UI layers call it without modification

## Known discrepancies across the docs

The three documents are aligned on the long-term project direction, but they are not equally current or equally detailed.

### 1. Different levels of granularity

- [docs/Attendance-OCR-App-Roadmap.md](docs/Attendance-OCR-App-Roadmap.md) is a broad strategic roadmap and phase tracker.
- [docs/MVP_ROADMAP.md](docs/MVP_ROADMAP.md) is the detailed execution checklist for the current MVP.
- [docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md) is a repository inventory and architecture summary, not a task tracker.

This means the roadmap docs are more actionable than the project-structure doc, and the project-structure doc is more archival than current-state.

## Document Truth Hierarchy

The documentation suite has different purposes and update frequencies. Priority is:

1. **First:** Follow [docs/MVP_ROADMAP.md](docs/MVP_ROADMAP.md) for exact sequence and dependencies
2. **Second:** Use [APP_OVERVIEW_MVP.md](APP_OVERVIEW_MVP.md) for detailed module specs and current state
3. **Third:** Consult [docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md) for repo layout only

**Known Status Notes:**
- `reconciliation.py` is **completed** (not a placeholder)
- `classification.py` is **completed** (not in-progress)
- Sample test files are `df_fuzzy_names.csv` and `OCR_Name_Attendance.csv` (not `sonyc-test.pdf`)
- `main.py` is partially implemented; Step 7/9 in MVP roadmap describes the rewrite needed
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

## Document Truth Hierarchy

The documentation suite has different purposes and update frequencies:

| Document | Purpose | When to Use |
|----------|---------|-------------|
| [APP_OVERVIEW_MVP.md](APP_OVERVIEW_MVP.md) | Complete current overview with module details, data flow, config, testing | Reference architecture, understand current state, debugging |
| [docs/MVP_ROADMAP.md](docs/MVP_ROADMAP.md) | Detailed execution checklist (Step 1–10) | **PRIMARY FOR SEQUENCING** — exact next steps |
| [docs/Attendance-OCR-App-Roadmap.md](docs/Attendance-OCR-App-Roadmap.md) | Strategic phases (Phase 0, 0.5, 1, 2, 3) | Long-term vision, phase alignment |
| [docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md) | Repository inventory and current layout | File organization reference; less current on status |
| **claude.md** (this file) | Working notes for agent guidance | Agent context and working principles |

### Priority for Implementation

1. **First:** Follow [docs/MVP_ROADMAP.md](docs/MVP_ROADMAP.md) for exact sequence and dependencies
2. **Second:** Use [APP_OVERVIEW_MVP.md](APP_OVERVIEW_MVP.md) for detailed module specs and current state
3. **Third:** Consult [docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md) for repo layout only

### Known Status Notes

- `reconciliation.py` is **completed** (not a placeholder)
- `classification.py` is **completed** (not in-progress)
- Sample test files are `df_fuzzy_names.csv` and `OCR_Name_Attendance.csv` (not `sonyc-test.pdf`)
- `main.py` is partially implemented; Step 7/9 in MVP roadmap describes the rewrite needed
