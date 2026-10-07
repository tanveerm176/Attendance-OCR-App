# DYCD Daily Attendance Audit Workflow

## Purpose

This document describes the end-to-end process for checking DYCD Connect attendance against physical Daily Attendance sheets. The audit has two distinct checks:

1. **Activity-level consistency:** determine whether a student's DYCD activity records agree with one another for a given date.
2. **Physical-sheet reconciliation:** determine whether DYCD Daily Attendance agrees with the attendance recorded on the physical sheet.

The first check identifies inconsistent DYCD entries; it does not establish which activity entry is correct. The Arrival activity is used as the daily DYCD status for the second check.

## Data and identifiers

The audit uses the following student identity fields:

| Field | Meaning |
| --- | --- |
| DYCD ID | Stable student identifier in the DYCD exports; primary key for final comparison |
| DYCD Name | Name as listed in DYCD, typically `FirstName, MiddleInitial, LastName` |
| Internal attendance-sheet name | Name as written on the physical sheet, typically `LastName, FirstName` |
| Date | The attendance date represented by the DYCD records and the physical sheet |

Names are useful for creating a crosswalk, but they are not the final join key. After a match has been reviewed and approved, compare records using **DYCD ID and date**.

## End-to-end process

### 1. Audit DYCD activity records

**Input:** DYCD export with activity-level attendance, including student ID, participant name, date, activity, and attendance status.

**Process:**

1. Group records by student and date.
2. Compare the student's attendance values across the activities recorded that day, such as Arrival, Dismissal, HW Help, Physical Activity, and SEL.
3. Flag a student-date when the activity attendance values disagree.
4. Select the **Arrival** attendance value as the representative daily DYCD status.
5. If no Arrival record exists for a student-date, use the first attendance value in that group's records as a fallback. The fallback is a representative value, not a determination that it is correct. This is used to compensate for atendance taken during Field Trips which are marked as 'Holiday Programming' in DYCD Connect.

**Outputs:** An activity-level audit workbook with mismatch details, a daily attendance table, and a student roster. The roster should retain the DYCD ID alongside the DYCD name. The daily attendance table should retain the student ID, date, and Arrival-based status (or the documented fallback).

**Interpretation:** A mismatch means the DYCD activity records need attention. It does not prove whether the student was present or absent on the paper sheet.

**Fallback review note:** The daily status output may contain the fallback value without a separate indicator that Arrival was missing. Check the activity-level source records when a fallback needs to be identified or reviewed.

### 2. Prepare and review the name crosswalk

**Input:** The DYCD student roster from Step 1 and the internal names used on the physical attendance sheets.

Create a crosswalk containing at least:

| DYCD ID | DYCD Name | Internal attendance-sheet name | Match score/status | Review decision |
| --- | --- | --- | --- | --- |

Use fuzzy matching to propose links between the two name formats. Review proposed matches before treating them as authoritative, especially where:

- the match score is low or multiple students have similar names;
- the DYCD name includes a middle initial that is absent from the physical sheet;
- spelling, punctuation, spacing, or OCR-related name variations are present;
- two students share the same or very similar names.

Once approved, preserve the relationship between each internal name and its DYCD ID. Do not use a fuzzy-matched name alone as the final comparison key.

### 3. Digitize the physical Daily Attendance sheets

**Inputs:**

- Scanned Daily Attendance sheets in PDF format, organized in a folder for processing.
- The OCR application's configured roster of internal attendance-sheet names. The current application reads this from `data/student_roster_26.txt`.

**Run the application:** From the OCR application's project directory, run:

```text
python main.py
```

Select the folder containing the scanned PDF sheets when prompted. The application processes the PDFs in filename order.

**What the current OCR application does:**

1. Renders each PDF page to an image (300 DPI by default).
2. Detects and crops the attendance table.
3. Extracts student names from the name column and classifies the sign-in mark as `Present`, `Absent`, or `EMPTY CELL`.
4. Cleans extracted names and fuzzy-matches them against the configured roster.
5. Exports the extracted rows to an Excel workbook under `output/`. Worksheets are grouped by the date detected from the sheet; the workbook filename includes the input folder name and the run date.

Each workbook worksheet uses these columns, in order: `Date`, `OCR Raw`, `Attendance Status`, `OCR Cleaned`, `Matched Name`, `Matched Score`, and `Flag`. Match flags include `Strong Match`, `Low Match - Needs Review`, and flags for unusable or unmatched names. Handwritten names that need manual entry are also flagged.

**Review the OCR output before comparison:**

- Confirm that the sheet date and extracted rows are correct.
- Manually resolve low-confidence, missing, unmatched, and handwritten-name rows.
- Verify that the matched roster name identifies the intended student; a high fuzzy score is a suggestion, not proof of identity.
- Confirm how `EMPTY CELL` should be treated for the audit. Do not silently convert it to `Absent` without an established program rule.
- Confirm that each physical-sheet student maps to the correct DYCD ID through the approved crosswalk.

### 4. Compare physical attendance with DYCD Daily Attendance

**Inputs:**

- The Arrival-based DYCD daily attendance output from Step 1.
- The reviewed OCR workbook from Step 3.
- The approved name crosswalk from Step 2.

**Process:**

1. Use the crosswalk to translate each reviewed OCR roster name to a DYCD ID.
2. Match the physical and DYCD records by **DYCD ID and date**.
3. Normalize attendance values according to an agreed status mapping, preserving unknown or empty values for review rather than guessing.
4. Compare the normalized physical status with the Arrival-based DYCD daily status.
5. Record discrepancies and records that cannot be compared, such as unmatched names, missing IDs, duplicate student-date rows, or missing attendance records on either side.

**Recommended discrepancy output:** Keep one row per issue and include the date, DYCD ID (when known), DYCD name, internal sheet name, DYCD status, physical-sheet status, OCR match score/flag, source filename, and a concise issue/review note. Retain the source values so a reviewer can trace each finding back to both inputs.

### 5. Resolve findings and retain an audit trail

Review each discrepancy against the original DYCD export and the physical sheet. Correct DYCD Connect or the source/crosswalk as appropriate under the program's normal correction process. Record the decision, who reviewed it, and when it was resolved. Preserve the original exports, OCR workbook, crosswalk version, comparison output, and correction notes according to the applicable records-retention and privacy practices.

## Current application boundaries

The OCR application implements the physical-sheet digitization and fuzzy name matching described in Step 3. It exports OCR names and matched roster names, but its current OCR output does **not** include a DYCD ID and does **not** perform the final DYCD-versus-physical comparison. Steps 1, 2, and 4 require the separate DYCD activity audit, an approved DYCD-ID-to-internal-name crosswalk, and a comparison process.

The activity-level audit is implemented in the separate activity-level audit application, not in this OCR application's repository. The Arrival selection and fallback behavior described in Step 1 should be kept consistent with that audit output.

## Completion checklist

- [ ] DYCD activity records are audited per student and date.
- [ ] Activity disagreements are retained for review and Arrival is used for the daily DYCD status.
- [ ] Missing Arrival values use the documented first-value fallback and are checked against the source records when reviewed.
- [ ] The name crosswalk has been reviewed and preserves the DYCD ID.
- [ ] OCR rows have been checked, including low-confidence and manual-entry flags.
- [ ] Empty cells and attendance labels have been normalized using an agreed rule.
- [ ] Final comparisons are keyed by DYCD ID and date.
- [ ] Discrepancies and unresolved/unmatched records are reported and traceable to source records.
- [ ] Resolutions and corrections are recorded in the audit trail.
