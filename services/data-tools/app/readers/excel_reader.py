from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd


def read_excel_dataset(path: Path, options: Dict[str, Any]) -> Tuple[pd.DataFrame, List[str]]:
    sheet_name = options.get("sheet_name")
    if sheet_name is None:
        sheet_name = 0
    df = pd.read_excel(path, sheet_name=sheet_name, engine="openpyxl")
    return df, []
