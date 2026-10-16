# Attendance Reconciliation Demo Guide

This guide follows the data from the moment the program starts until the Excel
report is written. It explains which module handles each step and how the
data changes along the way.

## Overview

The audit uses three workbooks:

1. **DYCD Daily Attendance** — student ID, DYCD name, date, and DYCD status.
2. **OCR Results** — date, OCR matched name, physical-sheet status, and OCR
   review details.
3. **Roster crosswalk** — the relationship between an internal attendance
   name and a DYCD ID.

The program first maps OCR matched names to DYCD IDs using the roster. It then
compares the attendance values by **DYCD ID and date**. The final comparison
does not perform fuzzy name matching: it uses an exact name lookup after
normalizing case and whitespace. Records that cannot be matched are retained
for review.

## Typical data flow

```text
Run attendance_reconciliation.py
        |
        v
Parse command-line options and select input/output paths
        |
        v
workbook_io.py reads and validates both attendance workbooks and the roster
        |
        v
comparison.py normalizes identifiers and maps OCR names to DYCD IDs
        |
        v
comparison.py compares attendance by DYCD ID + date
        |
        v
reporting.py builds the detailed, issues, and summary tables
        |
        v
Write the Excel report and print run counts
```

The implementation is organized as follows:

```text
demo-data/
|-- attendance_reconciliation.py
|-- attendance_audit/
    |-- __init__.py
    |-- workbook_io.py
    |-- comparison.py
    |-- reporting.py
    |-- formatting.py
```

## Step 1: Start the program and select paths

Run this command from the repository root:

```text
python demo-data/attendance_reconciliation.py
```

The `main()` function in `attendance_reconciliation.py` defines four optional
command-line arguments:

- `--dycd`: DYCD Daily Attendance workbook.
- `--ocr`: OCR Results workbook.
- `--roster`: roster crosswalk workbook.
- `--output`: where to save the final report.

If no options are provided, the script uses the three example workbooks in
`demo-data/`. `_default_output_path()` creates an output filename containing
the current timestamp, so repeated runs normally produce separate reports.

Once the paths are selected, `main()` calls `reconcile_workbooks()`. That
function coordinates the remaining steps: it reads the DYCD workbook, reads
the OCR workbook, reads the roster, and passes the three resulting dataframes
to `compare_attendance()`.

## Step 2: Read and validate the input workbooks

The file-reading functions are in `attendance_audit/workbook_io.py`.
`reconcile_workbooks()` calls `read_attendance_workbook()` twice:

1. For DYCD, it passes the required columns `Date`, `ID`, `Name`, and
   `Attendance`.
2. For OCR, it passes `Date`, `OCR Raw`, `Attendance Status`, `Matched Name`,
   `Matched Score`, and `Flag`.

For each workbook, `read_attendance_workbook()`:

1. Opens the workbook and visits each worksheet.
2. Calls `_parse_sheet_date()` to confirm that the worksheet title follows
   `MM-DD-YYYY`, such as `09-14-2026`.
3. Reads the worksheet and calls `_validate_columns()` to check that all
   required headers are present.
4. Keeps only the columns needed for the audit.
5. Converts the `Date` column to dates normalized to midnight.
6. Checks that the row dates agree with the date in the worksheet title.
   A mismatch raises an error rather than silently comparing the wrong day.
7. Appends the worksheet rows to the result.
8. Combines all worksheet rows into one dataframe.

The sheet title is used as a validation check; the actual attendance join in
the comparison step uses the normalized `Date` column. Worksheets are not
matched to each other merely by their position in the workbook.

`reconcile_workbooks()` also calls `read_roster()` to read the first worksheet
of the roster workbook. That function checks for `DYCD ID` and
`Internal Roster Name`, then returns those two columns. It does not assign
IDs; the comparison step performs that lookup.

## Step 3: Prepare the roster and DYCD records

The comparison begins in `compare_attendance()` in
`attendance_audit/comparison.py`. It prepares the roster and DYCD records
before attempting any joins.

### Prepare the roster

`_prepare_roster()` copies the roster ID and internal name columns. It calls
`_normalize_id()` to treat IDs as text, trim surrounding whitespace, and
remove a trailing `.0` sometimes introduced by spreadsheets. It calls
`_normalize_name()` to trim names, collapse repeated whitespace, and ignore
letter case.

The normalized name is stored in a helper column named `_name_key`. The
function stops with an error if an ID or name is blank, or if two names become
the same after normalization. A duplicate normalized name would make the
crosswalk ambiguous.

### Prepare DYCD attendance

`_prepare_dycd_attendance()` copies the DYCD dataframe, normalizes its `ID`,
and renames the source columns:

| Input column | Comparison column |
| --- | --- |
| `ID` | `DYCD ID` |
| `Name` | `DYCD Name` |
| `Attendance` | `DYCD Attendance` |

These names make it clear which source supplied each value in the final
report.

## Step 4: Attach DYCD IDs to OCR rows

`_attach_roster_ids()` prepares the OCR rows for the crosswalk lookup:

1. It creates `_name_key` from each OCR `Matched Name` using the same
   normalization as the roster.
2. It performs a left merge from OCR rows to roster rows using `_name_key`.
   A left merge keeps every OCR row, including names that do not match.
3. It uses `validate="many_to_one"` to ensure each normalized roster name
   points to no more than one roster record.
4. It adds `Roster Merge Status`. `both` means a roster name was found;
   `left_only` means no roster name matched.
5. It renames the OCR ID, name, and attendance fields for clarity in the
   comparison.

This is an exact lookup after case/whitespace normalization. It does not
correct spelling, reorder names, or choose a fuzzy candidate. An OCR row
whose name is not found remains available for review and receives no DYCD ID.

## Step 5: Compare records by DYCD ID and date

`compare_attendance()` passes the prepared data to
`_compare_matched_records()`. That function selects OCR rows which have a
roster match, then outer-merges them with the DYCD rows using both `DYCD ID`
and `Date`.

The outer merge is intentional: unlike an inner merge, it retains records
that exist in only one source. `validate="one_to_one"` also makes duplicate
student/date records an explicit error instead of allowing ambiguous pairings.

For rows found on both sides, attendance values are trimmed and compared
without regard to capitalization. The function assigns one of these results:

| Result | How it is assigned |
| --- | --- |
| `Match` | Both sources have the same status for the ID and date. |
| `Attendance Mismatch` | Both sources have a record, but their statuses differ. |
| `Missing from OCR` | A DYCD record has no mapped OCR record for the ID and date. |
| `Missing from DYCD` | A roster-mapped OCR record has no DYCD record for the ID and date. |

After that comparison, `_add_unmatched_roster_names()` appends OCR rows marked
`left_only` by the roster merge. Those rows cannot be compared by ID because
no ID was assigned. They are labelled `Unmatched Roster Name`, and their
attendance merge status is `not_compared`.

Finally, `compare_attendance()` fills any missing roster merge indicator with
`not_applicable` and orders the output columns using `REPORT_COLUMNS`. It
returns one dataframe containing matches and all records that need review.

## Step 6: Create the Excel report

`main()` passes the comparison dataframe to `write_report()` in
`attendance_audit/reporting.py`.

1. `_build_issues_sheet()` selects every row whose result is not `Match`.
2. `_build_summary_sheet()` groups results by date and result type, then
   counts the rows in each group.
3. `write_report()` writes three worksheets:
   - **All Results** — every comparison row.
   - **Issues** — mismatches, unmatched names, and records missing from either
     attendance source.
   - **Summary** — counts by date and result.
4. Before the workbook closes, `write_report()` passes its worksheets to
   `format_report_workbook()` in `attendance_audit/formatting.py`.
5. `format_report_workbook()` calls `format_report_worksheet()` for each tab.
   Each worksheet is then formatted in this order:
   - `_format_header_row()` styles the headings and freezes the top row.
   - `_format_body_cells()` aligns values and adds borders around populated
     cells.
   - `_format_result_rows()` colors rows based on the `Result` value, when
     that column exists.
   - `_format_date_column()` applies a consistent month/day/year display.
   - `_size_columns()` estimates readable widths from the cell contents.
   - `format_report_worksheet()` turns on the worksheet's column filters.
6. `write_report()` returns the report path to `main()`.

`main()` prints the total number of compared records, the number of matches,
the number of records requiring review, and the location of the saved report.

## Reading merge indicators

The report includes two merge-status columns:

- **Roster Merge Status** describes whether an OCR matched name was found in
  the roster crosswalk. `both` means found; `left_only` means no exact match.
- **Attendance Merge Status** describes whether the DYCD and mapped OCR
  attendance records were found on both sides of the ID/date join. `both`
  means both records were found; `left_only` or `right_only` means a record
  appeared on only one side. `not_compared` is used when the OCR name could
  not first be mapped to a roster ID.

Use these indicators together with `Result`, `OCR Flag`, and `Matched Score`
when reviewing a row. A low score or a manually corrected match is still
worth verifying against the roster and source attendance sheet.

## Important review notes

- The final name-to-ID mapping is exact after normalizing case and
  whitespace. It does not use fuzzy matching.
- Confirm unmatched names and any low-confidence or manually corrected OCR
  matches against the source documents before treating them as authoritative.
- Check each non-`Match` row in the `Issues` worksheet.
- Duplicate roster names after normalization and duplicate ID/date attendance
  records stop the run so they can be reviewed rather than compared
  ambiguously.
- IDs read as numbers may already have lost leading zeroes in Excel. Converting
  such a value back to text cannot restore digits that are no longer present.

## Using different workbooks

The default command uses the demo workbooks. To choose other files, provide
the corresponding command-line options. This example uses PowerShell syntax:

```text
python demo-data/attendance_reconciliation.py `
  --dycd "path\to\dycd_attendance.xlsx" `
  --ocr "path\to\ocr_results.xlsx" `
  --roster "path\to\roster.xlsx" `
  --output "path\to\reconciliation.xlsx"
```

The same options can be entered on one line in other shells.
