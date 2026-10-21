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

REVIEW_CROP_COLUMN = "_review_crop"


def _source_pdf_path(
    pdf_path: Path,
    input_dir: Path,
    source_path_root: str | None,
) -> str:
    if source_path_root is None:
        return str(pdf_path.resolve())

    relative_path = pdf_path.relative_to(input_dir)
    windows_root = PureWindowsPath(source_path_root)
    if windows_root.drive or "\\" in source_path_root:
        return str(windows_root.joinpath(*relative_path.parts))

    return str(PurePosixPath(source_path_root).joinpath(*relative_path.parts))


def process_pdf_folder(
    folder_path: Path,
    pipeline: OCRPipeline,
    *,
    source_path_root: str | None = None,
) -> pd.DataFrame:
    input_dir = folder_path.resolve()
    if not input_dir.is_dir():
        raise ValueError(f"PDF input directory does not exist: {input_dir}")

    pdf_paths = sorted(
        (
            path
            for path in input_dir.iterdir()
            if path.is_file() and path.suffix.casefold() == ".pdf"
        ),
        key=lambda path: path.name.casefold(),
    )
    if not pdf_paths:
        raise ValueError(f"No PDF files found in input directory: {input_dir}")

    dataframes = []
    for pdf_path in pdf_paths:
        print(f"Processing {pdf_path.name}...")
        dataframe = pipeline.run(pdf_path).copy()
        dataframe = dataframe.drop(
            columns=[REVIEW_CROP_COLUMN, "source_pdf_path"],
            errors="ignore",
        )
        dataframe["source_pdf_path"] = _source_pdf_path(
            pdf_path,
            input_dir,
            source_path_root,
        )
        dataframes.append(dataframe)

    return pd.concat(dataframes, ignore_index=True)


def run_batch(
    input_dir: Path,
    output_path: Path,
    *,
    roster_path: Path | None = None,
    source_path_root: str | None = None,
) -> Path:
    roster = build_roster(roster_path) if roster_path is not None else build_roster()
    pipeline = OCRPipeline(config=PipelineConfig(roster=roster))
    dataframe = process_pdf_folder(
        input_dir,
        pipeline,
        source_path_root=source_path_root,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    export_attendance(dataframe, output_path)
    print(f"Done - {len(dataframe)} rows written to {output_path}")
    return output_path


def main(argv: Sequence[str] | None = None) -> int:
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
