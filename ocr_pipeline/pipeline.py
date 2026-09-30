import cv2
import pandas as pd

from pathlib import Path
from ocr_pipeline import (ingestion, 
                          table_detection, 
                          img_cropping, 
                          ocr, 
                          classification, 
                          reconciliation, 
                          rotate,
                          deskew)

from ocr_pipeline.config import PipelineConfig
from ocr_pipeline.exceptions import TableDetectionError
import matplotlib.pyplot as plt
import matplotlib.image as mpimg

class OCRPipeline:
    def __init__(self, config: PipelineConfig):
        self.config = config

    def run(self, pdf_path: Path) -> pd.DataFrame:
        cfg = self.config

        # --- Stage 0: PDF Ingestion -> list[RGB Images] ---
        image_list = ingestion.pdf_to_image(pdf_path)

        ocr_names = []
        attendance_statuses = []

        for img_rgb in image_list:

            # --- Stage 1: Convert to Grayscale ---
            img_gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)

            # --- Stage 1.25: Correct PDF Orientation ---
            # img_gray = rotate.correct_orientation(img_gray)
            # img_rgb = rotate.correct_orientation(img_rgb)

            # --- Stage 1.5: PDF Deskew ---
            img_skew_angle = deskew.get_skew_angle(img_gray)

            if img_skew_angle != 0.0:
                img_gray = deskew.correct_skew(img_gray, img_skew_angle)
                img_rgb = deskew.correct_skew(img_rgb, img_skew_angle)

            # --- Stage 2: Vertical Line Detection ---
            vertical_lines = table_detection.get_vertical_line_positions(img_gray)

            if len(vertical_lines) <= cfg.img_crop_end:
                raise TableDetectionError(
                    f"Expected at least {cfg.img_crop_end + 1} vertical lines,"
                    f"found {len(vertical_lines)}"
                )
            
            # --- Stage 3: Crop Image Vertically to Table Region ---
            if vertical_lines[0] < 50:
                vertical_lines = vertical_lines[1:]

            table_x_start = vertical_lines[cfg.img_crop_start]
            table_x_end = vertical_lines[cfg.img_crop_end]

            table_img_rgb = img_cropping.vertical_img_crop(img_rgb, table_x_start, table_x_end)
            table_img_gray = cv2.cvtColor(table_img_rgb, cv2.COLOR_RGB2GRAY)

            # --- Stage 4: Horizontal Line Detection ---
            horizontal_lines = table_detection.get_horizontal_line_positions(table_img_gray)
            print(f'Original Horizontal Lines: {horizontal_lines}')
            if len(horizontal_lines) < 2:
                raise TableDetectionError(
                    f"Expected at least 2 horizontal lines to establish one table row,"
                    f"found {len(horizontal_lines)}"
                    # cv2.imwrite("reporting/debug_table_crop.png", cv2.cvtColor(table_img_rgb, cv2.COLOR_RGB2BGR))
                )

            # ---- Skip Header if not Main Page, splice horizontal_lines[] ---
            
            if horizontal_lines[0] < 5:
                print('horizontal_lines[0] < 5')
                horizontal_lines = horizontal_lines[1:]
                print(f'After Change Horizontal Lines: {horizontal_lines}')

            page_header = img_cropping.horizontal_img_crop(table_img_gray, 0, horizontal_lines[0])
            print(f'Page Header Height: {page_header.shape[0]}')

            # cv2.imwrite("page_header.png", page_header)
            if page_header.shape[0] >= 400:
                print(f'On Main Page, Header Skipped by {cfg.skip_header_start_row} lines')
                horizontal_lines = horizontal_lines[cfg.skip_header_start_row:]   
                print(f'After Header Skipped {horizontal_lines}')

            else: print('Not on Main Page')

            end_of_img = table_img_rgb.shape[0]
            if (horizontal_lines[-1] - horizontal_lines[-2]) > 500:
                end_of_img = horizontal_lines[-1] - 200 #ensures DYCD logo is cutout when processing written section
                print(f'[-1]:{horizontal_lines[-1]}, [-2]:{horizontal_lines[-2]}')
                print("DYCD Logo Detected, changed table height to disregard")
                horizontal_lines = horizontal_lines[:-1]
                print(f'DYCD Logo Detected Lines: {horizontal_lines}')

            # --- Stage 5: Iterate over Table Rows, Extract Name, Classify Attendance
            # x-coordinates rebased against table_img_rgb's shifted origin
            # (table_x_start subtracted, since vertical_lines was detected on
            # the *original* full-page image, not the cropped table).
            name_x_start = vertical_lines[cfg.name_col_start] - table_x_start
            name_x_end = vertical_lines[cfg.name_col_end] - table_x_start

            attendance_x_start = vertical_lines[cfg.attendance_col_start] - table_x_start
            attendance_x_end = vertical_lines[cfg.attendance_col_end] - table_x_start

            # --------------- DEBUG IMAGE GENERATION -------------------------------
            # debug_name_crop_raw = table_img_rgb[horizontal_lines[10]:horizontal_lines[11], name_x_start+1:name_x_end-10]
            # debug_name_crop_raw = cv2.cvtColor(debug_name_crop_raw, cv2.COLOR_RGB2GRAY)
            # cv2.imwrite("debug_name_crop_raw.png", debug_name_crop_raw)

            # debug_name_crop_binary = ocr.preprocess_for_ocr(debug_name_crop_raw)
            # cv2.imwrite("debug_name_crop_binary.png", debug_name_crop_binary)
            # # --------------- DEBUG IMAGE GENERATION -------------------------------

            # # --------------- SIGNATURE IMAGE GENERATION -------------------------------
            # debug_signature_crop = table_img_rgb[horizontal_lines[12]:horizontal_lines[13], attendance_x_start:attendance_x_end]
            # cv2.imwrite("debug_signature_crop.png", cv2.cvtColor(debug_signature_crop, cv2.COLOR_BGR2RGB))
            # # --------------- SIGNATURE IMAGE GENERATION -------------------------------

            # print(f"Name Extracted: {ocr.tesseract_ocr(debug_name_crop_raw)}")

            # Iterate over all rows
            for line_index in range(len(horizontal_lines) - 1):
                row_top_line, row_bottom_line = horizontal_lines[line_index], horizontal_lines[line_index+1]
                table_row_rgb = img_cropping.horizontal_img_crop(table_img_rgb, row_top_line, row_bottom_line)
                
                # Name sub-crop -> grayscale (tesseract_ocr requires Grayscale Img input)
                name_crop_rgb = img_cropping.vertical_img_crop(table_row_rgb, name_x_start+1, name_x_end-10)
                name_crop_gray = cv2.cvtColor(name_crop_rgb, cv2.COLOR_RGB2GRAY)
                ocr_name = ocr.tesseract_ocr(name_crop_gray)

                # Attendance sub-crop -> stays RGB for color classification
                attendance_crop_rgb = img_cropping.vertical_img_crop(table_row_rgb, attendance_x_start, attendance_x_end)
                attendance_status = classification.classify_attendance(attendance_crop_rgb)

                ocr_names.append(ocr_name)
                attendance_statuses.append(attendance_status)

            # ---- Detect Handwritten Names at Bottom of Sheet if any ----
            written_section = img_cropping.horizontal_img_crop(table_img_rgb, horizontal_lines[-1], end_of_img)
            # cv2.imwrite("./output/debug_written_section.png", written_section)
            written_names = img_cropping.vertical_img_crop(written_section, name_x_start, name_x_end)
            written_names_gray = cv2.cvtColor(written_names, cv2.COLOR_BGR2GRAY)

            # cv2.imwrite("written_names_gray.png", written_names_gray)
            written_flag = ocr.detect_handwritten_names(written_names_gray)

            if written_flag:
                ocr_names.append('WRITTEN NAME DETECTED')
                attendance_statuses.append('Present')

            print('Processed one sheet\n')
                
        # --- Stage 6: Assemble Raw Dataframe ---
        attendance_df = pd.DataFrame({'ocr_raw': ocr_names, 'attendance': attendance_statuses})

        # if written_flag:
        #     manual_entry = pd.DataFrame([{'ocr_raw': 'WRITTEN NAME DETECTED', 'attendance': 'Present'}])
        #     attendance_df = pd.concat([attendance_df, manual_entry], ignore_index=True)

        # --- Stage 7: Reconciliation (clean + fuzzy_match + flag)
        reconciled_df = reconciliation.fuzzy_match_names(attendance_df, 
                                                         cfg.roster,
                                                         threshold = cfg.fuzzy_match_threshold,
                                                         low_match_floor = cfg.low_match_floor)

        # NOTE: no date prompt, no excel export here - main.py handles that
        return reconciled_df

