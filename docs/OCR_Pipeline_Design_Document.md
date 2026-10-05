# Attendance OCR Pipeline

## Technical Design Document  ·  RiseBoro

*Draft  ·  July 01, 2026*

## 1. Purpose

This document describes the design of a Python-based OCR pipeline that extracts student attendance data from scanned sign-in sheets and compares the extracted records against the attendance database exported from RiseBoro's student information system. The goal is to surface discrepancies — cases where the physical sheet and the database disagree — so that data entry errors can be identified and corrected.

## 2. Problem Statement

Sign-in sheets are completed by hand each day and later entered into the attendance database manually. This creates opportunity for transcription error. The sheets themselves serve as the authoritative physical record, but because the roster changes throughout the year, cross-referencing by hand is time-consuming and error-prone.

Key constraints of the source material:

- Sheets are multi-page: page 1 contains a title and date header above the table; subsequent pages contain only the table.

- The table has 8 columns: #, Name, Grade, Well Check, Sign In, Time In, Sign Out, Time Out. Only Name and Sign In are extracted by the pipeline.

- Student names are pre-printed in a fixed font. The Sign In cell is filled by hand — a blue ink signature for present, or a red line drawn through the cell for absent.

- The red absent line begins in the Well Check column and continues through Sign In. Both columns must be considered together for reliable absent detection.

- The student roster changes during the year; the set of names on any given sheet reflects the roster at that point in time.

- Scans are provided as PDF files and may have slight rotation from the scanner feed.

## 3. System Overview

The pipeline is implemented in Python and runs as a command-line tool via main.py. It accepts a folder of scanned images (one per page) and a database export file (Excel or CSV), and produces a reconciliation Excel workbook.

### 3.1 Input

| **Input** | **Description** |
| --- | --- |
| **Scanned pages** | PNG or JPEG images, one file per page, grouped by date |
| **Database export** | Excel or CSV with columns: student name, date, status (P/A) |
| **Name roster** | List of canonical student names used for fuzzy matching |

### 3.2 Output

| **Output** | **Description** |
| --- | --- |
| **Reconciliation workbook** | One sheet per date. Rows flagged red for P/A mismatch, yellow for low name-match confidence. |
| **Unmatched names log** | Students whose OCR name could not be confidently matched to any roster entry. |

## 4. Pipeline Stages

The pipeline processes each scanned page through seven sequential stages.

### Stage 0 — PDF Ingestion (fitz / PyMuPDF)

Scans are delivered as multi-page PDF files. OpenCV cannot read PDFs directly, so each page is first rendered to a raster image using PyMuPDF (imported as fitz). The resulting image is a NumPy array in BGR format, compatible with all subsequent OpenCV operations.

**Approach**

- Open the PDF with fitz.open().

- Iterate over pages using doc.load_page(page_index).

- Render each page to a Pixmap at a controlled DPI using page.get_pixmap(matrix=fitz.Matrix(dpi/72, dpi/72)).

- Convert the Pixmap to a NumPy array and reorder channels from RGB to BGR for OpenCV compatibility.

**Key parameter**

| **Render DPI** | 200–300 DPI recommended. Higher DPI improves OCR accuracy on small printed text but increases memory and processing time. 300 DPI is the standard for document OCR. |
| --- | --- |

The full-color BGR image produced by this stage is preserved throughout the pipeline. Grayscale conversions for edge detection operate on copies; the original color image is used for attendance classification in Stage 5.

### Stage 1 — Deskew

Scanned pages often have a slight rotational offset from the scanner feed. An uncorrected skew causes Hough line detection in later stages to see diagonal lines instead of clean horizontals and verticals, degrading both table detection and row slicing.

**Approach**

- Convert to grayscale and apply Gaussian blur (5×5 kernel).

- Run Canny edge detection to produce a binary edge map.

- Apply HoughLinesP to detect line segments.

- Compute the median angle of all near-horizontal lines detected.

- Rotate the full color image by the negative of that angle using an affine transform.

**Key parameters**

| **Canny thresholds** | 50 / 150 — suitable for high-contrast black-on-white print |
| --- | --- |
| **HoughLinesP minLineLength** | image_width // 4 — excludes short text strokes |
| **Angle filter for "horizontal"** | < 10° or > 170° from x-axis |

### Stage 2 — Table Isolation

Page 1 of each sheet contains a title and date header above the table. Page 2 and beyond contain only the table. To treat all pages consistently, the table region is detected and cropped before any further processing.

**Approach**

- Run Canny + HoughLinesP on the deskewed image.

- Separate detected segments into horizontal and vertical groups by angle.

- The outer table boundary is: topmost horizontal, bottommost horizontal, leftmost vertical, rightmost vertical.

- Crop the color image to that bounding rectangle.

**Why this handles the page 1 / page 2 difference**

Because the crop is driven by line detection rather than fixed pixel coordinates, the header on page 1 is automatically excluded — the top boundary of the table is wherever the first full-width horizontal line appears, regardless of what is above it.

### Stage 3 — Date Extraction (page 1 only)

The session date appears as printed text in the header region of page 1, above the table. It is extracted using Tesseract OCR on the header crop (the region above the top table boundary) and then parsed into a normalized date string for use as the join key against the database export.

**Approach**

- Crop the region from y=0 to y=table_top on the deskewed image.

- Run Tesseract with --psm 6 (uniform block of text).

- Use a regex pattern to locate a date string (e.g. MM/DD/YYYY or Month DD, YYYY).

- Normalize to ISO format (YYYY-MM-DD) for reliable joining.

**Edge case**

- If no date is found in the header (e.g. damaged scan), prompt the user to supply the date manually via CLI argument.

### Stage 4 — Row and Column Segmentation

With the table isolated, the internal grid structure is detected to locate individual cell regions for each student row.

**Row boundaries**

- Run HoughLinesP on the table crop with minLineLength = table_width // 2.

- Collect the y-coordinate midpoint of each detected horizontal segment.

- Merge y-values within 10px of each other (Hough often detects the same printed line 2–3 times at slightly different positions).

- Consecutive pairs of merged y-values define each row's pixel extent.

**Column boundaries**

The table has 8 columns: #, Name, Grade, Well Check, Sign In, Time In, Sign Out, Time Out. All 8 vertical dividers are detected, but only two column regions are extracted per row:

| **Column region** | **Usage** |
| --- | --- |
| **Name** | Second column (between vertical dividers 1 and 2). Passed to Tesseract for OCR. |
| **Well Check + Sign In** | Third and fourth columns combined (between vertical dividers 2 and 4). Used together for attendance classification — the absent red line originates in Well Check and extends into Sign In, so both cells must be included in the crop to ensure the red line is captured regardless of where it starts. |

Vertical dividers are detected as x-coordinate midpoints of near-vertical Hough segments spanning at least table_height // 3. They are sorted left to right and indexed to extract the correct column boundaries.

### Stage 5 — Per-Row Data Extraction

For each detected row, two extractions are performed.

**5a — Name extraction (OCR)**

The name cell is preprocessed before being passed to Tesseract to reduce character recognition errors caused by thin or broken stroke rendering at scan resolution.

**Preprocessing steps**

- Crop the Name cell from the color image using row and column boundaries.

- Convert to grayscale and apply a morphological close operation (cv2.morphologyEx with MORPH_CLOSE).

- Morphological close fills small gaps within letter strokes by dilating then eroding — this reconnects broken strokes that Tesseract would otherwise misread as separate characters or noise.

- The structuring element is a small horizontal rectangle (e.g. 2×1 or 3×1 kernel), chosen to join horizontal stroke gaps without merging adjacent characters.

- Pass the processed image to Tesseract with --psm 7 (single line of text).

- Strip whitespace and punctuation artifacts from the result.

Note: Tesseract operates on the pre-printed font, which is consistent and machine-readable. The morphological close step handles the most common failure mode — thin font strokes that scan as interrupted lines. Remaining character-level errors are corrected downstream by fuzzy matching.

**5b — Attendance classification (color analysis)**

The attendance state is determined by pixel color analysis on a combined crop of the Well Check and Sign In columns. No OCR is used. The two columns are analyzed together because the red absent line originates in Well Check and extends rightward into Sign In — cropping Sign In alone risks missing the beginning of the line if it starts just left of the column boundary.

| **State** | **Detection method** |
| --- | --- |
| **Present (P)** | Blue ink signature in Sign In — high blue channel relative to red among non-white pixels in the combined crop |
| **Absent (A)** | Red line spanning Well Check into Sign In — high red channel, low blue channel among non-white pixels |
| **Empty cell** | Fewer than 50 non-white pixels in the combined crop — treated as Absent |

Non-white pixels are defined as any pixel where at least one channel is below 220. This masks the paper background and focuses the color test on the actual ink. Channel ratio thresholds (starting values: red > 150 and red > blue × 1.5 for absent; blue > red × 1.2 for present) should be calibrated against real scan samples, as scanner color profiles vary.

### Stage 6 — Name Reconciliation (Fuzzy Matching)

OCR output is matched to the canonical student roster using fuzzy string similarity. This corrects character-level OCR errors without requiring perfect recognition.

**Library**

- rapidfuzz — token_sort_ratio scorer, which normalizes word order before comparison. This handles cases where Tesseract drops a comma or reverses first/last name order.

**Matching logic**

- For each OCR-read name, find the closest match in the known roster.

- If similarity score ≥ 85: accept the match, record the canonical name.

- If similarity score < 85: record as unmatched, flag for manual review.

- Threshold of 85 is a starting point — calibrate against real scan samples.

**Why fuzzy matching over exact matching**

Exact matching fails on any single character error. A threshold-based fuzzy approach tolerates 1–3 character substitutions (typical Tesseract error rate on clean printed fonts) while still rejecting genuinely wrong matches between similar but distinct names.

### Stage 7 — Reconciliation and Output

The OCR-extracted records and database export are joined on (matched_name, date) using a pandas outer merge. The outer join ensures that students appearing in only one source are visible in the output rather than silently dropped.

**Flags applied to each row**

| **Flag** | **Condition** |
| --- | --- |
| **Mismatch** | status_ocr ≠ status_db for the same student on the same date |
| **Low confidence** | Fuzzy match score < 85 — the name match itself is uncertain |
| **Sheet only** | Student appears on the physical sheet but not in the database export for that date |
| **Database only** | Student appears in the database export but was not found on the physical sheet |

**Excel output format**

- One worksheet per date processed.

- Red row fill: confirmed P/A mismatch.

- Yellow row fill: low confidence name match (comparison may be unreliable).

- Unfilled rows: clean — no action needed.

- Columns: Matched Name, OCR Read (raw), Match Confidence, Sheet Status, Database Status, Mismatch, Low Confidence, Sheet Only, Database Only.

## 5. Dependencies

| **Package** | **Role** |
| --- | --- |
| **PyMuPDF (fitz)** | PDF ingestion — converts each page of a scanned PDF to a high-resolution NumPy-compatible image for OpenCV processing |
| **opencv-python** | Image preprocessing, Canny edge detection, HoughLinesP, affine rotation, morphological operations |
| **numpy** | Array operations, angle computation, pixel masking |
| **pytesseract** | OCR for student names and date header (wraps Tesseract engine) |
| **Tesseract OCR** | System-level install required — not a Python package |
| **rapidfuzz** | Fuzzy string matching for name reconciliation |
| **pandas** | Dataframe construction, outer merge, reconciliation logic |
| **openpyxl** | Excel output with conditional row color formatting |

## 6. Module Structure

The codebase is organized as a hybrid of Jupyter notebooks (for prototyping each stage) and .py modules (for the production pipeline).

| **File** | **Responsibility** |
| --- | --- |
| **main.py** | Entry point. Accepts CLI arguments: input folder, database export path, output path, optional date override. |
| **pdf_ingestor.py** | Stage 0. Opens PDF with fitz, renders each page to a BGR NumPy array at the configured DPI. |
| **deskew.py** | Stage 1. Detects rotation angle and returns corrected image. |
| **table_detector.py** | Stages 2–3. Isolates table crop and extracts date from header. |
| **segmenter.py** | Stage 4. Detects all 8 column boundaries and row extents; returns (y_top, y_bot) pairs and the x-coordinates of the Name and Well Check/Sign In column regions. |
| **extractor.py** | Stage 5. Morphological close + Tesseract OCR for names; color channel analysis for attendance using combined Well Check + Sign In crop. |
| **reconciler.py** | Stages 6–7. Fuzzy matching, outer merge, flag computation. |
| **exporter.py** | Writes the final reconciliation Excel workbook with color formatting. |
| **debug_context.py** | Optional debug mode. DebugContext object passed through all stages — saves annotated images per stage when enabled via --debug CLI flag. |
| **notebooks/** | One Jupyter notebook per stage for development and visual debugging. |

## 7. Debug Mode

The pipeline includes an optional visual debug mode designed to make integration and bug diagnosis fast. When enabled, each stage saves an annotated image showing exactly what it detected — table boundaries, row lines, column dividers, OCR reads, and attendance classifications. This makes it possible to pinpoint which stage produced a bad result without guessing or adding temporary print statements.

Debug mode is implemented as a DebugContext object instantiated in main.py and passed through every stage function. Each stage calls dbg.save() with its annotated output. When debug is disabled (the default), all save calls are no-ops with zero performance cost.

### 7.1 Enabling Debug Mode

Debug mode is activated via CLI flags:

| **Flag** | **Effect** |
| --- | --- |
| **--debug** | Enable debug output for all pages in the run |
| **--debug-page N** | Enable debug output for page N only — useful when a specific page is misbehaving and saving images for every page would create noise |
| **--debug-dir PATH** | Override the output directory for debug images (default: debug_output/ next to the input file) |

### 7.2 Annotated Output Per Stage

Each stage produces one annotated image per page. Images are saved as JPEGs named by date, page number, and stage:

Example: 2024-11-04_p1_stage_02_table_boundary.jpg

| **Stage** | **What is annotated** |
| --- | --- |
| **Stage 0 — Ingest** | Image dimensions and render DPI printed as a text overlay on the raw page image. |
| **Stage 1 — Deskew** | Detected skew angle printed as overlay. Before and after images saved side by side for direct comparison. |
| **Stage 2 — Table boundary** | The four outer table boundary lines drawn in cyan over the full page. Immediately reveals if a boundary was missed or incorrectly placed. |
| **Stage 3 — Date extraction** | The header crop region highlighted with a colored rectangle. Extracted date string printed as a text overlay. |
| **Stage 4 — Grid** | All detected horizontal row lines drawn in green, all vertical column dividers drawn in blue, overlaid on the table crop. Makes row merging errors and missed dividers immediately visible. |
| **Stage 5 — Cells** | Each name cell outlined with the Tesseract OCR result printed above it. Each attendance cell outlined in green (P) or red (A) with the classification label inside. Low-confidence cells outlined in yellow. |
| **Stage 6 — Fuzzy match** | Match confidence score printed next to each name. Rows below the 85-point threshold highlighted in yellow. |

### 7.3 Debug Output Folder Structure

All images for a run are written to a single folder, named and ordered so they can be reviewed sequentially:

| **Filename** | **Contents** |
| --- | --- |
| **2024-11-04_p1_stage_00_ingest.jpg** | Page 1, Stage 0 |
| **2024-11-04_p1_stage_01_deskew.jpg** | Page 1, Stage 1 |
| **2024-11-04_p1_stage_02_table_boundary.jpg** | Page 1, Stage 2 |
| **2024-11-04_p1_stage_03_header_date.jpg** | Page 1, Stage 3 |
| **2024-11-04_p1_stage_04_grid.jpg** | Page 1, Stage 4 |
| **2024-11-04_p1_stage_05_cells.jpg** | Page 1, Stage 5 |
| **2024-11-04_p1_stage_06_fuzzy.jpg** | Page 1, Stage 6 |
| **2024-11-04_p2_stage_00_ingest.jpg** | Page 2, Stage 0 — and so on |

### 7.4 Recommended Debug Workflow

When a reconciliation output row looks wrong, the recommended investigation sequence is:

- Identify which date and page the suspect row came from.

- Re-run main.py with --debug --debug-page N for that page only.

- Open stage_04_grid.jpg first — confirm the row boundaries are correct. If rows are merged or split incorrectly, the problem is in the segmenter and all downstream results for that page are unreliable.

- If the grid looks correct, open stage_05_cells.jpg — check the OCR read for the name cell and the color label on the attendance cell.

- If the name OCR read looks garbled, the issue is likely morphological close kernel size or DPI. If the attendance label is wrong, check the color thresholds against the actual cell crop.

- If both cells look correct but the reconciliation still flagged the row, open stage_06_fuzzy.jpg and check the match confidence — a score near the threshold may have matched the wrong roster entry.

## 8. Known Risks and Mitigations

| **Risk** | **Mitigation** |
| --- | --- |
| **PDF render DPI too low** | Rendering below 200 DPI produces images where thin font strokes merge or break, increasing OCR errors even after morphological close. If name recognition degrades, raise DPI to 300 before tuning other parameters. |
| **Scan rotation exceeds deskew range** | Affine rotation handles typical scanner skew (< 5°). Severely rotated scans will need manual correction before processing. |
| **Hough misses a table boundary line** | Fallback: if fewer than 2 horizontals or 2 verticals are found after filtering, log a warning and skip the page rather than producing a bad crop. |
| **Morphological close kernel too large** | An oversized kernel joins adjacent characters, producing merged glyphs that Tesseract misreads. Start with a 2×1 or 3×1 kernel and increase only if strokes are still broken on real scan samples. |
| **Red line starts in Well Check but does not reach Sign In** | The combined Well Check + Sign In crop handles this by ensuring the full extent of the line is captured. If classification still misses short lines, expand the crop leftward by one additional column boundary. |
| **Date not parseable from header** | CLI flag --date YYYY-MM-DD allows manual override. If neither source provides a date, the page is skipped and logged. |
| **OCR name below fuzzy threshold** | Flagged in output as unmatched. Accumulated in a separate log file for batch manual review at end of run. |
| **Similar student names causing wrong fuzzy match** | Match confidence is always written to the output. A score of 85–90 on names similar to another roster entry should be reviewed. Threshold can be raised if false matches are observed. |
| **Color classification fails on faded ink or poor scan quality** | The 50-pixel minimum non-white threshold and channel ratio tests are tunable. Enable debug mode (Section 7) to save annotated cell crops for the affected page and inspect the actual pixel values before adjusting thresholds. |
| **Roster changes mid-year** | The roster file should reflect the roster at the time of the sheet being processed. Students added or removed mid-year will generate Sheet Only or Database Only flags — these are expected and not errors. |

## 9. Out of Scope

- Reading or interpreting student signatures — only presence/absence of blue ink is classified.

- Extracting data from columns other than Name and Sign In (i.e. #, Grade, Well Check, Time In, Sign Out, Time Out are detected for layout purposes only and not extracted).

- Automatic correction of database records — the pipeline flags discrepancies only; corrections are made manually.

- Handling sheet formats other than the 8-column layout described above.

- Real-time or networked database access — the pipeline operates on exported files only.
