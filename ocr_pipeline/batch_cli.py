"""Headless batch entry point for processing attendance PDFs."""

from __future__ import annotations

import argparse
from pathlib import Path, PurePosixPath, PureWindowsPath
from collections.abc import Sequence

import pandas as pd
from dotenv import load_dotenv

from io_utils.excel_output import export_attendance
from io_utils.roster_input import build_roster
from ocr_pipeline.config import PipelineConfig

load_dotenv()

from ocr_pipeline.pipeline import OCRPipeline
from ocr_pipeline.models import AttendanceBatch, DailyAttendance, AttendanceRecord

REVIEW_CROP_COLUMN = "_review_crop"


def _source_pdf_path(
    pdf_path: Path,
    input_dir: Path,
    source_path_root: str | None,
) -> str:
    """Build the source path value to store for a processed PDF.

    Without an override, return the PDF's resolved local path. With an
    override, preserve the path style of the supplied root (Windows or
    POSIX) while appending the PDF's path relative to the input directory.
    """
    if source_path_root is None:
        return str(pdf_path.resolve())

    # Store a path that users can access from their host, even if OCR runs
    # inside a container with a different view of the filesystem.
    relative_path = pdf_path.relative_to(input_dir)
    # Pure paths join components without interpreting them on this host OS.
    windows_root = PureWindowsPath(source_path_root)
    if windows_root.drive or "\\" in source_path_root:
        return str(windows_root.joinpath(*relative_path.parts))

    return str(PurePosixPath(source_path_root).joinpath(*relative_path.parts))


def process_pdf_folder(
    folder_path: Path,
    pipeline: OCRPipeline,
    *,
    source_path_root: str | None = None,
) -> AttendanceBatch:
    """Run OCR on each PDF in a folder and combine the per-file dataframes.

    PDFs are processed in case-insensitive filename order. Internal review
    crops and any source path supplied by the pipeline are removed before the
    selected source path is attached to each row.

    Args:
        folder_path: Directory containing the PDF attendance sheets.
        pipeline: Configured OCR pipeline used to process each PDF.
        source_path_root: Optional path prefix for workbook source links. When
            omitted, each PDF's resolved local path is used.

    Returns:
        A single dataframe containing all processed PDF rows.

    Raises:
        ValueError: If the input directory does not exist or contains no PDFs.
    """
    input_dir = folder_path.resolve()
    if not input_dir.is_dir():
        raise ValueError(f"PDF input directory does not exist: {input_dir}")

    pdf_paths = sorted(
        (
            path
            for path in input_dir.iterdir()
            # Ignore directories and accept extensions like .PDF as well.
            if path.is_file() and path.suffix.casefold() == ".pdf"
        ),
        # Consistent ordering makes batch output predictable across runs.
        key=lambda path: path.name.casefold(),
    )
    if not pdf_paths:
        raise ValueError(f"No PDF files found in input directory: {input_dir}")

    attendance_batch = AttendanceBatch(
        source_folder = folder_path,
        attendance_group = None)
    
    for pdf_path in pdf_paths:
        print(f"Processing {pdf_path.name}...")

        # Work on a copy so adding batch metadata doesn't mutate pipeline output.
        daily_attendance = pipeline.run(pdf_path)

        # Image crops are only for interactive review, not for the workbook.
        # Replace any pipeline-provided path with the path chosen for this run.
        for record in daily_attendance.records:
            if record.review_crop:
                record.review_crop = None

        daily_attendance.source_pdf_display_path = _source_pdf_path(
            pdf_path,
            input_dir,
            source_path_root,
        )

        attendance_batch.attendance_sheets.append(daily_attendance)

    return attendance_batch


def run_batch(
    input_dir: Path,
    output_path: Path,
    *,
    roster_path: Path | None = None,
    source_path_root: str | None = None,
) -> Path:
    """Configure the OCR pipeline, process the input folder, and export Excel.

    Args:
        input_dir: Directory containing the PDF attendance sheets.
        output_path: Destination path for the generated workbook.
        roster_path: Optional text file to use instead of the bundled roster.
        source_path_root: Optional path prefix to record in source links,
            useful when the process runs in Docker but users need host paths.

    Returns:
        The output workbook path.
    """
    roster = build_roster(roster_path) if roster_path is not None else build_roster()
    pipeline = OCRPipeline(config=PipelineConfig(roster=roster))
    attendance_batch = process_pdf_folder(
        input_dir,
        pipeline,
        source_path_root=source_path_root,
    )

    # Create nested output directories so the requested output path can be new.
    # output_path.parent.mkdir(parents=True, exist_ok=True)
    # export_attendance(dataframe, output_path)
    # print(f"Done - {len(dataframe)} rows written to {output_path}")
    return output_path


def main(argv: Sequence[str] | None = None) -> int:
    """Parse command-line options and run a headless attendance batch.

    Flagged names are not opened in a GUI during this run; they remain marked
    for review in the exported workbook.

    Args:
        argv: Optional command-line argument sequence. If omitted, arguments
            are read from the process command line.

    Returns:
        Zero after the batch completes successfully.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Process attendance PDFs without opening the desktop review GUI. "
            "Review flagged rows in the exported workbook."
        )
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        required=True,
        help="Directory containing PDF attendance sheets",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path for the generated Excel workbook",
    )
    parser.add_argument(
        "--roster",
        type=Path,
        help="Optional roster text file; defaults to the app's bundled roster",
    )
    parser.add_argument(
        "--source-path-root",
        help=(
            "Path prefix to write in Excel instead of the input path visible to "
            "the process; useful for recording a host path when running in Docker"
        ),
    )
    # Accept an argv parameter so the CLI can also be exercised directly in tests.
    args = parser.parse_args(argv)

    run_batch(
        args.input_dir,
        args.output,
        roster_path=args.roster,
        source_path_root=args.source_path_root,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
