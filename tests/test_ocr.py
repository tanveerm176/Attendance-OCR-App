import numpy as np
import pytest
from ocr_pipeline.ocr import preprocess_for_ocr, tesseract_ocr

# Pass in image of text, verify str matches 
# Pass in image of text, verify that output of preprocess is image (np.ndarray)