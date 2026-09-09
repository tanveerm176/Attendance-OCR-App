from pathlib import Path

import cv2
import pandas as pd

from ocr_pipeline import ingestion, table_detection, img_cropping, ocr, classification, reconciliation
from ocr_pipeline.config import PipelineConfig
from ocr_pipeline.exceptions import TableDetectionError

class OCRPipeline:
    def __init__(self, config: PipelineConfig):
        self.config = config

    def run(self, pdf_path: Path) -> pd.DataFrame:
        cfg = self.config

        # --- Stage 1: PDF Ingestion -> RGB ONLY ---
        img_rgb = ingestion.pdf_to_image(pdf_path)

        # --- Stage 2: Vertical Line Detection ---
        img_gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)
        vertical_lines = table_detection.get_vertical_line_positions(img_gray)

        if len(vertical_lines) <= cfg.img_crop_end:
            raise TableDetectionError(
                f"Expected at least {cfg.img_crop_end + 1} vertical lines,"
                f"found {len(vertical_lines)}"
            )
        
        # --- Stage 3: Crop Image Vertically to Table Region ---
        # (line 0 -> img_crop_end)
        table_x_start = vertical_lines[cfg.img_crop_start]
        table_x_end = vertical_lines[cfg.img_crop_end]

        table_img_rgb = img_cropping.vertical_img_crop(img_rgb, table_x_start, table_x_end)

        # --- Stage 4: Horizontal Line Detection ---
        table_img_gray = cv2.cvtColor(table_img_rgb, cv2.COLOR_RGB2GRAY)
        horizontal_lines = table_detection.get_horizontal_line_positions(table_img_gray)

        if len(horizontal_lines) < 2:
            raise TableDetectionError(
                f"Expected at least 2 horizontal lines to establish one table row,"
                f"found {len(horizontal_lines)}"
            )

        # --- Stage 5: Iterate over Table Rows, Extract Name, Classify Attendance
        # x-coordinates rebased against table_img_rgb's shifted origin
        # (table_x_start subtracted, since vertical_lines was detected on
        # the *original* full-page image, not the cropped table).
        name_x_start = vertical_lines[cfg.name_col_start] - table_x_start
        name_x_end = vertical_lines[cfg.name_col_end] - table_x_start

        attendance_x_start = vertical_lines[cfg.attendance_col_start] - table_x_start
        attendance_x_end = vertical_lines[cfg.attendance_col_end] - table_x_start

        ocr_names = []
        attendance_statuses = []

        # Skip Header, splice horizontal_lines[]
        horizontal_lines = horizontal_lines[cfg.skip_header_start_row:]

        # Iterate over all rows
        for line_index in range(len(horizontal_lines) -1 ):
            row_top_line, row_bottom_line = horizontal_lines[line_index], horizontal_lines[line_index+1]
            table_row_rgb = img_cropping.horizontal_img_crop(table_img_rgb, row_top_line, row_bottom_line)
            
            # Name sub-crop -> grayscale (tesseract_ocr requires Grayscale Img input)
            name_crop_rgb = img_cropping.vertical_img_crop(table_row_rgb, name_x_start, name_x_end)
            name_crop_gray = cv2.cvtColor(name_crop_rgb, cv2.COLOR_RGB2GRAY)
            ocr_name = ocr.tesseract_ocr(name_crop_gray, cfg.tesseract_config)

            # Attendance sub-crop -> stays RGB for color classification
            attendance_crop_rgb = img_cropping.vertical_img_crop(table_row_rgb, attendance_x_start, attendance_x_end)
            attendance_status = classification.classify_attendance(attendance_crop_rgb)

            ocr_names.append(ocr_name)
            attendance_statuses.append(attendance_status)

        # --- Stage 6: Assemble Raw Dataframe ---
        attendance_df = pd.DataFrame({'ocr_raw': ocr_names, 'attendance': attendance_statuses})

        # --- Stage 7: Reconciliation (clean + fuzzy_match + flag)
        reconciled_df = reconciliation.fuzzy_match_names(attendance_df, 
                                                         cfg.roster,
                                                         threshold = cfg.fuzzy_match_threshold,
                                                         low_match_floor = cfg.low_match_floor)

        # return Reconciled DataFrame
        # NOTE: no date prompt, no excel export here - main.py handles that
        return reconciled_df

"""""""""   

Orchestrator for the attendance OCR pipeline

Pass 1: skeleton only. Every stage below returns a hardcoded stub value.
No real calls into ingestion/table_detection/img_cropping/classification/reconciliation yet - 
the point of this pass is to confirm the shape headed from one stage to the next before wiring anything real in
(Pass 2)
    ---- PASS 1: SKELETON ----


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
        return df"""""""""