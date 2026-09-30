# Attendance OCR App — Complete Overview

## Table of Contents
1. [Project Purpose](#project-purpose)
2. [Core Architecture](#core-architecture)
3. [Module Breakdown](#module-breakdown)
4. [Data Flow](#data-flow)
5. [File Organization](#file-organization)
6. [Configuration & Setup](#configuration--setup)
7. [Deployment & Distribution](#deployment--distribution)
8. [Phase 2 & Phase 3 (Future)](#phase-2--phase-3-future)
9. [Testing Strategy](#testing-strategy)

---

## Project Purpose

The **Attendance OCR App** automates the processing of scanned attendance sheets from educational activities. It:

1. **Renders PDFs** from printed sign-in sheets
2. **Detects table grids** using computer vision (kernel-based line detection)
3. **Extracts text** via OCR (Tesseract) from name cells
4. **Classifies attendance** by analyzing ink color in signature/mark cells
5. **Reconciles names** against a student roster using fuzzy matching
6. **Exports results** to Excel for further processing or archival

**Target Use Cases:** 
1. Automating DYCD Activity-Day audit workflow, outputs of the OCR app are compared with an excel output from DYCD to ensure data accuracy 
2. Reducing manual data entry and transcription error of daily attendance into DYCD Connect 

**Version:** 0.1.0 (MVP)

---

## Core Architecture

### Design Principles

- **Clean Pipeline Boundary:** The core interface is `OCRPipeline.run(pdf_path) → pd.DataFrame`
- **Separation of Concerns:** 
  - Pipeline logic (`ocr_pipeline/`) handles data processing only
  - CLI/UI layers (`main.py`, future GUI/web) handle user interaction and output
  - No interactive prompts or file I/O inside the pipeline itself
- **In-Memory Data Transfer:** Stages pass data as numpy arrays (images) and pandas DataFrames (structured data), avoiding repeated disk I/O
- **Stateless Transformations:** Most functions are pure functions (input → output, no side effects)

### High-Level Pipeline Flow

```
PDF File
   ↓
[Ingestion] → Render first page at 300 DPI as RGB image
   ↓
[Table Detection] → Detect vertical and horizontal grid lines
   ↓
[Image Cropping] → Crop to table region (columns 0–5)
   ↓
[OCR Extraction] → Extract text from name cells, classify attendance marks
   ↓
[Name Cleaning] → Remove OCR junk (digits, punctuation)
   ↓
[Fuzzy Matching] → Match cleaned names to roster using rapidfuzz
   ↓
[Classification] → Determine Present/Absent from attendance cell color (HSV)
   ↓
[Output] → Export to Excel with match scores and flags
```

---

## Module Breakdown

### `ocr_pipeline/` — Core Processing Modules

#### **`ingestion.py`**
- **Purpose:** Convert scanned PDF to usable image
- **Main Function:** `pdf_to_image(pdf_path: Path) → np.ndarray`
- **Details:**
  - Uses PyMuPDF (`fitz`) to render the first page of a PDF
  - Renders at 300 DPI for high OCR accuracy
  - Returns a numpy array in RGB color space (height × width × 3 channels)
  - No preprocessing or filtering applied here — just raw image
- **Dependencies:** PyMuPDF, numpy

#### **`table_detection.py`**
- **Purpose:** Locate column and row boundaries of the table using morphological operations
- **Main Functions:**
  - `get_vertical_line_positions(gray_img: np.ndarray) → list[int]` — finds x-coordinates of vertical grid lines
  - `get_horizontal_line_positions(gray_img: np.ndarray) → list[int]` — finds y-coordinates of horizontal grid lines
- **Algorithm:**
  1. Convert image to binary (threshold at 150)
  2. Invert (white pixels = potential lines)
  3. Apply morphological opening with a thin kernel (1×100 for vertical, 100×1 for horizontal)
  4. Sum pixels along columns (for vertical) or rows (for horizontal)
  5. Find peaks in the sum (locations with high white-pixel density)
  6. Cluster nearby peaks (within 5 pixels) to get line centers
- **Returns:** Sorted lists of pixel coordinates (integers)
- **Dependencies:** OpenCV, numpy

#### **`img_cropping.py`**
- **Purpose:** Extract rectangular regions from images
- **Main Functions:**
  - `vertical_img_crop(img: np.ndarray, x_start: int, x_end: int) → np.ndarray`
  - `horizontal_img_crop(img: np.ndarray, y_start: int, y_end: int) → np.ndarray`
- **Details:**
  - Simple NumPy array slicing with boundary validation
  - Raises `ValueError` if bounds are invalid
  - No image processing — just geometric extraction

#### **`ocr.py`**
- **Purpose:** Extract text from image regions using OCR
- **Main Functions:**
  - `preprocess_for_ocr(gray_img: np.ndarray) → np.ndarray` — prepare image for Tesseract
  - `tesseract_ocr(image_cell_gray: np.ndarray) → str` — run OCR on preprocessed image
- **Preprocessing Steps:**
  1. Threshold at 180 (binary, inverted)
  2. Dilate with 2×2 kernel to thicken thin font strokes
  3. Invert back to black-on-white (Tesseract's expected format)
  4. Pass to Tesseract
- **Details:**
  - Tesseract executable path is hardcoded for Windows: `C:\Users\mtanveer\AppData\Local\Programs\Tesseract-OCR\tesseract.exe`
  - Accepts grayscale (2D) NumPy arrays only
- **Dependencies:** OpenCV, pytesseract, Tesseract (external binary)

#### **`classification.py`**
- **Purpose:** Classify attendance marks from cell images (Present/Absent)
- **Main Function:** `classify_attendance(cell_img_rgb: np.ndarray) → str`
- **Classification Logic:**
  1. Convert RGB to HSV for color analysis
  2. Mask out background (low saturation, high brightness)
  3. If `< 30` non-background pixels: return `"EMPTY CELL"`
  4. Count saturated red pixels (hue 0–12 or 158–180) vs. blue pixels (hue 90–140)
  5. If both counts low: fall back to R−B channel difference
  6. Red dominant → `"Absent"`, Blue dominant → `"Present"`
  7. Ambiguous: default to `"Absent"` (conservative)
- **Returns:** String: `"Present"`, `"Absent"`, or `"EMPTY CELL"`
- **Dependencies:** OpenCV, numpy

#### **`reconciliation.py`**
- **Purpose:** Clean and match OCR names against roster
- **Main Functions:**
  - `clean_ocr_name(name: str) → str` — remove OCR junk (digits, special chars)
  - `fuzzy_match_names(df: pd.DataFrame, roster: list[str], name_col: str, threshold: int, low_match_floor: int) → pd.DataFrame`
- **Cleaning:** Regex-strips anything that isn't a letter, space, hyphen, or apostrophe
- **Matching:**
  - Uses `rapidfuzz.process.extractOne` with `token_sort_ratio` scorer
  - Threshold default: 80 (tunable via config)
  - Returns tuple: `(matched_roster_name, score)`
  - Flags matches below `low_match_floor` (default 30) as `"Low Match - Needs Review"`
  - Flags unrecoverable OCR extractions as `"OCRExtractionError"`
  - Flags names with no roster match as `"NoMatchFoundError"`
- **Output:** Appends columns to DataFrame: `cleaned_name`, `matched_name`, `match_score`, `flag`
- **Dependencies:** pandas, rapidfuzz

#### **`config.py`**
- **Purpose:** Centralized configuration for the pipeline
- **Main Class:** `PipelineConfig` (dataclass)
- **Key Settings:**
  - `roster` — list of student names
  - `img_crop_start`, `img_crop_end` — which vertical lines define the table (e.g., 0–5)
  - `skip_header_start_row` — how many header rows to skip (e.g., 2 for first page)
  - `default_start_row` — row index for subsequent pages (e.g., 0)
  - `name_col_start`, `name_col_end` — which columns contain names (e.g., 1–2)
  - `attendance_col_start`, `attendance_col_end` — which columns contain attendance marks (e.g., 3–5)
  - `fuzzy_match_threshold` — minimum fuzzy-match score (default 80)
  - `low_match_floor` — score below which matches are flagged as low confidence (default 30)
- **Environment Variables:**
  - `DPI` (default 300) — render resolution for PDF
  - `S3_BUCKET` (default None) — for future cloud integration
  - `OUTPUT_DIR` (default "./output") — where to save results

#### **`exceptions.py`**
- **Purpose:** Define custom exceptions for pipeline errors
- **Exception Classes:**
  - `OCRPipelineError` — base class for all pipeline exceptions
  - `TableDetectionError` — raised when grid detection fails (e.g., insufficient lines found)
  - `OCRExtractionError` — raised when OCR result is empty or unusable
  - `NoMatchFoundError` — raised when a name cannot be matched to roster
- **Usage:** Caught in orchestrator (`pipeline.py`) to handle failures gracefully

#### **`pipeline.py`**
- **Purpose:** Orchestrate all stages into a cohesive end-to-end workflow
- **Main Class:** `OCRPipeline`
- **Core Method:** `run(pdf_path: Path) → pd.DataFrame`
- **Workflow:**
  1. Load PDF as RGB image
  2. Convert to grayscale, detect vertical lines
  3. Validate line count (must find at least `img_crop_end + 1` lines)
  4. Crop image vertically to table region
  5. Detect horizontal lines in cropped table
  6. Validate row count
  7. Iterate over rows:
     - Extract name cell, run OCR
     - Extract attendance cell, classify color
     - Append row to result list
  8. Concatenate rows into a single DataFrame
  9. Return DataFrame with columns: `ocr_name`, `attendance_status`, etc.
- **Error Handling:** Raises `TableDetectionError` or other pipeline exceptions on failure

#### **`models.py`**
- **Purpose:** Define data structures for typed pipeline output
- **Classes:**
  - `AttendanceRecord` (dataclass)
    - `date: datetime` — sign-in date
    - `ocr_name: str` — raw OCR text
    - `cleaned_name: str` — after regex cleaning
    - `matched_name: Optional[str]` — fuzzy-matched roster name
    - `match_score: float` — fuzzy-match confidence (0–100)
    - `status: Literal["Present", "Absent", "EMPTY CELL"]` — attendance classification
    - `flag: str` — any error/warning labels
  - `DailySheet` (dataclass)
    - `sheet_date: datetime` — batch date
    - `source_pdf: Path` — PDF filename
    - `records: list[AttendanceRecord]` — all extracted records for this sheet

#### **`deskew.py`**
- **Status:** Empty placeholder
- **Intended Purpose:** Image rotation correction (skew removal)
- **Planned for:** Future enhancement if scans are consistently rotated

---

### `io_utils/` — Input/Output Utilities

#### **`roster_input.py`**
- **Purpose:** Load and validate student roster
- **Main Function:** `build_roster() → list[str]`
- **Details:**
  - Reads from hardcoded path `data/student_roster.txt`
  - Strips commas, newlines, and extra whitespace from each line
  - Returns a list of canonical student names
- **File Format:** Plain text, one name per line, comma-separated or space-separated
- **Example:**
  ```
  Aca Hernandez, Kevin
  Aca Hernandez, William
  Acevedo, Grayson
  ...
  ```

#### **`excel_output.py`**
- **Purpose:** Export DataFrame to Excel file
- **Main Function:** `export_attendance(df: pd.DataFrame, output_path: Path) → None`
- **Details:**
  - Writes DataFrame as `.xlsx` using openpyxl engine
  - No formatting or styling applied (MVP)
  - Creates file at specified path, creates parent directories if needed
- **Typical Output Columns:**
  - `ocr_name` — raw text extracted
  - `cleaned_name` — OCR junk removed
  - `matched_name` — roster name (or None)
  - `match_score` — fuzzy-match confidence
  - `status` — Present/Absent/EMPTY CELL
  - `flag` — error labels (e.g., "OCRExtractionError", "Low Match - Needs Review")
  - `date` — sign-in date

---

### `reporting/` — Logging & Summary

#### **`logger.py`**
- **Purpose:** Log detailed pipeline execution and results
- **Status:** Stub (currently empty)
- **Intended Use:** Write audit trail to file for debugging and compliance

#### **`summary.py`**
- **Purpose:** Print on-screen statistics and summary
- **Status:** Stub (currently empty)
- **Intended Use:** Display counts (total rows, matches, flags) after processing

---

### `main.py` — CLI Entry Point

- **Purpose:** User-facing command-line interface
- **Current Functions:**
  - `prompt_for_pdf_path() → Path` — file dialog to select PDF
  - `prompt_for_date() → str` — validate MM/DD/YYYY date input
- **Workflow (Planned, per docstring):**
  1. Check for app update (`updater.check_for_update()`)
  2. Parse CLI arguments (input folder, roster, output path)
  3. Validate input files exist
  4. Load roster (`io_utils.roster_input.build_roster()`)
  5. Prompt for batch date (MM/DD/YYYY format)
  6. Collect PDFs from input folder
  7. For each PDF:
     - Initialize pipeline
     - Call `pipeline.run(pdf_path)` → DataFrame
     - Append to batch results
  8. Concatenate all batch results
  9. Export to Excel (`io_utils.excel_output.export_attendance()`)
  10. Print summary (`reporting.summary.print_summary()`)
  11. Write log (`reporting.logger.write_log()`)
- **Status:** Partially implemented; docstring describes intended flow, but actual code not yet complete

---

### `updater.py` — Auto-Update Mechanism

- **Purpose:** Check GitHub for new releases and download/install updates
- **Main Functions:**
  - `get_local_version() → str` — read version from `VERSION` file
  - `get_latest_release() → tuple[str, str]` — fetch latest release from GitHub API
  - `is_newer(latest: str, current: str) → bool` — semantic version comparison
  - `download_and_replace(download_url: str)` — download `.exe` and replace running process
  - `check_for_update()` — entry point called from `main.py`
- **Details:**
  - Queries GitHub API: `https://api.github.com/repos/tanveerm176/Attendance-OCR-App/releases/latest`
  - Only operates when app is a PyInstaller bundle (`sys.frozen == True`)
  - In development mode (running as `.py` script), silently skips replacement
  - Silently catches all exceptions to prevent update failure from crashing app
  - On success, relaunches the app with the new executable
- **Typical Flow:**
  1. On startup, `check_for_update()` compares local vs. latest version
  2. If newer version available, prompts user: "Install now? (Y/N)"
  3. If user says yes and app is frozen: downloads, backs up old `.exe`, replaces, relaunches
  4. If network error or not frozen: prints message and continues

---

## Data Flow

### Single PDF Processing

```
User provides PDF path via file dialog
          ↓
main.py prompts for sign-in date (MM/DD/YYYY)
          ↓
OCRPipeline.run(pdf_path) is called
          ↓
  [ingestion.py]
  pdf_to_image() → RGB numpy array (HxWx3)
          ↓
  [table_detection.py]
  get_vertical_line_positions() → [x1, x2, x3, x4, x5, x6, ...]
  get_horizontal_line_positions() (after crop) → [y1, y2, y3, ...]
          ↓
  [img_cropping.py]
  vertical_img_crop(img, x0, x5) → table region (HxWx3)
          ↓
  [ocr.py + classification.py] — iterate over rows:
    for each row in [y1, y2):
      - Extract name region (x1:x2, y1:y2)
      - Grayscale convert
      - Run OCR → raw name string
      
      - Extract attendance region (x3:x5, y1:y2)
      - Keep RGB
      - Classify attendance → "Present"/"Absent"/"EMPTY CELL"
      
      - Append dict {ocr_name, status} to list
          ↓
  Convert list to DataFrame
  Columns: {ocr_name, status}
          ↓
  [reconciliation.py]
  fuzzy_match_names(df, roster)
  Appends columns: {cleaned_name, matched_name, match_score, flag}
          ↓
  Return DataFrame to caller
          ↓
main.py stamps date and source filename
          ↓
[excel_output.py]
export_attendance(df, output_path)
          ↓
File written to disk: output/audit_{date-with-dashes}.xlsx
```

### Batch Processing (Multiple PDFs)

1. Iterate over multiple PDFs
2. For each PDF, run single-PDF flow above
3. Append each result DataFrame to a list
4. After all PDFs: `pd.concat(batch_results, ignore_index=True)`
5. Export concatenated batch to single Excel file

---

## File Organization

### Root Directory Files

| File | Purpose |
|------|---------|
| `main.py` | CLI entry point |
| `updater.py` | GitHub release auto-update |
| `VERSION` | Current version (0.1.0) |
| `pyproject.toml` | Package metadata and dependencies |
| `requirements.txt` | Pip dependencies (alternative to pyproject.toml) |
| `pytest.ini` | Pytest configuration |

### Directory Structure

```
attendance_ocr_app/
├── ocr_pipeline/              # Core processing modules
│   ├── __init__.py
│   ├── ingestion.py           # PDF → RGB image
│   ├── table_detection.py     # Detect grid lines
│   ├── img_cropping.py        # Extract regions
│   ├── ocr.py                 # Tesseract OCR
│   ├── classification.py      # Attendance color classification
│   ├── reconciliation.py      # Name cleaning & fuzzy matching
│   ├── config.py              # PipelineConfig dataclass
│   ├── exceptions.py          # Custom exception classes
│   ├── pipeline.py            # OCRPipeline orchestrator
│   ├── models.py    # Data structures
│   └── deskew.py              # (Empty, for future use)
│
├── io_utils/                  # I/O utilities
│   ├── __init__.py
│   ├── roster_input.py        # Load student roster
│   └── excel_output.py        # Export to Excel
│
├── reporting/                 # Logging & summary
│   ├── __init__.py
│   ├── logger.py              # (Empty, for audit logging)
│   └── summary.py             # (Empty, for statistics)
│
├── tests/                     # Unit tests
│   ├── __init__.py
│   ├── test_ingestion.py
│   ├── test_table_detection.py
│   ├── test_img_cropping.py
│   ├── test_ocr.py
│   ├── test_classification.py
│   ├── test_reconciliation.py
│   ├── test_exceptions.py
│   └── sample_scans/          # Test fixture images
│       ├── present_cell.png
│       ├── absent_cell.png
│       ├── df_fuzzy_names.csv
│       └── OCR_Name_Attendance.csv
│
├── data/                      # Input data
│   └── student_roster.txt     # Student names, one per line
│
├── output/                    # Output Excel files
│   └── (generated at runtime)
│
├── docs/                      # Documentation
│   ├── Attendance-OCR-App-Roadmap.md  # Long-term phases
│   ├── MVP_ROADMAP.md                 # Current sprint tasks
│   └── PROJECT_STRUCTURE.md           # Repo inventory
│
├── phase2-gui/                # Future GUI (Flask/Qt)
│   └── gui/
│       └── app.py             # (Empty stub)
│
└── phase3-web/                # Future web app (Flask)
    ├── routes.py              # (Empty stub)
    ├── static/                # (Empty)
    └── templates/             # (Empty)
```

---

## Configuration & Setup

### Environment Variables

Managed in `ocr_pipeline/config.py`:

- **`DPI`** (default 300) — PDF render resolution in dots per inch
  - Higher = better OCR accuracy, slower rendering
  - Set to 300 for production, lower for testing
- **`S3_BUCKET`** (default None) — AWS S3 bucket for future cloud storage
  - When None: local filesystem mode
  - When set: upload/download from S3 (not yet implemented)
- **`OUTPUT_DIR`** (default "./output") — directory for Excel exports

### Roster Configuration

- **File:** `data/student_roster.txt`
- **Format:** One name per line, e.g., `LastName, FirstName`
- **Used By:** `io_utils/roster_input.py`
- **Loaded Into:** `PipelineConfig.roster` (list[str])

### Pipeline Configuration

All tunable parameters are in the `PipelineConfig` dataclass:

```python
@dataclass
class PipelineConfig:
    roster: list[str]                    # Student names
    img_crop_start: int = 0              # First table column
    img_crop_end: int = 5                # Last table column (exclusive)
    skip_header_start_row: int = 2       # Skip N header rows on page 1
    default_start_row: int = 0           # Start row for subsequent pages
    name_col_start: int = 1              # Name column start
    name_col_end: int = 2                # Name column end (exclusive)
    attendance_col_start: int = 3        # Attendance column start
    attendance_col_end: int = 5          # Attendance column end (exclusive)
    fuzzy_match_threshold: int = 80      # Min score to accept match
    low_match_floor: int = 30            # Min score before flagging as low confidence
```

### Python Dependencies

From `pyproject.toml`:

- `pandas` — data manipulation and Excel export
- `numpy` — numeric array operations
- `opencv-python` (cv2) — image processing and line detection
- `pytesseract` — Python wrapper for Tesseract OCR
- `PyMuPDF` (fitz) — PDF rendering
- `rapidfuzz` — fuzzy string matching
- `openpyxl` — Excel workbook creation

### System Dependencies

- **Tesseract OCR** — external binary, must be installed and available at:
  - **Windows:** `C:\Users\mtanveer\AppData\Local\Programs\Tesseract-OCR\tesseract.exe`
  - Can be overridden in `ocr_pipeline/ocr.py`: `pytesseract.pytesseract.tesseract_cmd = r'...'`
  - Download: https://github.com/UB-Mannheim/tesseract/wiki

---

## Deployment & Distribution

### PyInstaller Bundle

The app can be packaged as a standalone `.exe` using PyInstaller:

- **Config File:** `main.spec`
- **Build Command:** `pyinstaller main.spec`
- **Output:** `dist/main.exe`
- **Feature:** Auto-update capability (via `updater.py`)

### Version Management

- **File:** `VERSION`
- **Format:** Semantic versioning (e.g., `0.1.0`)
- **Usage:** `updater.py` reads this at startup and compares to GitHub releases
- **Bump Procedure:** Update file, commit, tag in Git, push to GitHub

### GitHub Integration

- **Release Source:** GitHub repository `tanveerm176/Attendance-OCR-App`
- **Auto-Update:** Pulls `.exe` assets from the latest GitHub release
- **URL:** `https://api.github.com/repos/tanveerm176/Attendance-OCR-App/releases/latest`
- **Fallback:** If network unavailable, silently skips update and continues

---

## Phase 2 & Phase 3 (Future)

### Phase 2 — GUI (Desktop Application)

**Directory:** `phase2-gui/gui/`

**Status:** Stub (empty)

**Intended Scope:**
- Graphical file picker (instead of CLI dialog)
- Real-time processing status display
- Manual review interface for low-confidence matches
- Direct Excel export without CLI prompts

**Planned Stack:** PyQt5, Tkinter, or wxPython

### Phase 3 — Web Application

**Directory:** `phase3-web/`

**Status:** Stubs (empty)

**Structure:**
- `routes.py` — Flask/Django endpoints
- `static/` — CSS, JavaScript, images
- `templates/` — HTML page templates

**Intended Scope:**
- Web interface for batch upload
- Live processing dashboard
- Historical audit logs
- Cloud storage integration (S3)

**Planned Stack:** Flask or Django, PostgreSQL, AWS S3

---

## Testing Strategy

### Unit Tests

Located in `tests/` directory, organized by module:

| Test File | Covers | Status |
|-----------|--------|--------|
| `test_ingestion.py` | PDF rendering | Implemented |
| `test_table_detection.py` | Line detection | Implemented |
| `test_img_cropping.py` | Region extraction | Implemented |
| `test_ocr.py` | Tesseract preprocessing | Implemented |
| `test_classification.py` | Attendance color classification | Implemented |
| `test_reconciliation.py` | Name cleaning & fuzzy matching | Implemented |
| `test_exceptions.py` | Exception classes | Implemented |

### Test Fixtures

Located in `tests/sample_scans/`:

- `present_cell.png` — sample "Present" mark image
- `absent_cell.png` — sample "Absent" mark image
- `df_fuzzy_names.csv` — sample OCR names for matching tests
- `OCR_Name_Attendance.csv` — sample attendance data

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_classification.py

# Run with coverage
pytest --cov=ocr_pipeline tests/
```

### Pytest Configuration

**File:** `pytest.ini`

```ini
[pytest]
addopts = --ignore=tests/__pycache__
```

---

## Typical Workflow

### Processing a Single Attendance Sheet

1. **User launches app:**
   ```bash
   python main.py
   ```

2. **App checks for updates** (via `updater.check_for_update()`)

3. **File dialog opens** — user selects a PDF scan of the sign-in sheet

4. **Date prompt** — user enters sign-in date (MM/DD/YYYY)

5. **Pipeline processes PDF:**
   - Renders PDF page 1
   - Detects table grid
   - Extracts names via OCR
   - Classifies attendance marks (Present/Absent)
   - Matches names to roster (fuzzy)
   - Flags low-confidence matches

6. **Results exported to Excel:**
   - Filename: `output/audit_{date-with-dashes}.xlsx`
   - Columns: ocr_name, cleaned_name, matched_name, match_score, status, flag, date

7. **Summary printed** (when `reporting/summary.py` is implemented)

8. **Audit log written** (when `reporting/logger.py` is implemented)

### Batch Processing Multiple Sheets

(Planned flow per `main.py` docstring)

1. CLI argument: `--input /path/to/folder`
2. Script iterates over all `.pdf` files in folder
3. For each PDF, runs the single-sheet flow above
4. Concatenates all results into one batch
5. Exports combined results to single Excel file
6. Writes batch log with statistics

---

## Error Handling

### Pipeline Exceptions

Defined in `ocr_pipeline/exceptions.py`:

- **`TableDetectionError`** — Grid detection failed (e.g., too few lines)
  - **Trigger:** Insufficient vertical/horizontal lines found
  - **Recovery:** User must manually check PDF quality or adjust config thresholds

- **`OCRExtractionError`** — Cell OCR result empty or unusable
  - **Trigger:** Tesseract returns empty string or unreadable noise
  - **Recovery:** Flag row as `OCRExtractionError` and let user review; do not crash

- **`NoMatchFoundError`** — Name cannot be matched to roster
  - **Trigger:** Fuzzy match score below threshold for all roster entries
  - **Recovery:** Flag row as `NoMatchFoundError` (or `Low Match - Needs Review` if marginal) and export to Excel

### User-Facing Error Recovery

- **Update check fails** → Silently logs and continues (network unavailable is normal)
- **PDF file not selected** → Raises `ValueError("No PDF selected — cannot continue.")`
- **Invalid date format** → Reprompts user until valid MM/DD/YYYY is entered
- **Roster file missing** → Should raise `FileNotFoundError` (to be handled in `main.py`)

---

## Key Design Decisions

### Why HSV for Attendance Classification?

- **RGB is lighting-sensitive** — the same ink can appear different under different lighting
- **HSV separates hue from brightness** — hue (red vs. blue) is more robust to lighting variation
- **Fallback to RGB channel difference** — for faint marks where saturation is too low to trust hue

### Why Fuzzy Matching?

- **OCR errors are inevitable** — handwriting and scan quality introduce junk characters
- `token_sort_ratio` handles reordered names (e.g., "John Smith" vs. "Smith, John")
- Threshold tunable per deployment (default 80 for strict, can lower for more matches)

### Why Separate Name Cleaning from Matching?

- Keeps the stages orthogonal — cleaning removes junk, matching finds roster entry
- Allows different matching algorithms (fuzzy, exact, phonetic) without changing cleaning logic
- Simpler testing — can test each stage independently

### Why in-Memory DataFrames, Not Repeated Excel I/O?

- Performance — concatenating in-memory is orders of magnitude faster than repeated disk writes
- Simplicity — pandas excels at DataFrame manipulation
- Future flexibility — when moving to cloud, in-memory staging makes cloud uploads easier

---

## Known Limitations (MVP)

1. **Single page per PDF** — only processes page 1 (multi-page support planned)
2. **Fixed table structure** — assumes columns 0–5 always contain data (configurable, but not dynamic)
3. **No manual review UI** — low-confidence matches exported to Excel for manual review only
4. **Tesseract path hardcoded** — Windows-specific path in `ocr.py` (should be configurable)
5. **No audit logging** — `reporting/logger.py` is a stub
6. **No statistics summary** — `reporting/summary.py` is a stub
7. **Batch mode not fully wired** — docstring describes it, but code incomplete

---

## Future Enhancements

### Short Term (Next MVP Iteration)

- [ ] Refactor to use data models 'Attendance Record' + 'Daily Sheet'
- [ ] Refactor Fuzzy Matching to match per row loop instead of ingesting an entire DataFrame
- [ ] Complete `main.py` batch processing logic
- [ ] Add multi-page PDF support
- [ ] Cut from the last horizontal line to the last img pixel, ocr for any handwritten names, flag on DF for manual entry 
- [ ] Add page source column for each row
- [ ] Use a `Attendance Master Excel` file that is updated every time a new set of sheets are processed
- [ ] Implement `reporting/summary.py` (statistics display)
- [ ] Implement `reporting/logger.py` (audit trail)
- [ ] Make Tesseract path configurable

### Additional Features
- [ ] ISEP system alignment where ever possible (Docker)
- [ ] PostgreSQL for multi db reconciliation 
- [ ] Find a way to integrate Apache Airflow if possible
- [ ] TrOCR for signature matching

### Medium Term (Phase 2)

- [ ] Build desktop GUI (PyQt5)
- [ ] Manual review interface for flagged matches
- [ ] Advanced table structure detection (non-fixed layouts)
- [ ] Support for multiple rosters/schools

### Long Term (Phase 3 & Beyond)

- [ ] Web application (Flask/Django)
- [ ] Cloud storage (AWS S3, Azure Blob)
- [ ] Database (PostgreSQL) for historical data
- [ ] Mobile app for remote processing
- [ ] API for third-party integration


