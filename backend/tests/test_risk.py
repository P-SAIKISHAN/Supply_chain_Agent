from __future__ import annotations


def test_risk_recompute_endpoint(client, auth_headers):
    recompute_response = client.post("/api/v1/risks/recompute", headers=auth_headers)
    assert recompute_response.status_code == 200
    recompute_data = recompute_response.json()
    assert recompute_data["total_scores"] >= 1
    assert recompute_data["corridor_count"] >= 1
    assert recompute_data["supplier_count"] >= 1
    assert recompute_data["shipment_count"] >= 1
    assert recompute_data["refinery_count"] >= 1
    assert 0 <= recompute_data["national_score"] <= 100
    assert recompute_data["national_level"] in {"low", "moderate", "medium", "high", "critical"}

    overview_response = client.get("/api/v1/risks/overview", headers=auth_headers)
    assert overview_response.status_code == 200
    overview_data = overview_response.json()
    assert overview_data["national_level"] in {"low", "moderate", "medium", "high", "critical"}
    assert overview_data["scope_counts"]["corridor"] >= 1
    assert overview_data["scope_counts"]["supplier"] >= 1

    corridor_response = client.get("/api/v1/risks/corridors", headers=auth_headers)
    supplier_response = client.get("/api/v1/risks/suppliers", headers=auth_headers)
    shipment_response = client.get("/api/v1/risks/shipments", headers=auth_headers)
    refinery_response = client.get("/api/v1/risks/refineries", headers=auth_headers)

    assert corridor_response.status_code == 200
    assert supplier_response.status_code == 200
    assert shipment_response.status_code == 200
    assert refinery_response.status_code == 200
    assert len(corridor_response.json()) >= 1
    assert len(supplier_response.json()) >= 1
    assert len(shipment_response.json()) >= 1
    assert len(refinery_response.json()) >= 1
