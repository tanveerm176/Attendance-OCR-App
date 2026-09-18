import os
import pytesseract
import numpy as np
import imutils
import cv2

from pytesseract import Output


tesseract_cmd = os.getenv("TESSERACT_CMD")
if tesseract_cmd:
    pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

def detect_rotation(img_gray: np.ndarray) -> dict:
    results_dict = pytesseract.image_to_osd(img_gray, output_type='dict', config="--psm 0")
    print(results_dict)
    print(f'Rotation Angle Needed: {results_dict['rotate']}')
    return results_dict

def rotate_image(img: np.ndarray, rotation_angle:int) -> np.ndarray:
    img_rotated = imutils.rotate_bound(img, angle=rotation_angle)
    print(f'Rotated Image by: {rotation_angle}')
    return img_rotated

def correct_orientation(image: np.ndarray) -> np.ndarray:
    osd = pytesseract.image_to_osd(image, output_type=Output.DICT)
    rotate_angle = osd["rotate"]

    if rotate_angle == 0:
        return image
    elif rotate_angle == 90:
        return cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
    elif rotate_angle == 180:
        return cv2.rotate(image, cv2.ROTATE_180)
    elif rotate_angle == 270:
        return cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
    else:
        # OSD contract only guarantees 0/90/180/270 — anything else means
        # OSD returned something unexpected, worth surfacing rather than
        # silently falling through
        raise ValueError(f"Unexpected OSD rotate value: {rotate_angle}")