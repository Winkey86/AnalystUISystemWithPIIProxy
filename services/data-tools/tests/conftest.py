from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient


@dataclass(frozen=True)
class TestPaths:
    input_dir: Path
    artifact_root: Path


@pytest.fixture()
def paths(tmp_path, monkeypatch) -> TestPaths:
    input_dir = tmp_path / "input"
    artifact_root = tmp_path / "artifacts"
    input_dir.mkdir()
    artifact_root.mkdir()
    monkeypatch.setenv("DATA_INPUT_DIR", str(input_dir))
    monkeypatch.setenv("ARTIFACT_ROOT", str(artifact_root))
    monkeypatch.setenv("MAX_PREVIEW_ROWS", "3")
    monkeypatch.setenv("MAX_QUERY_ROWS", "5")
    monkeypatch.setenv("QUERY_TIMEOUT_SECONDS", "10")
    monkeypatch.setenv("MAX_FILE_SIZE_MB", "100")
    return TestPaths(input_dir=input_dir, artifact_root=artifact_root)


@pytest.fixture()
def client(paths):
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


def write_csv(path: Path, rows=None) -> Path:
    rows = rows or [
        {"id": 1, "customer_email": "a@example.com", "amount": 10, "category": "A"},
        {"id": 2, "customer_email": "b@example.com", "amount": 20, "category": "B"},
        {"id": 3, "customer_email": "c@example.com", "amount": 30, "category": "A"},
        {"id": 4, "customer_email": "d@example.com", "amount": 40, "category": "B"},
    ]
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def load_csv(client, paths: TestPaths, dataset_name: str = "sales_raw", rows=None):
    source = write_csv(paths.input_dir / f"{dataset_name}.csv", rows=rows)
    return client.post(
        "/tools/load_dataset",
        json={
            "source_type": "file",
            "path": str(source),
            "format": "csv",
            "dataset_name": dataset_name,
            "options": {"delimiter": "auto", "encoding": "auto"},
        },
    )
