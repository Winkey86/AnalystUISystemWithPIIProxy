from datetime import datetime, timezone
from typing import Dict, List, Optional
import json

from app.artifact_store import ensure_dirs
from app.config import Settings, get_settings
from app.contracts import DatasetMetadata, ToolError


class MetadataRegistry:
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.path = self.settings.artifact_root / "metadata" / "datasets.json"

    def ensure(self) -> None:
        ensure_dirs(self.settings)
        if not self.path.exists():
            self.path.write_text(json.dumps({"datasets": {}}, indent=2), encoding="utf-8")

    def _read(self) -> Dict[str, Dict]:
        self.ensure()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ToolError("Metadata registry is corrupted", status_code=500, code="registry_corrupted") from exc
        datasets = data.get("datasets", {})
        if not isinstance(datasets, dict):
            raise ToolError("Metadata registry has invalid format", status_code=500, code="registry_invalid")
        return datasets

    def _write(self, datasets: Dict[str, Dict]) -> None:
        self.ensure()
        payload = {"datasets": datasets}
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def exists(self, dataset_id: str) -> bool:
        return dataset_id in self._read()

    def get(self, dataset_id: str) -> DatasetMetadata:
        datasets = self._read()
        raw = datasets.get(dataset_id)
        if raw is None:
            raise ToolError(f"Unknown dataset_id: {dataset_id}", status_code=404, code="dataset_not_found")
        return DatasetMetadata(**raw)

    def upsert(self, metadata: DatasetMetadata, overwrite: bool = False) -> None:
        datasets = self._read()
        if metadata.dataset_id in datasets and not overwrite:
            raise ToolError(
                f"Dataset already exists: {metadata.dataset_id}. Use overwrite=true to replace it.",
                status_code=409,
                code="dataset_exists",
            )
        datasets[metadata.dataset_id] = _model_dump(metadata)
        self._write(datasets)

    def list(self) -> List[DatasetMetadata]:
        return [DatasetMetadata(**raw) for raw in self._read().values()]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _model_dump(model):
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()
