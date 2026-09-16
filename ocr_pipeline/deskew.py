import numpy as np
import cv2


def get_skew_angle(gray_img: np.ndarray) -> float:
    # gray_img = cv2.cvtColor(scanned_img, cv2.COLOR_RGB2GRAY)

    # Binarize and invert
    _, binary = cv2.threshold(gray_img, 150, 255, cv2.THRESH_BINARY_INV)
    
    # Edge detection first — Hough works on edges not filled regions
    edges = cv2.Canny(binary, 50, 150, apertureSize=3)
    
    # Detect lines using Hough transform
    # rho=1, theta=pi/180 → 1 pixel and 1 degree resolution
    # threshold=200 → minimum votes to be considered a line (tune this)
    lines = cv2.HoughLines(edges, 1, np.pi/1800, threshold=650)
    
    if lines is None:
        print("No lines detected — try lowering threshold")
        return 0
    
    # Extract angles from all detected lines
    angles = []
    for line in lines:
        rho, theta = line[0]
        # Convert to degrees, center around 0
        angle = np.degrees(theta) - 90
        # Only keep near-horizontal lines (your table rows)
        if -10 < angle < 10:
            angles.append(angle)
    
    if not angles:
        print("No horizontal lines found")
        return 0
    
    # Median is more robust than mean — ignores outliers
    skew_angle = np.median(angles)
    print(f"Detected skew: {skew_angle:.4f} degrees")
    print(f"Lines used for estimate: {len(angles)}")

    # if viz_skew:
    #     # Draw detected lines on the image to see what it found
    #     debug_img = cv2.cvtColor(gray_img, cv2.COLOR_GRAY2BGR)

    #     if lines is not None:
    #         for line in lines:
    #             rho, theta = line[0]
    #             a, b = np.cos(theta), np.sin(theta)
    #             x0, y0 = a*rho, b*rho
    #             x1 = int(x0 + 2000*(-b))
    #             y1 = int(y0 + 2000*(a))
    #             x2 = int(x0 - 2000*(-b))
    #             y2 = int(y0 - 2000*(a))
    #             cv2.line(debug_img, (x1,y1), (x2,y2), (0,0,255), 1)

    #     plt.figure(figsize=(6, 8))
    #     plt.imshow(cv2.cvtColor(debug_img, cv2.COLOR_BGR2RGB))
    #     plt.title(f'Detected lines: {len(lines) if lines is not None else 0}')
    #     plt.axis('off')
    #     plt.show()
    print(f'Image Skewed by: {skew_angle}')
    return skew_angle

def correct_skew(img: np.ndarray, skew_angle: float) -> np.ndarray:

    (h, w) = img.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, skew_angle, 1.0)
    deskewed_img = cv2.warpAffine(img, M, (w, h),
                               flags=cv2.INTER_CUBIC,
                               borderMode=cv2.BORDER_REPLICATE)
    return deskewed_img