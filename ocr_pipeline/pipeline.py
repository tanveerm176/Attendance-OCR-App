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
        img_rgb, img_gray = self._stub_ingest(pdf_path)
        
        # --- Stage 2: vertical line detection (on full page) ---
        # raise TableDetectionError if < 6 vertical lines detected
        # table_detection.get_vertical_line_positions(img_gray) -> list[float]
        vertical_lines = self._stub_vertical_lines(img_gray)

        if len(vertical_lines) != 6:
            raise TableDetectionError(
                f"Expected at least 6 vertical lines, found {len(vertical_lines)}"
            )

        # --- Stage 3: crop image to needed columns ---
        # img_cropping crops using verticals_lines[self.config.img_crop_start] 
        # and verticals_lines[self.config.img_crop_end]
        table_img = self._stub_crop_table(img_rgb, vertical_lines)

        # --- Stage 4: horizontal line detection (on cropped image to determine rows) ---
        # table_detection.get_horizontal_line_positions(img_gray) -> list[int]
        horizontal_lines = self._stub_horizontal_lines(table_img)

        if len(horizontal_lines) < 2:
            raise TableDetectionError(
                f"Expected at least 2 lines for establishing a row, found {len(horizontal_lines)}"
            )
        
        # --- Stage 5: per-row loop ---
        # for each row (bounded by consecutive horizontal_lines enteries):
        #   - crop name sub-region (name_col_start : name_col_end) -> ocr.tesseract_ocr()
        #   - crop attendance sub-region (attendance_col_start : attendance_col_end) -> classification.classify_attendance()

        # x_start/x_end for each sub-crop must be rebased against table_img's
        # shifted origin:
        #   name_x_start = vertical_lines[config.name_col_start] - vertical_lines[config.img_crop_start]
        #   name_x_end   = vertical_lines[config.name_col_end]   - vertical_lines[config.img_crop_start]
        # (same pattern for attendance_col_start/end)
        # Currently a no-op since img_crop_start=0, but correct regardless of that value.
        ocr_names, statuses = self._stub_row_loop(
            table_img, vertical_lines, horizontal_lines
        )

        # --- Stage 6: assemble raw DataFrame --- 
        df = pd.DataFrame({"ocr_raw": ocr_names, "status": statuses})

        # --- Stage 7: reconciliation (clean + fuzzy_match + flag)
        df = self._stub_reconcile(df)

        # --- Stage 8: return ---
        # NOTE: no date prompt, no excel output -> main.py will handle that
        return df

    # ------------------------------------------------------------------
    # Pass 1 stubs — replaced with real calls in Pass 2
    # ------------------------------------------------------------------

    def _stub_ingest(self, pdf_path: Path):
        return None, None  # (img_rgb, img_gray)

    def _stub_vertical_lines(self, img_gray):
        return [0, 100, 200, 300, 400, 500]  # 6 lines -> matches table_col indices 0-5

    def _stub_crop_table(self, img_rgb, vertical_lines):
        return None  # cropped table image

    def _stub_horizontal_lines(self, table_img):
        return [0, 50, 100, 150]  # 3 rows

    def _stub_row_loop(self, table_img, vertical_lines, horizontal_lines):
        ocr_names = ["Stub Name 1", "Stub Name 2", "Stub Name 3"]
        statuses = ["Present", "Absent", "EMPTY CELL"]
        return ocr_names, statuses

    def _stub_reconcile(self, df: pd.DataFrame) -> pd.DataFrame:
        df["cleaned_name"] = df["ocr_raw"]
        df["matched_name"] = None
        df["match_score"] = 0
        df["flag"] = "STUB"
        return df