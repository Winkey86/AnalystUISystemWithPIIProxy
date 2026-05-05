from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import openpyxl

from config import settings


def _safe_upload_path(filename: str) -> Path:
    base = Path(settings.uploads_dir)
    base.mkdir(parents=True, exist_ok=True)
    p = (base / filename).resolve()
    if not str(p).startswith(str(base.resolve())):
        raise ValueError("Path traversal not allowed")
    return p


def register(mcp: Any, audited: Callable) -> None:
    @mcp.tool()
    @audited
    def excel_sheet_list(filename: str) -> dict[str, Any]:
        """Список листов в Excel-файле из директории uploads.

        Args:
            filename: Имя файла (только имя, без пути), расположенного в /data/uploads/.
        """
        p = _safe_upload_path(filename)
        if not p.exists():
            return {"error": f"File not found: {filename}"}
        wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
        sheets = wb.sheetnames
        wb.close()
        return {"filename": filename, "sheets": sheets}

    @mcp.tool()
    @audited
    def excel_preview(filename: str, sheet: str, n: int = 10) -> dict[str, Any]:
        """Просмотр первых N строк листа Excel.

        Args:
            filename: Имя файла в /data/uploads/.
            sheet: Название листа.
            n: Количество строк (max 100).
        """
        import pandas as pd

        n = min(n, settings.max_rows_preview)
        p = _safe_upload_path(filename)
        if not p.exists():
            return {"error": f"File not found: {filename}"}
        df = pd.read_excel(p, sheet_name=sheet, nrows=n, engine="openpyxl")
        return {
            "filename": filename,
            "sheet": sheet,
            "rows": df.to_dict(orient="records"),
            "columns": list(df.columns),
        }
