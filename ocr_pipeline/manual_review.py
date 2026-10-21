"""Visual review of OCR records that need an operator's name selection."""

from __future__ import annotations

import base64
from collections.abc import Callable, Sequence

import cv2
import numpy as np
import pandas as pd
import tkinter as tk
from tkinter import ttk

from ocr_pipeline.exceptions import NoMatchFoundError, OCRExtractionError
from ocr_pipeline.reconciliation import LOW_MATCH_LABEL

REVIEW_CROP_COLUMN = "_review_crop"
RESOLVED_MANUALLY_FLAG = "Resolved - Manual Review"
REVIEW_FLAGS = {
    OCRExtractionError.__name__,
    NoMatchFoundError.__name__,
    LOW_MATCH_LABEL,
    "NEED-MANUAL-ENTRY",
}

NameSelectionDialog = Callable[
    [np.ndarray, str, str, float, Sequence[str], str | None],
    str | None,
]


def _encode_preview(image_rgb: np.ndarray, max_width: int = 800, max_height: int = 300) -> str:
    # if image_rgb.ndim != 3 or image_rgb.shape[2] != 3 or image_rgb.size == 0:
    #     raise ValueError("Review crop must be a non-empty RGB image")

    height, width = image_rgb.shape[:2]
    scale = min(1.0, max_width / width, max_height / height)
    if scale < 1.0:
        image_rgb = cv2.resize(
            image_rgb,
            (max(1, round(width * scale)), max(1, round(height * scale))),
            interpolation=cv2.INTER_AREA,
        )

    image_bgr = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)
    encoded, buffer = cv2.imencode(".png", image_bgr)
    if not encoded:
        raise ValueError("Could not encode the OCR review crop as a PNG")

    return base64.b64encode(buffer).decode("ascii")


def _show_review_queue(
    dataframe: pd.DataFrame,
    review_positions: list[int],
    roster: Sequence[str],
    *,
    parent: tk.Tk,
) -> None:
    """Review all flagged rows in one window, advancing after each decision."""
    parent.title("Review OCR names")
    parent.resizable(False, False)

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

    current_review = 0
    confirm_button: ttk.Button

    def update_confirm_state(_event: object = None) -> None:
        confirm_button.configure(state="normal" if selected_name.get() else "disabled")

    def show_current_record() -> None:
        position = review_positions[current_review]
        flag = str(dataframe.iloc[position]["flag"])
        ocr_name = str(dataframe.iloc[position]["ocr_raw"])
        match_score = float(dataframe.iloc[position]["matched_score"])
        crop = dataframe.iloc[position][REVIEW_CROP_COLUMN]
        if not isinstance(crop, np.ndarray):
            raise ValueError(f"Missing image crop for OCR review row {position + 1}")

        progress_label.configure(
            text=f"Review record {current_review + 1} of {len(review_positions)}"
        )
        flag_label.configure(text=f"Review required: {flag}")
        ocr_label.configure(text=f"OCR text: {ocr_name or '(empty)'}")
        score_label.configure(text=f"Match score: {match_score:g}")
        photo = tk.PhotoImage(data=_encode_preview(crop), format="png")
        image_label.configure(image=photo)
        image_label.image = photo
        suggested_name = dataframe.iloc[position]["matched_name"]
        selected_name.set(suggested_name if isinstance(suggested_name, str) else "")
        update_confirm_state()

    def advance(selection: str | None = None) -> None:
        nonlocal current_review
        position = review_positions[current_review]
        if selection is not None:
            dataframe.iat[position, dataframe.columns.get_loc("matched_name")] = selection
            dataframe.iat[position, dataframe.columns.get_loc("flag")] = (
                RESOLVED_MANUALLY_FLAG
            )

        current_review += 1
        if current_review == len(review_positions):
            parent.quit()
            return
        show_current_record()

    def confirm() -> None:
        if selected_name.get() in roster:
            advance(selected_name.get())

    buttons = ttk.Frame(parent)
    buttons.pack(fill="x", padx=12, pady=(0, 12))
    ttk.Button(buttons, text="Skip", command=lambda: advance()).pack(side="right")
    confirm_button = ttk.Button(buttons, text="Use selected name", command=confirm)
    confirm_button.pack(side="right", padx=(0, 8))
    name_picker.bind("<<ComboboxSelected>>", update_confirm_state)
    parent.protocol("WM_DELETE_WINDOW", parent.quit)
    name_picker.focus_set()
    show_current_record()
    parent.update_idletasks()
    parent.deiconify()
    parent.lift()
    parent.focus_force()
    parent.mainloop()


def review_flagged_records(
    dataframe: pd.DataFrame,
    roster: Sequence[str],
    *,
    dialog: NameSelectionDialog | None = None,
) -> pd.DataFrame:
    """Review flagged rows and apply confirmed roster choices to a copy."""
    required_columns = {"flag", "ocr_raw", "matched_name", "matched_score", REVIEW_CROP_COLUMN}
    missing_columns = required_columns.difference(dataframe.columns)
    if missing_columns:
        raise ValueError(
            f"Attendance data is missing review columns: {sorted(missing_columns)}"
        )

    reviewed = dataframe.copy()
    flag_column = reviewed.columns.get_loc("flag")
    ocr_column = reviewed.columns.get_loc("ocr_raw")
    name_column = reviewed.columns.get_loc("matched_name")
    score_column = reviewed.columns.get_loc("matched_score")
    crop_column = reviewed.columns.get_loc(REVIEW_CROP_COLUMN)

    review_positions = [
        position
        for position in range(len(reviewed))
        if reviewed.iat[position, flag_column] in REVIEW_FLAGS
    ]

    if not review_positions:
        print("Name reconciliation complete: no records need manual review.")
        return reviewed

    print(f"Name reconciliation complete: {len(review_positions)} records need review.")
    if dialog is None:
        if not roster:
            raise ValueError("Cannot review flagged OCR names with an empty roster")
        for position in review_positions:
            if not isinstance(reviewed.iat[position, crop_column], np.ndarray):
                raise ValueError(f"Missing image crop for OCR review row {position + 1}")
        root = tk.Tk()
        try:
            _show_review_queue(reviewed, review_positions, roster, parent=root)
            return reviewed
        finally:
            root.destroy()

    for review_number, position in enumerate(review_positions, start=1):
        flag = reviewed.iat[position, flag_column]
        crop = reviewed.iat[position, crop_column]
        if not isinstance(crop, np.ndarray):
            raise ValueError(f"Missing image crop for OCR review row {position + 1}")

        score = reviewed.iat[position, score_column]
        print(f"Reviewing record {review_number} of {len(review_positions)} ({flag}).")
        selection = dialog(
            crop,
            str(flag),
            str(reviewed.iat[position, ocr_column]),
            float(score),
            roster,
            reviewed.iat[position, name_column],
        )
        if selection is None:
            continue
        if selection not in roster:
            raise ValueError(f"Selected name is not present in the roster: {selection}")

        reviewed.iat[position, name_column] = selection
        reviewed.iat[position, flag_column] = RESOLVED_MANUALLY_FLAG

    return reviewed
