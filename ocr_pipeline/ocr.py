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


def remove_red_strikethrough(image_rgb: np.ndarray) -> np.ndarray:
    """Remove red marks from an RGB crop before it is converted to grayscale.

    The image is converted to HSV so red can be identified across the hue
    range's wraparound at zero. Pixels matching either red hue range are
    combined into a mask, then OpenCV inpaints those pixels from nearby
    content so the mark is less likely to interfere with name OCR.

    If no red pixels are found, return an unchanged copy of the input.
    """
    if image_rgb.ndim != 3 or image_rgb.shape[2] != 3:
        raise ValueError(
            f"Expected an RGB image with 3 channels, received {image_rgb.shape}"
        )

    # HSV separates hue from brightness and saturation, making red ink easier
    # to detect than with fixed RGB channel comparisons.
    hsv = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2HSV)

    # Red straddles the beginning/end of OpenCV's hue range, so cover both.
    lower_red = cv2.inRange(hsv, np.array([0, 45, 50]), np.array([10, 255, 255]))
    upper_red = cv2.inRange(hsv, np.array([170, 45, 50]), np.array([180, 255, 255]))
    red_mask = cv2.bitwise_or(lower_red, upper_red)

    if not np.any(red_mask):
        return image_rgb.copy()

    # Replace masked pixels using nearby image content rather than white, which
    # could erase parts of letters where the strike crosses the printed name.
    return cv2.inpaint(image_rgb, red_mask, 3, cv2.INPAINT_TELEA)


def tesseract_ocr(image_cell_gray: np.ndarray) -> str:
    assert image_cell_gray.ndim == 2, f'Expected Grayscale Image with 2 channels, received {image_cell_gray.shape}'
    processed = preprocess_for_ocr(image_cell_gray)
    ocr_result = pytesseract.image_to_string(processed).strip()

    # print(f'OCR RESULT---->:{ocr_result}')

    # if tesseract ocr fails on processed, try on just tesseract
    if ocr_result == '':
        only_tesseract = pytesseract.image_to_string(image_cell_gray).strip()

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