from conftest import load_csv


def test_profile_quality_finds_nulls(client, paths):
    load_csv(client, paths, dataset_name="quality_nulls", rows=[
        {"id": 1, "amount": 10, "constant": "x"},
        {"id": 2, "amount": None, "constant": "x"},
    ])

    response = client.post("/tools/profile_quality", json={"dataset_id": "quality_nulls"})

    issues = response.json()["issues"]
    assert response.status_code == 200
    assert any(issue["issue"] == "nulls" and issue["column"] == "amount" for issue in issues)


def test_profile_quality_finds_duplicates(client, paths):
    load_csv(client, paths, dataset_name="quality_dupes", rows=[
        {"id": 1, "amount": 10},
        {"id": 1, "amount": 10},
    ])

    response = client.post("/tools/profile_quality", json={"dataset_id": "quality_dupes"})

    issues = response.json()["issues"]
    assert any(issue["issue"] == "duplicate_rows" for issue in issues)


def test_profile_quality_finds_empty_columns(client, paths):
    load_csv(client, paths, dataset_name="quality_empty", rows=[
        {"id": 1, "empty_col": None},
        {"id": 2, "empty_col": None},
    ])

    response = client.post("/tools/profile_quality", json={"dataset_id": "quality_empty"})

    issues = response.json()["issues"]
    assert any(issue["issue"] == "empty_column" and issue["column"] == "empty_col" for issue in issues)


def test_profile_quality_finds_constant_columns(client, paths):
    load_csv(client, paths, dataset_name="quality_constant", rows=[
        {"id": 1, "constant_col": "same"},
        {"id": 2, "constant_col": "same"},
    ])

    response = client.post("/tools/profile_quality", json={"dataset_id": "quality_constant"})

    issues = response.json()["issues"]
    assert any(issue["issue"] == "constant_column" and issue["column"] == "constant_col" for issue in issues)
