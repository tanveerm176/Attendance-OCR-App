import cv2
import numpy as np

def get_vertical_line_positions(gray_img: np.ndarray) -> list[int]:
    """
    Detects vertical grid lines in a grayscale image using morphological opening.
    Returns a sorted list of x-coordinates where vertical lines are found.

    Args:
        gray_img: grayscale numpy array of the full page

    Returns:
        vertical_line_positions: sorted list of x pixel coordinates
    """
    # Stage1: Create a binary version of the image and invert
    # Set pixels < 150 to 0 and pixels > 150 to 255 
    # Morphological operations in OpenCV process white pixels as
    #  foreground objects and black pixels as background
    _, binary = cv2.threshold(gray_img, 150, 255, cv2.THRESH_BINARY_INV)
    veritcal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1,100))
    v_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, veritcal_kernel)

    # Stage2: Sum pixels down each COLUMN of image bin matrix,
    #  produce 1D array of how many white pixels exist in the COLUMN 
    # Peaks indicate vertical line positions
    col_sums = np.sum(v_lines, axis=0) # axis=0 -> cols instead of axis=1

    # Find rows with significant white pixels (actual lines)
    line_threshold = np.max(col_sums) * 0.3 
    line_cols = np.where(col_sums > line_threshold)[0]

    # Stage3: Cluster nearby columns together
    vertical_line_positions = []

    if len(line_cols) > 0:
        # assign first col to cluster list
        col_cluster = [line_cols[0]]

        # iterate over the col positions starting from the second element onward
        for curr_col in line_cols[1:]:
            # if two adjacent cols are < 5 pixels apart, cluster them together
            if curr_col - col_cluster[-1] < 5:
                col_cluster.append(curr_col)
            # once cols are > 5 pixels apart, mean(cluster) and add to line_positions
            # set new cluster to the last col that was iterated to
            else:
                vertical_line_positions.append(int(np.mean(col_cluster)))
                col_cluster = [curr_col]

        # once all cols are iterated, mean the last cluster list into the final line
        vertical_line_positions.append(int(np.mean(col_cluster)))

    return vertical_line_positions


def get_horizontal_line_positions(gray_img: np.ndarray) -> list[int]:
    """
    Detects horizontal grid lines in a grayscale image using morphological opening.
    Returns a sorted list of y-coordinates where horizontal lines are found.

    Args:
        gray_img: grayscale numpy array of the full page

    Returns:
        horizontal_line_positions: sorted list of y pixel coordinates
    """
    _, binary = cv2.threshold(gray_img, 150, 255, cv2.THRESH_BINARY_INV)
    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (105,1))
    h_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel)

    row_sums = np.sum(h_lines, axis=1)
    line_threshold = np.max(row_sums) * 0.5
    line_rows = np.where(row_sums > line_threshold)[0]

    horizontal_line_positions = []
    if len(line_rows) > 0:
        row_cluster = [line_rows[0]]

        for curr_row in line_rows[1:]:
            if curr_row - row_cluster[-1] < 5:
                row_cluster.append(curr_row)
            else:
                horizontal_line_positions.append(int(np.mean(row_cluster)))
                row_cluster = [curr_row]

        horizontal_line_positions.append(int(np.mean(row_cluster)))

    return horizontal_line_positions