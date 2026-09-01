# Project Structure

Attendance OCR App processes scanned attendance-sheet PDFs, detects table boundaries, extracts text with OCR, reconciles names against a roster, and produces audit-ready output. The repository is organized as follows.

## Root Files

| File | Description |
| --- | --- |
| `main.py` | Command-line application entry point. It currently performs the update check and documents the planned end-to-end batch workflow. |
| `config.py` | Central configuration values, including OCR render DPI, optional S3 bucket configuration, and the output directory. |
| `updater.py` | Checks GitHub for a newer release, prompts for updates, downloads a replacement executable, and relaunches the packaged app. |
| `VERSION` | Stores the current application version used by the updater. |
| `requirements.txt` | Lists the Python dependencies required by the application and its OCR/image-processing pipeline. |
| `pytest.ini` | Pytest configuration for running the test suite. |
| `main.spec` | PyInstaller build specification for packaging `main.py` and the `VERSION` file into an executable. |
| `auto-update-and-phases.txt` | Project notes describing the auto-update mechanism and planned application phases. |

## OCR Pipeline

| File | Description |
| --- | --- |
| `ocr_pipeline/__init__.py` | Marks `ocr_pipeline` as a Python package. |
| `ocr_pipeline/ingestion.py` | Opens the first page of a scanned PDF, renders it at the configured DPI, and returns it as a NumPy RGB image. |
| `ocr_pipeline/table_detection.py` | Uses OpenCV thresholding and morphological operations to detect and cluster vertical and horizontal table-grid lines. |
| `ocr_pipeline/img_cropping.py` | Provides validated vertical and horizontal image-cropping helpers for extracting table cells or regions. |
| `ocr_pipeline/ocr.py` | Preprocesses image cells and sends them to Tesseract OCR using a fixed single-line recognition configuration. |
| `ocr_pipeline/classification.py` | Reserved for classifying attendance values or other extracted sheet fields. It is currently a placeholder. |
| `ocr_pipeline/deskew.py` | Reserved for correcting rotation or skew in scanned sheets before table detection and OCR. It is currently a placeholder. |
| `ocr_pipeline/reconciliation.py` | Reserved for cleaning OCR names, matching them to the roster, and flagging low-confidence matches. It is currently a placeholder. |

## Input and Output

| File | Description |
| --- | --- |
| `io/__init__.py` | Marks `io` as a Python package for input and output helpers. |
| `io/roster_input.py` | Reserved for loading and validating the student roster. It is currently a placeholder. |
| `io/excel_output.py` | Reserved for writing reconciled attendance data to an Excel workbook. It is currently a placeholder. |
| `data/student_roster.txt` | Local source roster containing student names used for reconciliation. |

## Reporting

| File | Description |
| --- | --- |
| `reporting/__init__.py` | Marks `reporting` as a Python package. |
| `reporting/summary.py` | Reserved for printing a processing summary after a batch is completed. It is currently a placeholder. |
| `reporting/logger.py` | Reserved for recording processing details and batch results in a log. It is currently a placeholder. |

## Phase 2 Desktop GUI

| File | Description |
| --- | --- |
| `phase2-gui/gui/app.py` | Planned desktop GUI application entry point for interactive attendance-sheet processing. It is currently a placeholder. |
| `phase2-gui/gui/widgets.py` | Planned reusable GUI widgets and controls for the Phase 2 desktop interface. It is currently a placeholder. |

## Phase 3 Web Application

| File | Description |
| --- | --- |
| `phase3-web/routes.py` | Planned web route definitions for the browser-based application. It is currently a placeholder. |
| `phase3-web/static/` | Intended location for web assets such as stylesheets, JavaScript, and images. |
| `phase3-web/templates/` | Intended location for server-rendered HTML templates. |

## Tests

| File or directory | Description |
| --- | --- |
| `tests/__init__.py` | Marks `tests` as a Python package. |
| `tests/test_ingestion.py` | Tests PDF loading and image rendering behavior. |
| `tests/test_img_cropping.py` | Tests image crop bounds and returned regions. |
| `tests/test_table_detection.py` | Tests detection of vertical and horizontal table boundaries. |
| `tests/test_ocr.py` | Tests OCR preprocessing and text extraction behavior. |
| `tests/test_reconciliation.py` | Tests planned roster reconciliation behavior. |
| `tests/sample_scans/sonyc-test.pdf` | Sample scanned attendance sheet used as test input. |

## Build Artifacts

| Path | Description |
| --- | --- |
| `build/main/` | PyInstaller-generated intermediate build output. |
| `build/main/Analysis-00.toc` | PyInstaller analysis table of contents. |
| `build/main/EXE-00.toc` | PyInstaller executable build table of contents. |
| `build/main/PKG-00.toc` | PyInstaller package build table of contents. |
| `build/main/PYZ-00.pyz` | PyInstaller Python module archive. |
| `build/main/PYZ-00.toc` | Table of contents for the Python module archive. |
| `build/main/warn-main.txt` | Warnings produced during the PyInstaller build. |
| `build/main/xref-main.html` | HTML cross-reference report generated by PyInstaller. |
| `build/main/localpycs/` | PyInstaller-generated local Python bytecode artifacts. |

## Processing Flow

1. `main.py` starts the application and checks for updates through `updater.py`.
2. `ocr_pipeline/ingestion.py` renders scanned PDFs into images.
3. Deskewing and table-boundary detection prepare the page for cell extraction.
4. `ocr_pipeline/img_cropping.py` isolates regions, and `ocr_pipeline/ocr.py` extracts text.
5. Classification and reconciliation enrich the extracted rows and compare names with `data/student_roster.txt`.
6. `io/excel_output.py` writes the audit results, while `reporting/summary.py` and `reporting/logger.py` provide status and logging.
7. The Phase 2 GUI and Phase 3 web application directories provide planned user interfaces around the same pipeline.
