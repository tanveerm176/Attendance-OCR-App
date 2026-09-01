import numpy as np
import cv2

def classify_attendance(cell_img_rgb: np.ndarray) -> str:
    # --- Stage 0: image conversion ---
    # convert RGB image to HSV for more accurate color analysis

    img_hsv = cv2.cvtColor(cell_img_rgb, cv2.COLOR_RGB2HSV)
    img_hue = img_hsv[:, :, 0]
    img_saturation = img_hsv[:, :, 1]
    img_value = img_hsv[:, :, 2]

    attendance_status = ''

    # --- Stage 1: background mask ---
    # low saturation threshold to catch faded ink
    # high value threshold to exclude bright white paper
    not_background = (img_saturation > 10) & (img_value < 245)

    if not_background.sum() < 30:
        attendance_status = 'EMPTY CELL' # genuinely empty cell
        return attendance_status

    # --- Stage 2: classify by hue on saturated pixels ---
    # only pixels with enough saturation to trust the hue reading 
    saturated = not_background & (img_saturation > 20)

    red_pixels = saturated & ((img_hue <  12) | (img_hue > 158))
    blue_pixels = saturated & (img_hue > 90) & (img_hue < 140)

    red_count = red_pixels.sum()
    blue_count = blue_pixels.sum()

    # --- Stage 3: fallback for low saturated ink ---
    # if neither color has enough saturated pixels to decide, 
    #   fall back to RGB channel difference on all ink pixels
    if red_count < 20 and blue_count < 20:
        blue_channel = cell_img_rgb[:, :, 0].astype(float)
        red_channel = cell_img_rgb[:, :, 2].astype(float)

        mask = not_background

        blue_mean = blue_channel[mask].mean()
        red_mean = red_channel[mask].mean()

        if (red_mean - blue_mean) > -20:
            attendance_status = 'Absent'
        else:
            attendance_status = 'Present'
        return attendance_status

    # --- Stage 4: decide by pixel count ---
    if red_count >= blue_count:
        attendance_status = 'Absent'
    else:
        attendance_status = 'Present'
    
    return attendance_status