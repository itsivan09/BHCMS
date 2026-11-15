def test_login_page_loads(client):
    response = client.get("/login")
    assert response.status_code == 200


def test_login_success_redirects(client, seed_users, login_as):
    response = login_as("admin")
    assert response.status_code in (302, 303)


def test_logout_redirects_to_login(client, seed_users, login_as):
    login_as("admin")
    response = client.get("/logout", follow_redirects=False)
    assert response.status_code in (302, 303)
    assert "/login" in response.headers.get("Location", "")
