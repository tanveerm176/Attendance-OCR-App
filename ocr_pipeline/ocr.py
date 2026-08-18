import cv2
import numpy as np
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r'C:\Users\mtanveer\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'

def preprocess_for_ocr(gray_img: np.ndarray) -> np.ndarray:
    # Upscale — tesseract loves large images
    # scaled = cv2.resize(gray_img, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    # 2. Threshold (Invert: White text/line on Black background)
    _, binary = cv2.threshold(gray_img, 180, 255, cv2.THRESH_BINARY_INV)

    # 3. Remove the horizontal line
    # Create a horizontal kernel long enough to capture the line but not character strokes
    kernel_line = cv2.getStructuringElement(cv2.MORPH_RECT, (30, 1))
    detected_line = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_line)

    # Subtract line from image
    text_only = cv2.subtract(binary, detected_line)

    # 4. Slightly thicken (dilate) the 'Ink Free' font strokes 
    # This fills in thin gaps in stylized fonts that make '2' look like '7'
    kernel_dilate = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    thickened = cv2.dilate(binary, kernel_dilate, iterations=1)

    # 5. Invert back for Tesseract (Black text on White)
    processed = cv2.bitwise_not(thickened)
    
    return processed

def tesseract_ocr(image_cell: np.ndarray) -> str:
    custom_config = r'--oem 1 --psm 7'
    processed = preprocess_for_ocr(image_cell)
    return pytesseract.image_to_string(processed, config=custom_config)