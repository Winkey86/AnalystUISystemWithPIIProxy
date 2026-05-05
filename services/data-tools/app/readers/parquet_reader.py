from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd


def read_parquet_dataset(path: Path, options: Dict[str, Any]) -> Tuple[pd.DataFrame, List[str]]:
    return pd.read_parquet(path), []
