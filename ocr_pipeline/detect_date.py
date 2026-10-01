import numpy as np
from datetime import datetime
from ocr_pipeline.ocr import tesseract_ocr

def detect_sheet_date(table_img_gray: np.ndarray, row_positions, col_positions) -> datetime:
    
    date_section = table_img_gray[row_positions[0]-150:row_positions[0]-10,:col_positions[2]]
    date_ocr = tesseract_ocr(date_section).strip().replace(" ", "")
    colon_mark = date_ocr.find(':')
    date_str = date_ocr[colon_mark+1:]

    sheet_date = datetime.strptime(date_str, '%m/%d/%Y')

    return sheet_date