# scratch_test_pass2.py — place at project root, same as scratch_test_pass1.py
import pandas as pd
from pathlib import Path
from ocr_pipeline.config import PipelineConfig
from ocr_pipeline.pipeline import OCRPipeline
import time
# from io.roster_input import build_roster
# Start the timer
start_time = time.perf_counter()
# use your real roster list here — even a few names is enough for a first pass
sonyc_roster = [
    "Aca Hernandez, Kevin",
    "Aca Hernandez, William",
    "Acevedo, Grayson",
    "Agualongo, Matthew",
    "Aguasvivas, Sarah",
    "Akinnubi, Isaac",
    "Alatorre, Vanessa",
    "Almodovar, Emma",
    "Almodovar, Nathan",
    "Alvarez, Rosalinda",
    "Alvarracin, Matthew"
]

config = PipelineConfig(roster=sonyc_roster)
pipeline = OCRPipeline(config)

df = pipeline.run(Path("tests/sample_scans/sonyc-test.pdf"))

pd.set_option('display.max_rows', None)
pd.set_option('display.max_colwidth', None)
print(df)
print()
print(df['flag'].value_counts())

# End the timer
end_time = time.perf_counter()

# Calculate total execution time
execution_time = end_time - start_time
print(f"Execution time: {execution_time:.6f} seconds")