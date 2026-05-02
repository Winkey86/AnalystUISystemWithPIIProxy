from conftest import load_csv


def test_preview_dataset_respects_limit(client, paths):
    load_csv(client, paths)

    response = client.post(
        "/tools/preview_dataset",
        json={"dataset_id": "sales_raw", "mode": "head", "limit": 10, "mask_pii": False},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["rows_returned"] == 3
    assert len(body["preview"]) == 3
    assert body["warnings"]


def test_preview_dataset_masks_pii(client, paths):
    load_csv(client, paths)

    response = client.post(
        "/tools/preview_dataset",
        json={"dataset_id": "sales_raw", "mode": "head", "limit": 2, "mask_pii": True},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["pii_detected"] is True
    assert body["preview"][0]["customer_email"] == "[EMAIL]"
