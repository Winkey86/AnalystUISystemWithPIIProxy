from conftest import load_csv


def test_safe_sql_preview_allows_select(client, paths):
    load_csv(client, paths)

    response = client.post(
        "/tools/safe_sql_preview",
        json={"dataset_id": "sales_raw", "sql": "select category, sum(amount) as revenue from sales_raw group by category"},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "ok"
    assert body["is_read_only"] is True


def test_safe_sql_preview_allows_with_select(client, paths):
    load_csv(client, paths)

    response = client.post(
        "/tools/safe_sql_preview",
        json={"dataset_id": "sales_raw", "sql": "WITH q AS (SELECT * FROM sales_raw) SELECT count(*) AS c FROM q"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_safe_sql_preview_blocks_dangerous_operations(client, paths):
    load_csv(client, paths)
    cases = {
        "ALTER": "ALTER TABLE sales_raw ADD COLUMN x INT",
        "ATTACH": "ATTACH 'x.duckdb' AS x",
        "COPY": "COPY sales_raw TO 'x.csv'",
        "CREATE": "CREATE TABLE x AS SELECT * FROM sales_raw",
        "DELETE": "DELETE FROM sales_raw",
        "DETACH": "DETACH x",
        "DROP": "DROP TABLE sales_raw",
        "INSERT": "INSERT INTO sales_raw VALUES (1)",
        "INSTALL": "INSTALL httpfs",
        "LOAD": "LOAD httpfs",
        "PRAGMA": "PRAGMA show_tables",
        "REPLACE": "REPLACE INTO sales_raw VALUES (1)",
        "TRUNCATE": "TRUNCATE TABLE sales_raw",
        "UPDATE": "UPDATE sales_raw SET amount = 1",
    }

    for operation, sql in cases.items():
        response = client.post(
            "/tools/safe_sql_preview",
            json={"dataset_id": "sales_raw", "sql": sql},
        )

        body = response.json()
        assert response.status_code == 200
        assert body["status"] == "blocked"
        assert operation in body["blocked_operations"]


def test_safe_sql_preview_blocks_multiple_statements(client, paths):
    load_csv(client, paths)

    response = client.post(
        "/tools/safe_sql_preview",
        json={"dataset_id": "sales_raw", "sql": "SELECT * FROM sales_raw; SELECT 1"},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "blocked"
    assert "MULTIPLE_STATEMENTS" in body["blocked_operations"]


def test_safe_sql_preview_handles_comments_and_mixed_case(client, paths):
    load_csv(client, paths)

    response = client.post(
        "/tools/safe_sql_preview",
        json={"dataset_id": "sales_raw", "sql": "-- harmless\nSeLeCt * FrOm sales_raw"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_safe_sql_preview_ignores_blocked_words_in_comments_and_strings(client, paths):
    load_csv(client, paths)

    response = client.post(
        "/tools/safe_sql_preview",
        json={"dataset_id": "sales_raw", "sql": "SELECT 'DROP' AS word FROM sales_raw -- DELETE ignored"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_safe_sql_query_executes_select_and_saves_result_artifact(client, paths):
    load_csv(client, paths)

    response = client.post(
        "/tools/safe_sql_query",
        json={
            "dataset_id": "sales_raw",
            "sql": "SELECT category, SUM(amount) AS revenue FROM sales_raw GROUP BY category ORDER BY revenue DESC",
            "limit": 10,
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "ok"
    assert body["result_artifact_uri"].startswith("artifact://query_results/")
    assert body["rows_returned"] == 2
    assert list((paths.artifact_root / "query_results").glob("*.parquet"))


def test_safe_sql_query_does_not_return_more_than_max_query_rows(client, paths):
    rows = [{"id": i, "customer_email": f"user{i}@example.com", "amount": i, "category": "A"} for i in range(10)]
    load_csv(client, paths, dataset_name="many_rows", rows=rows)

    response = client.post(
        "/tools/safe_sql_query",
        json={"dataset_id": "many_rows", "sql": "SELECT * FROM many_rows", "limit": 100},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["rows_returned"] == 5
    assert len(body["preview"]) <= 3
