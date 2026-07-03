from __future__ import annotations


def _create_and_run_scenario(client, auth_headers):
    create_response = client.post(
        "/api/v1/scenarios",
        headers=auth_headers,
        json={
            "name": "Procurement scenario",
            "scenario_type": "sanctions_escalation",
            "trigger_description": "Create a scenario to validate procurement recommendations.",
            "impacted_corridors": [2],
            "impacted_suppliers": [4],
            "duration_days": 14,
            "disruption_severity_pct": 48,
            "price_shock_pct": 10,
            "tanker_delay_days": 3,
            "reserve_usage_allowed": True,
            "status": "draft",
        },
    )
    assert create_response.status_code == 200
    scenario_id = create_response.json()["id"]

    run_response = client.post(
        f"/api/v1/scenarios/{scenario_id}/run",
        headers=auth_headers,
        json={"duration_days": 14, "disruption_severity_pct": 50, "price_shock_pct": 11},
    )
    assert run_response.status_code == 200
    return scenario_id


def test_procurement_recommendation_generation(client, auth_headers):
    scenario_id = _create_and_run_scenario(client, auth_headers)

    recommend_response = client.post(
        "/api/v1/procurement/recommend",
        headers=auth_headers,
        json={
            "target_scope": "scenario",
            "scenario_id": scenario_id,
            "top_n": 3,
            "candidate_suppliers_limit": 4,
            "candidate_corridors_limit": 3,
        },
    )
    assert recommend_response.status_code == 200
    recommend_data = recommend_response.json()
    assert recommend_data["target_scope"] == "scenario"
    assert recommend_data["scenario_id"] == scenario_id
    assert recommend_data["generated_count"] == 3
    assert len(recommend_data["recommendations"]) == 3

    top_option = recommend_data["recommendations"][0]
    assert top_option["recommended_supplier"]
    assert top_option["recommended_route"]
    assert 0 <= top_option["overall_score"] <= 100
    assert top_option["action_priority"] in {"low", "medium", "high", "critical"}

    list_response = client.get(
        "/api/v1/procurement/recommendations",
        headers=auth_headers,
        params={"scenario_id": scenario_id},
    )
    assert list_response.status_code == 200
    list_data = list_response.json()
    assert list_data["total_count"] >= 3
    assert len(list_data["items"]) >= 3

    recommendation_id = list_data["items"][0]["id"]
    detail_response = client.get(
        f"/api/v1/procurement/recommendations/{recommendation_id}",
        headers=auth_headers,
    )
    assert detail_response.status_code == 200
    detail_data = detail_response.json()
    assert detail_data["id"] == recommendation_id
    assert detail_data["recommended_supplier"]
