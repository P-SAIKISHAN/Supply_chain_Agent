from __future__ import annotations


def test_register_login_and_me_flow(client):
    register_payload = {
        "full_name": "Asha Verma",
        "email": "asha.verma@example.com",
        "password": "StrongPass123!",
        "role": "procurement",
    }

    register_response = client.post("/api/v1/auth/register", json=register_payload)
    assert register_response.status_code == 201
    register_data = register_response.json()
    assert register_data["token_type"] == "bearer"
    assert register_data["user"]["email"] == register_payload["email"]
    assert register_data["user"]["role"] == "procurement"
    assert register_data["access_token"]

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": register_payload["email"], "password": register_payload["password"]},
    )
    assert login_response.status_code == 200
    login_data = login_response.json()
    assert login_data["token_type"] == "bearer"
    assert login_data["user"]["email"] == register_payload["email"]
    assert login_data["access_token"]

    me_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {login_data['access_token']}"},
    )
    assert me_response.status_code == 200
    me_data = me_response.json()
    assert me_data["email"] == register_payload["email"]
    assert me_data["full_name"] == register_payload["full_name"]
    assert me_data["role"] == "procurement"


def test_duplicate_registration_is_rejected(client):
    payload = {
        "full_name": "Duplicate User",
        "email": "duplicate@example.com",
        "password": "StrongPass123!",
        "role": "analyst",
    }

    first = client.post("/api/v1/auth/register", json=payload)
    second = client.post("/api/v1/auth/register", json=payload)

    assert first.status_code == 201
    assert second.status_code == 400
    assert "already exists" in second.json()["error"]["message"].lower()
