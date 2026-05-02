from pathlib import Path
from typing import Any, Dict, List, Tuple
import json

import pandas as pd


def read_json_dataset(path: Path, options: Dict[str, Any]) -> Tuple[pd.DataFrame, List[str]]:
    encoding = options.get("encoding") or "utf-8-sig"
    with path.open("r", encoding=encoding) as handle:
        data = json.load(handle)

    if isinstance(data, dict) and isinstance(data.get("records"), list):
        records = data["records"]
    elif isinstance(data, list):
        records = data
    else:
        records = [data]

    return pd.json_normalize(records), []
