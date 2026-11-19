# OCR Data Flow

The pipeline passes attendance dataclasses between stages. A pandas DataFrame
is constructed inside the Excel exporter, not passed through the OCR or
review stages.

## Processing

1. The desktop entry point selects a folder, loads a roster, and creates an
   `OCRPipeline`. The headless CLI accepts paths and an optional host-visible
   source path prefix.
2. Each workflow discovers PDFs in case-insensitive filename order and calls
   `OCRPipeline.run` for each one. The result is a `DailyAttendance` holding
   its source path, optional detected date, and ordered `AttendanceRecord`s.
3. `pdf_to_image` renders all pages into RGB arrays. Each page is deskewed,
   table boundaries are detected, and student rows and the handwritten
   region are located.
4. For each normal row, the name is OCR'd, attendance is classified, and
   `match_name` cleans and reconciles the name against the roster. A grayscale
   crop is copied only if the resulting flag needs review.
5. A detected handwritten region produces a separate `NEED-MANUAL-ENTRY`
   record with a copied RGB crop. Detection indicates text, not the student's
   identity.
6. In the desktop workflow, manual review runs before the next PDF. Confirmed
   records receive the selected name and `Resolved - Manual Review` flag,
   become reviewed, and lose their crop. Skipped records remain unresolved
   with their crop. The headless workflow discards review crops and retains
   the flags for the exported workbook.
7. The sheets are collected in an `AttendanceBatch`. `export_attendance`
   flattens records into DataFrame columns, groups them by sheet date, and
   writes formatted Excel worksheets. It includes source PDF hyperlinks when
   display paths are provided. It rejects empty batches and missing dates;
   review crops are never written to Excel.

## Memory and date notes

- Flagged normal-row crops and handwritten crops are copied so they do not
  retain their larger source image. Skipped desktop-review crops remain in
  memory with their records.
- `pdf_to_image` currently retains all rendered pages for a PDF until
  `OCRPipeline.run` finishes; page rendering is not yet lazy.
- A sheet date belongs to each `DailyAttendance`. An undetected date is `None`
  and fails export; there is no fallback prompt in the current pipeline.
