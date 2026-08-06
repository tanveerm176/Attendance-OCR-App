import os

DPI = int(os.getenv("DPI", 300))
BUCKET_NAME = os.getenv("S3_BUCKET", None)   # None = local mode
OUTPUT_DIR  = os.getenv("OUTPUT_DIR", "./output")