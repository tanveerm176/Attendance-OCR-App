import os
import cv2
import numpy as np
import pytesseract
from ocr_pipeline.reconciliation import clean_ocr_name

# pytesseract.pytesseract.tesseract_cmd = r'C:\Users\mtanveer\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'

# Only override pytesseract's default PATH-based lookup if TESSERACT_CMD
# is explicitly set. Local dev machines without Tesseract on PATH should
# set this in their own environment; CI and properly-configured machines
# rely on PATH resolution automatically.    

tesseract_cmd = os.getenv("TESSERACT_CMD")
if tesseract_cmd:
    pytesseract.pytesseract.tesseract_cmd = tesseract_cmd


def preprocess_for_ocr(gray_img: np.ndarray) -> np.ndarray:
    # 2. Threshold (Invert: White text/line on Black background)
    _, binary = cv2.threshold(gray_img, 180, 255, cv2.THRESH_BINARY_INV)

    # 4. Slightly thicken (dilate) the 'Ink Free' font strokes 
    # This fills in thin gaps in stylized fonts that make '2' look like '7'
    kernel_dilate = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    thickened = cv2.dilate(binary, kernel_dilate, iterations=1)

    # 5. Invert back for Tesseract (Black text on White)
    processed = cv2.bitwise_not(thickened)
    
    return processed

def tesseract_ocr(image_cell_gray: np.ndarray) -> str:
    assert image_cell_gray.ndim == 2, f'Expected Grayscale Image with 2 channels, received {image_cell_gray.shape}'
    processed = preprocess_for_ocr(image_cell_gray)
    ocr_result = pytesseract.image_to_string(processed)

    # print(f'OCR RESULT---->:{ocr_result}')

    # if tesseract ocr fails on processed, try on just tesseract
    if ocr_result == '':
        only_tesseract = pytesseract.image_to_string(image_cell_gray)

        # cv2.imwrite(f"reporting/OCR_failed_{clean_ocr_name(only_tesseract)}.png", 
        #             processed)

        # print(f'OCR RETRY----->:{only_tesseract}')

        return only_tesseract

    return ocr_result


def detect_handwritten_names(image_cell_gray: np.ndarray) -> bool:
    handwritten_flag = False

    written_ocr = tesseract_ocr(image_cell_gray)
    # print(written_ocr)
    
    if written_ocr != '':
        handwritten_flag = True

    return handwritten_flag 