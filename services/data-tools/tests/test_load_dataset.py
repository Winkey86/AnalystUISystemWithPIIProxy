import pandas as pd

from conftest import load_csv


def test_load_dataset_loads_csv(client, paths):
    response = load_csv(client, paths)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["dataset_id"] == "sales_raw"
    assert body["artifact_uri"] == "artifact://datasets/sales_raw.parquet"
    assert (paths.artifact_root / "datasets" / "sales_raw.parquet").exists()


def test_datasets_returns_registry_entries_and_tool_calls_are_logged(client, paths):
    load_csv(client, paths)

    datasets_response = client.get("/datasets")

    assert datasets_response.status_code == 200
    datasets = datasets_response.json()
    assert datasets[0]["dataset_id"] == "sales_raw"
    assert datasets[0]["artifact_uri"] == "artifact://datasets/sales_raw.parquet"
    log_path = paths.artifact_root / "logs" / "tool_calls.jsonl"
    assert log_path.exists()
    log_text = log_path.read_text(encoding="utf-8")
    assert '"tool_name": "load_dataset"' in log_text
    assert '"tool_name": "list_datasets"' in log_text


def test_load_dataset_loads_xlsx(client, paths):
    source = paths.input_dir / "sales.xlsx"
    pd.DataFrame({"id": [1, 2], "amount": [10, 20]}).to_excel(source, index=False)

    response = client.post(
        "/tools/load_dataset",
        json={
            "source_type": "file",
            "path": str(source),
            "format": "xlsx",
            "dataset_name": "sales_xlsx",
            "options": {"sheet_name": None},
        },
    )

    assert response.status_code == 200
    assert response.json()["schema_summary"] == {"rows": 2, "columns": 2}
    assert (paths.artifact_root / "datasets" / "sales_xlsx.parquet").exists()


def test_load_dataset_loads_json(client, paths):
    source = paths.input_dir / "nested.json"
    source.write_text(
        '[{"id": 1, "customer": {"email": "a@example.com"}}, {"id": 2, "customer": {"email": "b@example.com"}}]',
        encoding="utf-8",
    )

    response = client.post(
        "/tools/load_dataset",
        json={"source_type": "file", "path": str(source), "format": "json", "dataset_name": "nested_json"},
    )

    assert response.status_code == 200
    schema = client.post("/tools/inspect_schema", json={"dataset_id": "nested_json"}).json()
    assert "customer.email" in {column["name"] for column in schema["columns"]}


def test_load_dataset_loads_parquet(client, paths):
    source = paths.input_dir / "source.parquet"
    pd.DataFrame({"id": [1, 2], "amount": [10, 20]}).to_parquet(source, index=False)

    response = client.post(
        "/tools/load_dataset",
        json={"source_type": "file", "path": str(source), "format": "parquet", "dataset_name": "source_parquet"},
    )

    assert response.status_code == 200
    assert response.json()["schema_summary"] == {"rows": 2, "columns": 2}


def test_load_dataset_blocks_duplicate_dataset_id_when_overwrite_false(client, paths):
    first = load_csv(client, paths, dataset_name="duplicate")
    second = load_csv(client, paths, dataset_name="duplicate")

    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["code"] == "dataset_exists"
