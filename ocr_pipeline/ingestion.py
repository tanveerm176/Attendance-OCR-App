import fitz
import numpy as np
import cv2
from ocr_pipeline.config import DPI
from pathlib import Path

def pdf_to_image(pdf_path: Path) -> tuple[np.ndarray, np.ndarray]:
    """
    Opens a scanned PDF, renders the first page at 300 DPI,
    and returns it as an RGB numpy array.

    Args:
        pdf_path: path to the scanned PDF file

    Returns:
        img_rgb: HxWx3 numpy array in RGB color space
    """
    pdf_document = fitz.open(pdf_path)
    page = pdf_document[0]

    # Render to pixel map - zoom = OCR resolution 300dpi
    zoom = DPI/72 # PDF points to pixels (1 inch = 72 pts)
    mat = fitz.Matrix(zoom, zoom)
    pixmap = page.get_pixmap(matrix=mat)

    """
    Convert to numpy array so OpenCV & MatPlotLib can work with it
    pdf_img.samples = 1D stream of bytes of image
    reshaped to 2D matrix of height x width & 3 color channels
    """
    img_rgb = np.frombuffer(pixmap.samples, dtype=np.uint8,).reshape(
        pixmap.height, pixmap.width, pixmap.n
        )

    img_gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)

    pdf_document.close()
    
    return img_rgb, img_gray