from conftest import load_csv


def test_inspect_schema_returns_columns(client, paths):
    load_csv(client, paths)

    response = client.post(
        "/tools/inspect_schema",
        json={"dataset_id": "sales_raw", "include_examples": True, "max_examples_per_column": 2},
    )

    assert response.status_code == 200
    columns = response.json()["columns"]
    assert {column["name"] for column in columns} >= {"id", "amount", "customer_email"}


def test_inspect_schema_returns_pii_hint(client, paths):
    load_csv(client, paths)

    response = client.post(
        "/tools/inspect_schema",
        json={"dataset_id": "sales_raw", "include_examples": False, "max_examples_per_column": 0},
    )

    email_column = next(column for column in response.json()["columns"] if column["name"] == "customer_email")
    assert email_column["pii_hint"] is True
