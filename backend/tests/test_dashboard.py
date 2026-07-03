from __future__ import annotations


def test_dashboard_summary_and_panels(client, auth_headers):
    summary_response = client.get("/api/v1/dashboard/summary", headers=auth_headers)
    assert summary_response.status_code == 200
    summary = summary_response.json()
    kpis = summary["kpis"]
    assert kpis["average_national_risk_score"] >= 0
    assert kpis["active_disruptions_count"] >= 0
    assert kpis["shipments_at_risk_count"] >= 0
    assert kpis["estimated_import_dependency_pct"] >= 0
    assert kpis["strategic_reserve_days_cover"] >= 0

    corridor_response = client.get("/api/v1/dashboard/corridor-risk", headers=auth_headers)
    supplier_response = client.get("/api/v1/dashboard/supplier-risk", headers=auth_headers)
    alerts_response = client.get("/api/v1/dashboard/alerts", headers=auth_headers)
    prices_response = client.get("/api/v1/dashboard/price-trends", headers=auth_headers)
    refinery_response = client.get("/api/v1/dashboard/refinery-stress", headers=auth_headers)
    recommendations_response = client.get("/api/v1/dashboard/recommendations", headers=auth_headers)

    assert corridor_response.status_code == 200
    assert supplier_response.status_code == 200
    assert alerts_response.status_code == 200
    assert prices_response.status_code == 200
    assert refinery_response.status_code == 200
    assert recommendations_response.status_code == 200

    assert len(corridor_response.json()) >= 1
    assert len(supplier_response.json()) >= 1
    assert len(alerts_response.json()) >= 1
    assert len(prices_response.json()) >= 1
    assert len(refinery_response.json()) >= 1
    assert len(recommendations_response.json()) >= 1
