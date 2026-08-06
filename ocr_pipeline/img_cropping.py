import numpy as np

def vertical_img_crop(img:np.ndarray, x_start:int, x_end:int) -> np.ndarray:
    if x_start < 0 or x_end > img.shape[1] or x_start >= x_end:
        raise ValueError(f"Invalid x bounds: x_start={x_start}, x_end={x_end}, img width={img.shape[1]}")
    return img[:,x_start:x_end]

def horizontal_img_crop(img:np.ndarray, y_start:int, y_end:int) -> np.ndarray:
    if y_start < 0 or y_end > img.shape[0] or y_start >= y_end:
        raise ValueError(f"Invalid y bounds: y_start={y_start}, y_end={y_end}, img height={img.shape[0]}")
    return img[y_start:y_end,:]