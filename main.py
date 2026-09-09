"""CLI entry point for the attendance OCR pipeline.

Responsibilities kept here, deliberately not in pipeline.py:
- prompting for the sign-in date
- picking the source PDF via a file dialog
- stamping the date onto the result DataFrame
- exporting to Excel
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

import time
import tkinter as tk
import pandas as pd
from updater import check_for_update
from datetime import datetime
from pathlib import Path
from tkinter import filedialog

from ocr_pipeline.config import PipelineConfig
from ocr_pipeline.pipeline import OCRPipeline
from io_utils.roster_input import build_roster
from io_utils.excel_output import export_attendance


def prompt_for_pdf_path() -> Path:
    root = tk.Tk()
    root.withdraw()  # hide the empty root window, only show the dialog

    selected = filedialog.askopenfilename(
        title="Select scanned sign-in sheet",
        filetypes=[("PDF files", "*.pdf")],
    )
    root.destroy()

    if not selected:
        raise ValueError("No PDF selected — cannot continue.")

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

def build_excel_output(pdf_path: Path, sheet_date: str) -> Path:
    output_dir = Path("./output")
    output_dir.mkdir(parents=True, exist_ok=True)

    safe_date = sheet_date.replace("/","-")
    return output_dir/f"attendance_{safe_date}.xlsx"

def main():
    pdf_path = prompt_for_pdf_path()
    sheet_date = prompt_for_date()

    # Start the timer
    start_time = time.perf_counter()  
    
    roster = build_roster()
    config = PipelineConfig(roster=roster)
    pipeline = OCRPipeline(config=config)

    df = pipeline.run(pdf_path)

    # stamp date as the first column
    df.insert(0,'Date',sheet_date)

    pd.set_option('display.max_rows', None)
    pd.set_option('display.max_colwidth', None)
    print(df)

    # output_path = build_excel_output(pdf_path, sheet_date)
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