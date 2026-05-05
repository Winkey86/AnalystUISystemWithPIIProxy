from pathlib import Path


def test_load_dataset_forbids_path_traversal(client, paths):
    outside = paths.input_dir.parent / "outside.csv"
    outside.write_text("id\n1\n", encoding="utf-8")

    response = client.post(
        "/tools/load_dataset",
        json={
            "source_type": "file",
            "path": "../outside.csv",
            "format": "csv",
            "dataset_name": "outside",
        },
    )

    assert response.status_code == 400
    assert response.json()["code"] == "path_outside_input_dir"


def test_load_dataset_forbids_absolute_path_outside_input_dir(client, paths, tmp_path):
    outside_dir = tmp_path / "elsewhere"
    outside_dir.mkdir()
    outside = outside_dir / "outside.csv"
    outside.write_text("id\n1\n", encoding="utf-8")

    response = client.post(
        "/tools/load_dataset",
        json={
            "source_type": "file",
            "path": str(Path(outside).resolve()),
            "format": "csv",
            "dataset_name": "outside_abs",
        },
    )

    assert response.status_code == 400
    assert response.json()["code"] == "path_outside_input_dir"
