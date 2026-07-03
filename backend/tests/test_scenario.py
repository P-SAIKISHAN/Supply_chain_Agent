from __future__ import annotations


def test_scenario_create_run_and_results(client, auth_headers):
    create_response = client.post(
        "/api/v1/scenarios",
        headers=auth_headers,
        json={
            "name": "Hormuz partial closure test",
            "scenario_type": "chokepoint_closure",
            "trigger_description": "Simulate a partial closure of the Strait of Hormuz for test coverage.",
            "impacted_corridors": [1],
            "impacted_suppliers": [1],
            "duration_days": 10,
            "disruption_severity_pct": 55,
            "price_shock_pct": 12,
            "tanker_delay_days": 4,
            "reserve_usage_allowed": True,
            "status": "draft",
        },
    )
    assert create_response.status_code == 200
    create_data = create_response.json()
    scenario_id = create_data["id"]
    assert create_data["name"] == "Hormuz partial closure test"
    assert create_data["scenario_type"] == "chokepoint_closure"

    run_response = client.post(
        f"/api/v1/scenarios/{scenario_id}/run",
        headers=auth_headers,
        json={
            "duration_days": 12,
            "disruption_severity_pct": 60,
            "price_shock_pct": 15,
            "tanker_delay_days": 5,
            "reserve_usage_allowed": True,
        },
    )
    assert run_response.status_code == 200
    run_data = run_response.json()
    assert run_data["scenario"]["id"] == scenario_id
    assert run_data["result"]["scenario_id"] == scenario_id
    assert run_data["result"]["estimated_supply_loss_pct"] >= 0
    assert isinstance(run_data["most_affected_refineries"], list)
    assert run_data["mitigation_urgency_level"] in {"low", "moderate", "medium", "high", "critical"}

    results_response = client.get(f"/api/v1/scenarios/{scenario_id}/results", headers=auth_headers)
    assert results_response.status_code == 200
    results_data = results_response.json()
    assert results_data["scenario_id"] == scenario_id
    assert results_data["result"]["scenario_id"] == scenario_id
