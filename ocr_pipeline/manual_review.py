"""Visual review of OCR records that need an operator's name selection."""

from __future__ import annotations

import base64
from collections.abc import Callable, Sequence

import cv2
import numpy as np
import pandas as pd
import tkinter as tk
from tkinter import ttk
from ocr_pipeline.models import DailyAttendance, AttendanceRecord

from ocr_pipeline.constants import RESOLVED_MANUALLY_FLAG

# Signature of a pluggable review UI, used instead of the Tk window (e.g. in tests).
# Arguments: name crop, flag, OCR text, match score, roster, suggested name.
# Returns the chosen roster name, or None to skip the record.
NameSelectionDialog = Callable[
    [np.ndarray, str, str, float, Sequence[str], str | None],
    str | None,
]


def _encode_preview(image_rgb: np.ndarray, max_width: int = 800, max_height: int = 300) -> str:
    """Convert an RGB image into a base64 PNG string that Tk can display.

    The image is shrunk, keeping its aspect ratio, to fit within max_width and
    max_height. Smaller images are never enlarged.

    Raises:
        ValueError: If the image cannot be encoded as a PNG.
    """
    # if image_rgb.ndim != 3 or image_rgb.shape[2] != 3 or image_rgb.size == 0:
    #     raise ValueError("Review crop must be a non-empty RGB image")

    height, width = image_rgb.shape[:2]
    # A scale of 1.0 is the cap so small crops are not upscaled.
    scale = min(1.0, max_width / width, max_height / height)
    if scale < 1.0:
        image_rgb = cv2.resize(
            image_rgb,
            (max(1, round(width * scale)), max(1, round(height * scale))),
            interpolation=cv2.INTER_AREA,
        )

    # OpenCV's encoder expects BGR channel order, so convert before encoding.
    image_bgr = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)
    encoded, buffer = cv2.imencode(".png", image_bgr)
    if not encoded:
        raise ValueError("Could not encode the OCR review crop as a PNG")

    return base64.b64encode(buffer).decode("ascii")


def _show_review_queue(daily_attendance: DailyAttendance, 
                       review_records: list[AttendanceRecord], 
                       roster: Sequence[str], 
                       *, 
                       parent: tk.Tk) -> None:
    
    """Show a single window that steps through each record needing review.

    For every record the operator sees the name crop, the OCR text, the flag and
    the match score, and either picks a roster name or skips the record. Picking
    a name updates the record in place (matched_name and match_flag). This
    function blocks in the Tk main loop until the last record is handled or the
    window is closed.

    Args:
        daily_attendance: The sheet the records belong to.
        review_records: The records to show, in order. Each needs a review crop.
        roster: Valid student names offered in the dropdown.
        parent: The Tk root window to build the UI in.
    """
    parent.title("Review OCR names")
    parent.resizable(True, True)

    progress_label = ttk.Label(parent)
    progress_label.pack(padx=12, pady=(12, 4))
    flag_label = ttk.Label(parent)
    flag_label.pack(padx=12, pady=4)
    ocr_label = ttk.Label(parent)
    ocr_label.pack(padx=12, pady=4)
    score_label = ttk.Label(parent)
    score_label.pack(padx=12, pady=4)

    image_label = ttk.Label(parent)
    image_label.pack(padx=12, pady=8)

    ttk.Label(parent, text="Select the student's name:").pack(padx=12, pady=(4, 2))
    selected_name = tk.StringVar()
    name_picker = ttk.Combobox(
        parent,
        textvariable=selected_name,
        values=list(roster),
        state="readonly",
        width=45,
    )
    name_picker.pack(padx=12, pady=(0, 8))

    # State shared by the nested callbacks below (they rebind it with nonlocal).
    current_review = 0  # index into review_records of the record on screen
    confirm_button: ttk.Button  # created after the callbacks that reference it
    current_photo: tk.PhotoImage | None = None

    def update_confirm_state(_event: object = None) -> None:
        """Enable the confirm button only while a name is selected."""
        confirm_button.configure(state="normal" if selected_name.get() else "disabled")

    def show_current_record() -> None:
        """Fill the window's labels, image and dropdown for the current record."""
        nonlocal current_photo
        record = review_records[current_review]
        flag = record.match_flag
        ocr_name = record.ocr_name
        match_score = record.match_score
        crop = record.review_crop
        if not isinstance(crop, np.ndarray):
            raise ValueError(f"Missing image crop for OCR review row {record.record_index}")

        progress_label.configure(
            text=f"Review record {current_review + 1} of {len(review_records)}"
        )
        flag_label.configure(text=f"Review required: {flag}")
        ocr_label.configure(text=f"OCR text: {ocr_name or '(empty)'}")
        score_label.configure(text=f"Match score: {match_score:g}")

        # Tkinter doesn't hold a Python reference to the image, so keep one in the
        # enclosing scope or it is garbage-collected and the label goes blank.
        current_photo = tk.PhotoImage(data=_encode_preview(crop), format="png")
        image_label.configure(image=current_photo)

        # Pre-select the fuzzy-match suggestion so the operator can just confirm it.
        suggested_name = record.matched_name
        selected_name.set(suggested_name if isinstance(suggested_name, str) else "")
        update_confirm_state()

    def advance(selection: str | None = None) -> None:
        """Apply the operator's choice to the current record and move to the next.

        A selection of None means the record was skipped and is left unchanged.
        Closes the window after the last record.
        """
        nonlocal current_review
        record = review_records[current_review]

        if selection is not None:
            record.matched_name = selection
            record.match_flag = RESOLVED_MANUALLY_FLAG
            record.reviewed = True
            record.review_crop = None

        current_review += 1

        if current_review == len(review_records):
            # quit() only stops the main loop; the caller destroys the window.
            parent.quit()
            return
        
        show_current_record()

    def confirm() -> None:
        """Accept the dropdown choice, but only if it is a valid roster name."""
        if selected_name.get() in roster:
            advance(selected_name.get())

    buttons = ttk.Frame(parent)
    buttons.pack(fill="x", padx=12, pady=(0, 12))

    ttk.Button(buttons, text="Skip", command=lambda: advance()).pack(side="right")
    confirm_button = ttk.Button(buttons, text="Use selected name", command=confirm)

    confirm_button.pack(side="right", padx=(0, 8))
    name_picker.bind("<<ComboboxSelected>>", update_confirm_state)

    # Closing the window with the X ends the review; remaining records are left unchanged.
    parent.protocol("WM_DELETE_WINDOW", parent.quit)
    name_picker.focus_set()
    show_current_record()

    # Bring the window to the front so it isn't hidden behind other apps.
    parent.update_idletasks()
    parent.deiconify()
    parent.lift()
    parent.focus_force()
    parent.mainloop()


def review_flagged_records(daily_attendance: DailyAttendance, 
                           roster: Sequence[str], 
                           *, 
                           dialog: NameSelectionDialog | None = None) -> None:
    """Let an operator resolve the records on a sheet that were flagged for review.

    Records are updated in place: a confirmed choice sets matched_name and
    sets match_flag to RESOLVED_MANUALLY_FLAG. Skipped records are unchanged.

    Args:
        daily_attendance: The sheet whose records are reviewed.
        roster: Valid student names the operator may choose from.
        dialog: Optional replacement for the Tk window. It is called once per
            record and returns the chosen name or None to skip.

    Raises:
        ValueError: If the roster is empty, a flagged record has no image crop,
            or a dialog returns a name that is not in the roster.
    """
    # Create list of records that are flagged for review
    # needs_review is True for flagged records that haven't been resolved yet
    review_records = [student_record
                        for student_record in daily_attendance.records 
                        if student_record.needs_review]

    if not review_records:
        print("Name reconciliation complete: no records need manual review.")
        return None

    print(f"Name reconciliation complete: {len(review_records)} records need review.")

    if dialog is None:
        if not roster:
            raise ValueError("Cannot review flagged OCR names with an empty roster")
        
        # Fail up front rather than partway through the review session.
        for record in review_records:
            if not isinstance(record.review_crop, np.ndarray):
                raise ValueError(f"Missing image crop for OCR review row {record.record_index}")
            
        root = tk.Tk()

        try:
            _show_review_queue(daily_attendance, review_records, roster, parent=root)
            return None
        
        finally:
            # Always release the Tk window, even if the review raises.
            root.destroy()

    # Custom dialog path (not yet migrated to DailyAttendance records).
    for record in review_records:
        flag = record.match_flag
        crop = record.review_crop

        if not isinstance(crop, np.ndarray):
            raise ValueError(f"Missing image crop for OCR review row {record.record_index}")

        score = record.match_score
        print(f"Reviewing record {record.record_index} of {len(review_records)} ({flag}).")

        selection = dialog(
            crop,
            str(flag),
            record.ocr_name,
            float(score),
            roster,
            record.matched_name,
        )

        if selection is None:
            continue

        if selection not in roster:
            raise ValueError(f"Selected name is not present in the roster: {selection}")

        record.matched_name = selection
        record.match_flag = RESOLVED_MANUALLY_FLAG

        # drop crop after review and set reviewed to True
        record.review_crop = None
        record.reviewed = True

    return None
