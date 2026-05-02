from typing import Any, Dict, List
import math

import numpy as np
import pandas as pd


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    result.columns = [str(column) for column in result.columns]
    return result


def json_safe_value(value: Any) -> Any:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        if math.isnan(float(value)) or math.isinf(float(value)):
            return None
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def dataframe_to_records(df: pd.DataFrame) -> List[Dict[str, Any]]:
    safe_df = df.astype(object).where(pd.notna(df), None)
    records = safe_df.to_dict(orient="records")
    return [
        {str(key): json_safe_value(value) for key, value in record.items()}
        for record in records
    ]
