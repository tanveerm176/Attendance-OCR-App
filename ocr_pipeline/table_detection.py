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
    # --- Stage 0: Assert input image is grayscale ---
    assert gray_img.ndim == 2, f'Expected Grayscale Image with 2 channels, received {gray_img.shape}'

    # --- Stage 1: Create a binary version of the image and invert ---
    # Set pixels < 150 to 0 and pixels > 150 to 255 
    # Morphological operations in OpenCV process white pixels as
    #  foreground objects and black pixels as background
    _, binary = cv2.threshold(gray_img, 150, 255, cv2.THRESH_BINARY_INV)
    vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1,100))
    v_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, vertical_kernel)

    # --- Stage 2: Sum pixels down each COLUMN of image bin matrix ----
    #   produce 1D array of how many white pixels exist in the COLUMN 
    # Peaks indicate vertical line positions
    col_sums = np.sum(v_lines, axis=0) # axis=0 -> cols instead of axis=1

    # Find rows with significant white pixels (actual lines)
    line_threshold = np.max(col_sums) * 0.3 
    line_cols = np.where(col_sums > line_threshold)[0]

    # --- Stage 3: Cluster nearby columns together ---
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
    assert gray_img.ndim == 2, f'Expected Grayscale Image with 2 channels, received {gray_img.shape}'

    _, binary = cv2.threshold(gray_img, 150, 255, cv2.THRESH_BINARY_INV)
    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (105,1))
    h_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel)

    row_sums = np.sum(h_lines, axis=1)
    line_threshold = np.max(row_sums) * 0.2 # change to 0.1 when image rotated
    line_rows = np.where(row_sums > line_threshold)[0]

    horizontal_line_positions = []
    if len(line_rows) > 0:
        row_cluster = [line_rows[0]]

        for curr_row in line_rows[1:]:
            if curr_row - row_cluster[-1] < 10:
                row_cluster.append(curr_row)
            else:
                horizontal_line_positions.append(int(np.mean(row_cluster)))
                row_cluster = [curr_row]

        horizontal_line_positions.append(int(np.mean(row_cluster)))

    return horizontal_line_positions


def split_student_rows_and_handwritten_region(
    horizontal_lines: list[int],
    image_height: int,
) -> tuple[list[tuple[int, int]], tuple[int, int]]:
    """Split detected horizontal boundaries into student rows and write-in area.

    Each consecutive pair of boundaries defines a candidate row. The median
    interval height provides a page-specific estimate of a normal student row,
    allowing unusually short line artifacts and large footer gaps to be ignored.
    When a large gap follows the last normal row, its first part is reserved for
    handwriting and capped so the crop does not extend far into the footer.

    If there is no such gap, reserve a typical-sized region immediately below
    the final detected boundary instead.

    Returns:
        A list of (top, bottom) student-row bounds and (start, end) bounds for
        the handwriting region. All bounds are vertical pixel coordinates.
    """
    # Measure the height of every interval between neighboring horizontal lines.
    row_heights = np.diff(horizontal_lines)
    if len(row_heights) == 0 or np.any(row_heights <= 0):
        raise ValueError("Horizontal lines must contain increasing row boundaries")

    # Median height is robust to a few bad detections or merged rows.
    typical_row_height = float(np.median(row_heights))
    # Accept normal variation, but exclude short border artifacts and merged/footer gaps.
    min_row_height = typical_row_height * 0.5
    max_row_height = typical_row_height * 1.5

    # Keep only intervals close enough to the typical student-row height.
    student_rows = [
        (top, bottom)
        for top, bottom in zip(horizontal_lines, horizontal_lines[1:])
        if min_row_height <= bottom - top <= max_row_height
    ]
    if not student_rows:
        raise ValueError("Could not identify any normal-height student rows")

    last_student_bottom = student_rows[-1][1]
    next_line_index = horizontal_lines.index(last_student_bottom) + 1

    # A large gap after the final student row is the write-in/footer area.
    if next_line_index < len(horizontal_lines):
        next_line = horizontal_lines[next_line_index]
        if next_line - last_student_bottom > max_row_height:
            # Limit the crop to three row heights to avoid including a distant logo.
            max_handwritten_height = round(typical_row_height * 3)
            handwritten_end = min(
                next_line, last_student_bottom + max_handwritten_height
            )
            return student_rows, (last_student_bottom, handwritten_end)

    # Without a detected gap, inspect a bounded region just below the last line.
    handwriting_height = round(typical_row_height * 1.5)
    handwritten_start = horizontal_lines[-1]
    handwritten_end = min(image_height, handwritten_start + handwriting_height)
    return student_rows, (handwritten_start, handwritten_end)
