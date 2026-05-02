from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd

from app.contracts import ToolError


AUTO_ENCODINGS = ("utf-8", "utf-8-sig", "cp1251", "latin1")


def read_csv_dataset(path: Path, options: Dict[str, Any]) -> Tuple[pd.DataFrame, List[str]]:
    delimiter = options.get("delimiter", "auto")
    encoding_option = options.get("encoding", "auto")
    encodings = AUTO_ENCODINGS if encoding_option in (None, "", "auto") else (str(encoding_option),)

    errors: List[str] = []
    for encoding in encodings:
        try:
            read_kwargs: Dict[str, Any] = {"encoding": encoding}
            if delimiter in (None, "", "auto"):
                read_kwargs.update({"sep": None, "engine": "python"})
            else:
                read_kwargs["sep"] = delimiter
            df = pd.read_csv(path, **read_kwargs)
            warnings = []
            if encoding_option in (None, "", "auto"):
                warnings.append(f"csv_encoding={encoding}")
            return df, warnings
        except (UnicodeDecodeError, LookupError, pd.errors.ParserError) as exc:
            errors.append(f"{encoding}: {exc}")
            continue

    raise ToolError(
        f"Could not read CSV file with configured encoding fallback: {'; '.join(errors)}",
        status_code=400,
        code="csv_read_failed",
    )
