from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from main import build_excel_output, process_pdf_folder


class FakePipeline:
    def run(self, pdf_path: Path) -> pd.DataFrame:
        return pd.DataFrame({"source": [pdf_path.name]})


def test_process_pdf_folder_concatenates_pdf_results_in_filename_order(tmp_path):
    (tmp_path / "b.pdf").touch()
    (tmp_path / "A.PDF").touch()
    (tmp_path / "ignore.txt").touch()

    result = process_pdf_folder(tmp_path, FakePipeline())

    assert result["source"].tolist() == ["A.PDF", "b.pdf"]
    assert result.index.tolist() == [0, 1]


def test_process_pdf_folder_raises_when_folder_has_no_pdfs(tmp_path):
    with pytest.raises(ValueError, match="No PDF files found"):
        process_pdf_folder(tmp_path, FakePipeline())


def test_process_pdf_folder_applies_review_to_each_pdf(tmp_path):
    (tmp_path / "a.pdf").touch()
    (tmp_path / "b.pdf").touch()
    reviewed_files = []

    def review(dataframe):
        reviewed_files.extend(dataframe["source"].tolist())
        dataframe["reviewed"] = True
        return dataframe

    result = process_pdf_folder(tmp_path, FakePipeline(), review_callback=review)

    assert reviewed_files == ["a.pdf", "b.pdf"]
    assert result["reviewed"].tolist() == [True, True]


def test_process_pdf_folder_removes_internal_review_crops(tmp_path):
    (tmp_path / "a.pdf").touch()

    class PipelineWithReviewCrop:
        def run(self, pdf_path: Path) -> pd.DataFrame:
            return pd.DataFrame(
                {"source": [pdf_path.name], "_review_crop": [object()]}
            )

    def review(dataframe):
        assert "_review_crop" in dataframe.columns
        return dataframe

    result = process_pdf_folder(
        tmp_path,
        PipelineWithReviewCrop(),
        review_callback=review,
    )

    assert "_review_crop" not in result.columns


def test_build_excel_output_uses_folder_and_current_date(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    folder_path = tmp_path / "Attendance Batch"

    output_path = build_excel_output(folder_path, date(2026, 10, 2))

    assert output_path == Path("output/Attendance Batch_10-02-2026.xlsx")
    assert output_path.parent.is_dir()
