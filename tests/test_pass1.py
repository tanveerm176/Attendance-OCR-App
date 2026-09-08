# scratch_test_pass1.py — throwaway, not part of the real test suite yet
from pathlib import Path
from ocr_pipeline.config import PipelineConfig
from ocr_pipeline.pipeline import OCRPipeline

config = PipelineConfig(roster=["Cintron, Dylan", "Smith, Jane"])
pipeline = OCRPipeline(config)

df = pipeline.run(Path("fake.pdf"))  # path doesn't need to exist yet — stub ignores it

print(df)
print(df.columns.tolist())
print(df.dtypes)