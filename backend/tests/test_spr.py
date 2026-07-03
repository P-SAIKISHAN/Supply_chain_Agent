from __future__ import annotations


def _create_and_run_scenario(client, auth_headers):
    create_response = client.post(
        "/api/v1/scenarios",
        headers=auth_headers,
        json={
            "name": "SPR optimization scenario",
            "scenario_type": "route_disruption",
            "trigger_description": "Create a scenario to validate SPR optimization.",
            "impacted_corridors": [1, 2],
            "impacted_suppliers": [1, 4],
            "duration_days": 18,
            "disruption_severity_pct": 58,
            "price_shock_pct": 14,
            "tanker_delay_days": 6,
            "reserve_usage_allowed": True,
            "status": "draft",
        },
    )
    assert create_response.status_code == 200
    scenario_id = create_response.json()["id"]

    run_response = client.post(
        f"/api/v1/scenarios/{scenario_id}/run",
        headers=auth_headers,
        json={"duration_days": 18, "disruption_severity_pct": 58, "price_shock_pct": 14, "tanker_delay_days": 6},
    )
    assert run_response.status_code == 200
    return scenario_id


def test_spr_optimization_flow(client, auth_headers):
    scenario_id = _create_and_run_scenario(client, auth_headers)

    optimize_response = client.post(
        "/api/v1/spr/optimize",
        headers=auth_headers,
        json={
            "target_scope": "scenario",
            "scenario_id": scenario_id,
            "current_reserve_days_cover": 30,
            "import_recovery_days": 21,
            "replenishment_window_days": 45,
            "reserve_usage_allowed": True,
        },
    )
    assert optimize_response.status_code == 200
    optimize_data = optimize_response.json()
    plan = optimize_data["plan"]
    assert plan["scenario_id"] == scenario_id
    assert plan["total_drawdown_bbl"] >= 0
    assert plan["drawdown_days"] >= 0
    assert isinstance(plan["daily_release_schedule"], dict)
    assert isinstance(optimize_data["refinery_allocation_suggestion"], list)
    assert isinstance(optimize_data["replenishment_strategy"], dict)
    assert isinstance(optimize_data["risk_notes"], list)

    plans_response = client.get(
        "/api/v1/spr/plans",
        headers=auth_headers,
        params={"scenario_id": scenario_id},
    )
    assert plans_response.status_code == 200
    plans_data = plans_response.json()
    assert plans_data["total_count"] >= 1
    assert plans_data["limit"] >= 1
    assert plans_data["offset"] == 0
    assert plans_data["page"] == 1
    assert plans_data["pages"] >= 1
    assert len(plans_data["items"]) >= 1

    plan_id = plans_data["items"][0]["id"]
    detail_response = client.get(f"/api/v1/spr/plans/{plan_id}", headers=auth_headers)
    assert detail_response.status_code == 200
    detail_data = detail_response.json()
    assert detail_data["id"] == plan_id
    assert detail_data["total_drawdown_bbl"] >= 0
