import pandas as pd
from pathlib import Path

def export_attendance(df: pd.DataFrame, output_path:Path) -> None:

    df.to_excel(output_path, index=False)

    return None