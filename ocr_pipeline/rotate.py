import os
import pytesseract
import numpy as np
import imutils

from pytesseract import Output


tesseract_cmd = os.getenv("TESSERACT_CMD")
if tesseract_cmd:
    pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

def detect_rotation(img_gray: np.ndarray) -> dict:
    results_dict = pytesseract.image_to_osd(img_gray, output_type=Output.DICT)
    print(f'Rotation Angle Needed: {results_dict['rotate']}')
    return results_dict

def rotate_image(img: np.ndarray, rotation_angle:int) -> np.ndarray:
    img_rotated = imutils.rotate_bound(img, angle=rotation_angle)
    print(f'Rotated Image by: {rotation_angle}')
    return img_rotated