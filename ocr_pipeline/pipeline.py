"""Orchestrator for the attendance OCR pipeline

Pass 1: skeleton only. Every stage below returns a hardcoded stub value.
No real calls into ingestion/table_detection/img_cropping/classification/reconciliation yet - 
the point of this pass is to confirm the shape headed from one stage to the next before wiring anything real in
(Pass 2)
"""

from pathlib import Path
import pandas as pd

from ocr_pipeline.config import PipelineConfig
from ocr_pipeline.exceptions import TableDetectionError

class OCRPipeline:
    def __init__(self, config: PipelineConfig) -> None:
        self.config = config

    def run(self, pdf_path: Path) -> pd.DataFrame:
        # --- Stage 1: ingestion ---
        # ingestion.pdf_to_image(pdf_path) -> RGB + grayscale img
        
        # --- Stage 2: vertical line detection (on full page) ---
        # raise TableDetectionError if < 6 vertical lines detected
        # table_detection.get_vertical_line_positions(img_gray) -> list[float]

        # --- Stage 3: crop image to needed columns ---
        # img_cropping crops using verticals_lines[self.config.img_crop_start] 
        # and verticals_lines[self.config.img_crop_end]

        # --- Stage 4: horizontal line detection (on cropped image to determine rows) ---
        # table_detection.get_horizontal_line_positions(img_gray) -> list[int]
        
        # --- Stage 5: per-row loop ---
        # for each row (bounded by consecutive horizontal_lines enteries):
        #   - crop name sub-region (name_col_start : name_col_end) -> ocr.tesseract_ocr()
        #   - crop attendance sub-region (attendance_col_start : attendance_col_end) -> classification.classify_attendance()

        # --- Stage 6: assemble raw DataFrame --- 

        # --- Stage 7: reconciliation (clean + fuzzy_match + flag)

        # --- Stage 8: return ---
        # NOTE: no date prompt, no excel output -> main.py will handle that