import cv2
import numpy as np
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r'C:\Users\mtanveer\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'

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

def tesseract_ocr(image_cell_gray: np.ndarray, tesseract_config: str = r'--oem 1 --psm 7') -> str:
    assert image_cell_gray.ndim == 2, f'Expected Grayscale Image with 2 channels, received {image_cell_gray.shape}'
    processed = preprocess_for_ocr(image_cell_gray)
    # return pytesseract.image_to_string(processed, config=tesseract_config)
    return pytesseract.image_to_string(processed)