"""Attach DYCD IDs to OCR rows and compare the two attendance sources."""

from __future__ import annotations

import pandas as pd


REPORT_COLUMNS = [
    "Date",
    "DYCD ID",
    "DYCD Name",
    "Internal Roster Name",
    "OCR Matched Name",
    "OCR Raw",
    "DYCD Attendance",
    "OCR Attendance",
    "Result",
    "Roster Merge Status",
    "Attendance Merge Status",
    "Matched Score",
    "OCR Flag",
]


def _normalize_id(values: pd.Series) -> pd.Series:
    """Keep student IDs as text and remove a spreadsheet-added trailing .0."""
    text_values = values.astype("string").str.strip()
    return text_values.str.replace(r"\.0$", "", regex=True)


def _normalize_name(values: pd.Series) -> pd.Series:
    """Normalize case and whitespace for exact crosswalk lookups."""
    text_values = values.astype("string")
    trimmed_values = text_values.str.strip()
    single_spaced_values = trimmed_values.str.replace(r"\s+", " ", regex=True)
    return single_spaced_values.str.casefold()


def _prepare_roster(roster: pd.DataFrame) -> pd.DataFrame:
    """Create a normalized name key and reject incomplete or duplicate roster rows."""
    prepared_roster = roster[["DYCD ID", "Internal Roster Name"]].copy()
    prepared_roster["DYCD ID"] = _normalize_id(prepared_roster["DYCD ID"])
    prepared_roster["_name_key"] = _normalize_name(
        prepared_roster["Internal Roster Name"]
    )

    # A blank ID or name cannot create a reliable student crosswalk.
    blank_ids = prepared_roster["DYCD ID"].isna() | prepared_roster["DYCD ID"].eq("")
    blank_names = (
        prepared_roster["_name_key"].isna()
        | prepared_roster["_name_key"].eq("")
    )
    if blank_ids.any() or blank_names.any():
        raise ValueError("The roster contains a blank DYCD ID or Internal Roster Name.")

    # Two names that become equal after normalization make the lookup ambiguous.
    duplicate_names = prepared_roster["_name_key"].duplicated(keep=False)
    if duplicate_names.any():
        names = prepared_roster.loc[
            duplicate_names, "Internal Roster Name"
        ].tolist()
        raise ValueError(
            "The roster has duplicate internal names after whitespace/case "
            f"normalization: {names}"
        )

    return prepared_roster


def _prepare_dycd_attendance(dycd_attendance: pd.DataFrame) -> pd.DataFrame:
    """Rename DYCD columns and normalize its primary key before comparison."""
    prepared_dycd = dycd_attendance.copy()
    prepared_dycd["ID"] = _normalize_id(prepared_dycd["ID"])

    # Use clear source-specific names in the final report.
    prepared_dycd = prepared_dycd.rename(
        columns={
            "ID": "DYCD ID",
            "Name": "DYCD Name",
            "Attendance": "DYCD Attendance",
        }
    )
    return prepared_dycd


def _attach_roster_ids(
    ocr_attendance: pd.DataFrame,
    roster: pd.DataFrame,
) -> pd.DataFrame:
    """Add DYCD IDs to OCR rows using the reviewed internal-name crosswalk."""
    prepared_ocr = ocr_attendance.copy()
    prepared_ocr["_name_key"] = _normalize_name(prepared_ocr["Matched Name"])

    # Keep the merge indicator so an unknown OCR name is visible for review.
    ocr_with_roster = prepared_ocr.merge(
        roster,
        on="_name_key",
        how="left",
        validate="many_to_one",
        indicator="Roster Merge Status",
    )
    ocr_with_roster["DYCD ID"] = _normalize_id(ocr_with_roster["DYCD ID"])
    ocr_with_roster = ocr_with_roster.rename(
        columns={
            "DYCD ID": "OCR DYCD ID",
            "Matched Name": "OCR Matched Name",
            "Attendance Status": "OCR Attendance",
        }
    )
    return ocr_with_roster


def _compare_matched_records(
    dycd_attendance: pd.DataFrame,
    ocr_with_roster: pd.DataFrame,
) -> pd.DataFrame:
    """Join records by DYCD ID and date, preserving one-sided attendance rows."""
    mapped_ocr = ocr_with_roster.loc[
        ocr_with_roster["Roster Merge Status"].eq("both")
    ].copy()

    # An outer join keeps records present in only one attendance workbook.
    compared = dycd_attendance.merge(
        mapped_ocr,
        left_on=["DYCD ID", "Date"],
        right_on=["OCR DYCD ID", "Date"],
        how="outer",
        validate="one_to_one",
        indicator="Attendance Merge Status",
    )
    compared["DYCD ID"] = compared["DYCD ID"].fillna(compared["OCR DYCD ID"])

    dycd_status = (
        compared["DYCD Attendance"].astype("string").str.strip().str.casefold()
    )
    ocr_status = compared["OCR Attendance"].astype("string").str.strip().str.casefold()
    statuses_match = (dycd_status == ocr_status).fillna(False)

    # Assign a clear result for matches, status differences, and missing records.
    compared["Result"] = "Attendance Mismatch"
    both_sources = compared["Attendance Merge Status"].eq("both")
    compared.loc[both_sources & statuses_match, "Result"] = "Match"
    compared.loc[
        compared["Attendance Merge Status"].eq("left_only"), "Result"
    ] = "Missing from OCR"
    compared.loc[
        compared["Attendance Merge Status"].eq("right_only"), "Result"
    ] = "Missing from DYCD"
    return compared


def _add_unmatched_roster_names(
    compared: pd.DataFrame,
    ocr_with_roster: pd.DataFrame,
) -> pd.DataFrame:
    """Append OCR rows that could not be connected to a roster name and DYCD ID."""
    unmatched_ocr = ocr_with_roster.loc[
        ocr_with_roster["Roster Merge Status"].eq("left_only")
    ].copy()

    if unmatched_ocr.empty:
        return compared

    # These OCR rows cannot join on ID; retain them with an explicit review result.
    unmatched_ocr = unmatched_ocr.rename(
        columns={
            "Matched Name": "OCR Matched Name",
            "Attendance Status": "OCR Attendance",
        }
    )
    unmatched_ocr["DYCD ID"] = pd.NA
    unmatched_ocr["DYCD Name"] = pd.NA
    unmatched_ocr["DYCD Attendance"] = pd.NA
    unmatched_ocr["Attendance Merge Status"] = "not_compared"
    unmatched_ocr["Result"] = "Unmatched Roster Name"

    return pd.concat([compared, unmatched_ocr], ignore_index=True, sort=False)


def compare_attendance(
    dycd_attendance: pd.DataFrame,
    ocr_attendance: pd.DataFrame,
    roster: pd.DataFrame,
) -> pd.DataFrame:
    """Compare records by DYCD ID and date, retaining rows that need review."""
    prepared_roster = _prepare_roster(roster)
    prepared_dycd = _prepare_dycd_attendance(dycd_attendance)
    ocr_with_roster = _attach_roster_ids(ocr_attendance, prepared_roster)

    compared = _compare_matched_records(prepared_dycd, ocr_with_roster)
    compared = _add_unmatched_roster_names(compared, ocr_with_roster)

    # Keep a text merge status for every row, including one-sided records.
    compared["Roster Merge Status"] = (
        compared["Roster Merge Status"].astype("string").fillna("not_applicable")
    )
    return compared.reindex(columns=REPORT_COLUMNS)
