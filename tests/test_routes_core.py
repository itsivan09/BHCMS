def test_dashboard_loads_for_logged_in_user(client, seed_users, login_as):
    login_as("admin")
    response = client.get("/")
    assert response.status_code == 200


def test_notifications_page_loads(client, seed_users, login_as):
    login_as("admin")
    response = client.get("/notifications")
    assert response.status_code == 200


def test_search_patients_api_returns_json(client, seed_users, login_as):
    login_as("admin")
    response = client.get("/search_patients?q=none")
    assert response.status_code == 200
    assert response.is_json
