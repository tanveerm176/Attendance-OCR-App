"""CLI entry point for the attendance OCR pipeline.

Responsibilities kept here, deliberately not in pipeline.py:
- selecting a folder of PDF sign-in sheets
- concatenating each PDF's pipeline output
- exporting the combined results to Excel
"""

    # check_for_update()
    # 1. parse CLI args
    #    --input (folder path)
    #    --roster (file path)
    #    --output (file path, default: ./output/audit_{date}.xlsx)

    # 2. validate inputs
    #    - input folder exists
    #    - input folder contains at least one .pdf
    #    - roster file exists

    # 3. load roster
    #    roster = io.roster.load_roster(args.roster)

    # 4. prompt user for batch date
    #    sheet_date = input("Enter date for this batch (MM/DD/YYYY): ")
    #    validate format with datetime.strptime — reprompt on invalid input

    # 5. collect and sort PDFs
    #    pdf_paths = sorted(input_folder.glob("*.pdf"))

    # 6. initialize batch collector
    #    batch_results = []

    # 7. iterate over PDFs
    #    for pdf_path in pdf_paths:
    #        log: processing pdf_path
    #
    #        img = pipeline.ingestion.load_pdf(pdf_path)
    #        img = pipeline.deskew.deskew(img)
    #        col_positions, row_positions = pipeline.table_detection.detect_boundaries(img)
    #
    #        sheet_df = pipeline.ocr.extract_sheet(img, col_positions, row_positions)
    #        sheet_df = pipeline.reconciliation.clean_names(sheet_df)
    #        sheet_df = pipeline.reconciliation.fuzzy_match_names(sheet_df, roster)
    #        sheet_df = pipeline.classification.classify_all(sheet_df, img, col_positions, row_positions)
    #
    #        sheet_df['date'] = sheet_date
    #        sheet_df['source_file'] = pdf_path.name
    #
    #        batch_results.append(sheet_df)
    #        log: completed pdf_path, N rows extracted

    # 8. concatenate batch
    #    batch_df = pd.concat(batch_results, ignore_index=True)

    # 9. flag low confidence matches
    #    batch_df = pipeline.reconciliation.flag_low_confidence(batch_df)

    # 10. write Excel output
    #     io.excel_output.write(batch_df, args.output)

    # 11. print on-screen summary
    #     reporting.summary.print_summary(batch_df)

    # 12. write log
    #     reporting.logger.write_log(batch_df, args.output)
from dotenv import load_dotenv
load_dotenv()  # populates os.environ from .env, before anything else runs

import time
import tkinter as tk
import pandas as pd
from updater import check_for_update
from datetime import date, datetime
from pathlib import Path
from tkinter import filedialog

from ocr_pipeline.config import PipelineConfig
from ocr_pipeline.pipeline import OCRPipeline
from io_utils.roster_input import build_roster
from io_utils.excel_output import export_attendance

def prompt_for_pdf_folder() -> Path:
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
    while True:
        raw = input("Enter the sign-in sheet date (MM/DD/YYYY): ").strip()
        try:
            # validate the format, but keep the original string for the output
            datetime.strptime(raw, "%m/%d/%Y")
            return raw
        except ValueError:
            print(f"'{raw}' isn't a valid MM/DD/YYYY date — try again.")

def process_pdf_folder(folder_path: Path, pipeline: OCRPipeline) -> pd.DataFrame:
    pdf_paths = sorted(
        (
            path
            for path in folder_path.iterdir()
            if path.is_file() and path.suffix.casefold() == ".pdf"
        ),
        key=lambda path: path.name.casefold(),
    )
    if not pdf_paths:
        raise ValueError(f"No PDF files found in selected folder: {folder_path}")

    dataframes = []
    for pdf_path in pdf_paths:
        print(f"Processing {pdf_path.name}...")
        dataframes.append(pipeline.run(pdf_path))

    return pd.concat(dataframes, ignore_index=True)


def build_excel_output(folder_path: Path, run_date: date | None = None) -> Path:
    output_dir = Path("./output")
    output_dir.mkdir(parents=True, exist_ok=True)

    if run_date is None:
        run_date = datetime.now().date()
    filename = f"{folder_path.name}_{run_date.strftime('%m-%d-%Y')}.xlsx"
    return output_dir / filename

def main():
    folder_path = prompt_for_pdf_folder()

    # Start the timer
    start_time = time.perf_counter()  
    
    roster = build_roster()
    config = PipelineConfig(roster=roster)
    pipeline = OCRPipeline(config=config)

    df = process_pdf_folder(folder_path, pipeline)

    pd.set_option('display.max_rows', None)
    pd.set_option('display.max_colwidth', None)
    print(df)

    output_path = build_excel_output(folder_path)
    export_attendance(df, output_path)


    print(f"Done - {len(df)} rows written to {output_path}")
    # End the timer
    end_time = time.perf_counter()

    # Calculate total execution time
    execution_time = end_time - start_time
    print(f"Execution time: {execution_time:.6f} seconds")

    return

if __name__ == "__main__":
    main()