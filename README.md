# Attendance OCR App

The Attendance OCR App processes scanned attendance-sheet PDFs, extracts student names and sign-in status, compares extracted names with a roster, and exports results to Excel. Rows that need human attention can be reviewed in a Tkinter window that displays the name crop and lets the operator select a roster name.

> Review the [SONYC Audit Application Flowchart](<docs/SONYC Audit Application Flowchart.pdf>) for the application's high-level workflow. The OCR-specific steps are documented in [OCR Data Flow](<docs/OCR_DATA_FLOW.md>).

## What the app does

- Renders every page in each selected PDF to an image.
- Detects and crops the attendance table.
- Uses Tesseract OCR to read names.
- Classifies sign-in cells as `Present`, `Absent`, or `EMPTY CELL`.
- Fuzzy-matches OCR names to the configured roster and flags uncertain results.
- Opens a manual review window for flagged names. The operator can select a roster name or skip a row.
- Exports the resulting records to a date-grouped Excel workbook.

The app assists with transcription; review the output before using it as an authoritative attendance record.

## Requirements

- Windows
- Python 3.10 or newer
- Tesseract OCR installed separately from Python packages
- A roster file at `data/student_roster_26.txt`
- Scanned attendance sheets in PDF format

The default roster is configured in [`io_utils/roster_input.py`](<io_utils/roster_input.py>). Names are loaded from one line per student.

## Setup

From the repository root, create and activate a virtual environment, then install the project and its test dependency:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Install Tesseract OCR for Windows and make sure `tesseract.exe` is available on `PATH`. If it is not on `PATH`, copy [`.env.example`](<.env.example>) to `.env` and set `TESSERACT_CMD` to the full path to `tesseract.exe`, for example:

```text
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

The application loads `.env` at startup. Do not commit machine-specific `.env` settings.

## Run the app

From the repository root:

```powershell
python main.py
```

When prompted, choose the folder containing the PDFs. The app processes PDF files in case-insensitive filename order. For each PDF, it runs OCR and reconciliation, then opens the visual review window if records need review. Review is per PDF, before the app moves on to the next PDF.

### Headless batch processing

For Docker or other headless environments, run the batch entry point instead of `main.py`. It processes PDFs without opening Tkinter and leaves uncertain names flagged for correction in Excel:

```powershell
attendance-ocr-batch `
  --input-dir .\attendance-scans `
  --output .\output\attendance.xlsx
```

The bundled roster is used by default. Pass `--roster .\data\student_roster_26.txt` to use a different roster. Each date worksheet ends with a `Source PDF Path` column containing a clickable PDF filename; the hyperlink cell is merged across rows from the same source PDF. When running in Docker, `--source-path-root` can point the hyperlink at the corresponding host-side input directory, for example `--source-path-root "C:\Attendance\Input"`.

### Build and run with Docker

GitHub Actions builds and smoke-tests the Docker image on pushes to `main` or `feature/headless-cli`, pull requests targeting `main`, and manual workflow runs. The workflow does not publish the image.

To run it locally on a machine with Docker installed, build the image from the repository root:

```sh
docker build -t attendance-ocr:local .
```

Mount the PDFs, roster, and output directory when starting the container. Roster and attendance files are intentionally excluded from the image:

```sh
docker run --rm \
  --mount type=bind,source=/path/to/pdfs,target=/data/input,readonly \
  --mount type=bind,source=/path/to/roster.txt,target=/data/roster.txt,readonly \
  --mount type=bind,source=/path/to/output,target=/data/output \
  attendance-ocr:local \
  --input-dir /data/input \
  --output /data/output/attendance.xlsx \
  --roster /data/roster.txt \
  --source-path-root /path/to/pdfs
```

In the review window:

- Inspect the displayed name crop, OCR text, current flag, and match score.
- Choose a name from the roster and select **Use selected name** to resolve the record.
- Select **Skip** to leave the record's existing name and unresolved flag unchanged.
- Closing the window leaves any not-yet-reviewed records unresolved.

Confirmed choices receive the flag `Resolved - Manual Review`.

## Output

The app creates an `output` directory relative to the current working directory and writes a workbook named after the selected folder and run date, for example:

```text
output/Attendance Batch_10-20-2026.xlsx
```

The workbook has one worksheet per detected attendance date, named `MM-DD-YYYY`. The exported columns are:

| Column | Meaning |
| --- | --- |
| Date | Attendance-sheet date |
| OCR Raw | Name text returned by OCR, or a handwritten-name marker |
| Attendance Status | `Present`, `Absent`, or `EMPTY CELL` |
| OCR Cleaned | OCR name after punctuation/digit cleanup |
| Matched Name | Best roster match or operator-confirmed selection |
| Matched Score | Fuzzy-match score |
| Flag | Match/review status |

Image crops are temporary in-memory data used by the review interface. They are removed before results are combined and exported.

## Configuration

| Setting | Default | Description |
| --- | --- | --- |
| `DPI` | `300` | PDF render resolution, read from the environment |
| `TESSERACT_CMD` | unset | Optional full path to the Tesseract executable |
| `fuzzy_match_threshold` | `80` | Scores below this are marked `Low Match - Needs Review` |
| `low_match_floor` | `30` | Scores below this are treated as no match |

The matching thresholds are defined on [`PipelineConfig`](<ocr_pipeline/config.py>).

## OCR data flow

The extraction and per-record handoff are described in [docs/OCR_DATA_FLOW.md](<docs/OCR_DATA_FLOW.md>). This covers PDF rendering, page/table processing, name OCR, attendance classification, roster reconciliation, crop-based manual review, and export handoff.

## Tests

Run the suite from the repository root:

```powershell
python -m pytest
```

Some older tests rely on sample image/PDF assets and fixtures; check the test output for environment-specific missing-resource failures.

## Project layout

| Path | Purpose |
| --- | --- |
| `main.py` | Folder selection, PDF batch processing, manual-review callback, and Excel export |
| `ocr_pipeline/` | PDF ingestion, table detection, cropping, OCR, classification, reconciliation, and manual review |
| `io_utils/` | Roster loading and Excel output/formatting |
| `data/` | Configured roster text files |
| `docs/` | Application workflow, design notes, and OCR data-flow documentation |
| `tests/` | Automated tests |
