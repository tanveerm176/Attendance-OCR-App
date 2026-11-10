"""Run attendance OCR for a selected folder and export the combined results."""

from dotenv import load_dotenv
load_dotenv()  # populates os.environ from .env, before anything else runs

import time
import itertools
import tkinter as tk
import pandas as pd
from collections.abc import Callable
from updater import check_for_update
from datetime import date, datetime
from pathlib import Path
from tkinter import filedialog

from ocr_pipeline.config import PipelineConfig
from ocr_pipeline.pipeline import OCRPipeline
from io_utils.roster_input import build_roster
from io_utils.excel_output import export_attendance
from ocr_pipeline.manual_review import review_flagged_records
from ocr_pipeline.models import AttendanceBatch, DailyAttendance

def prompt_for_pdf_folder() -> Path:
    """Ask the user to select the folder containing scanned sign-in sheets."""
    root = tk.Tk()
    root.withdraw()  # hide the empty root window, only show the dialog

    try:
        selected = filedialog.askdirectory(title="Select folder of scanned sign-in sheets")
    finally:
        root.destroy()

    if not selected:
        raise ValueError("No folder selected — cannot continue.")

    return Path(selected)


def prompt_for_date() -> str:
    """Prompt until the user enters a date in MM/DD/YYYY format."""
    while True:
        raw = input("Enter the sign-in sheet date (MM/DD/YYYY): ").strip()
        try:
            # validate the format, but keep the original string for the output
            datetime.strptime(raw, "%m/%d/%Y")
            return raw
        except ValueError:
            print(f"'{raw}' isn't a valid MM/DD/YYYY date — try again.")


def process_pdf_folder(folder_path: Path, pipeline: OCRPipeline,
    review_callback: Callable[[DailyAttendance], None] | None = None) -> AttendanceBatch:
    """Process PDFs in name order and combine their attendance rows.

    The optional review callback runs on each PDF's results before the next PDF
    starts. Temporary crop images used by that review step are removed before
    the per-file dataframes are combined.
    """
    # Keep only files with a .pdf extension and process them in a stable,
    # case-insensitive filename order.
    pdf_paths = sorted((path 
                        for path in folder_path.iterdir() 
                        if path.is_file() and path.suffix.casefold() == ".pdf"), 
                        key=lambda path: path.name.casefold())

    if not pdf_paths:
        # Fail before processing so an empty selection doesn't reach pd.concat.
        raise ValueError(f"No PDF files found in selected folder: {folder_path}")

    attendance_batch = AttendanceBatch(
                source_folder=folder_path,
                attendance_group=None)
    
    for pdf_path in pdf_paths:
        print(f"Processing {pdf_path.name}...")
        daily_attendance = pipeline.run(pdf_path)
        

        # Review this PDF before moving on: the pipeline attaches each name crop
        # to its row, and the callback displays flagged rows for roster selection.

        if review_callback is not None:
            review_callback(daily_attendance)

        # Crops are only needed by the review UI; keep image arrays out of the
        # combined results and Excel export.
        
        attendance_batch.attendance_sheets.append(daily_attendance)

    return attendance_batch


def build_excel_output(folder_path: Path, run_date: date | None = None) -> Path:
    """Create the output directory and return a dated workbook path for a folder."""
    output_dir = Path("./output")
    output_dir.mkdir(parents=True, exist_ok=True)

    if run_date is None:
        run_date = datetime.now().date()
    filename = f"{folder_path.name}_{run_date.strftime('%m-%d-%Y')}.xlsx"
    return output_dir / filename


def main():
    """Coordinate folder selection, OCR, flagged-name review, and Excel export."""
    folder_path = prompt_for_pdf_folder()

    # Start the timer
    start_time = time.perf_counter()  
    
    roster = build_roster()
    config = PipelineConfig(roster=roster)
    pipeline = OCRPipeline(config=config)

    attendance_batch = process_pdf_folder(
        folder_path,
        pipeline,
        # Reconcile flagged names against the roster in the visual review UI.
        review_callback=lambda attendance: review_flagged_records(attendance, roster)
    )

    # Flatten Records
    # student_records = itertools.chain.from_iterable(sheet.records for sheet in attendance_batch.attendance_sheets)
    # for record in student_records:
    #     print(record.match_flag, " ",record.match_score, " ", record.review_crop)

    # pd.set_option('display.max_rows', None)
    # pd.set_option('display.max_colwidth', None)
    # print(df)

    # output_path = build_excel_output(folder_path)
    # export_attendance(df, output_path)


    # print(f"Done - {len(df)} rows written to {output_path}")
    # End the timer
    end_time = time.perf_counter()

    # Calculate total execution time
    execution_time = end_time - start_time
    print(f"Execution time: {execution_time:.6f} seconds")

    return

if __name__ == "__main__":
    main()