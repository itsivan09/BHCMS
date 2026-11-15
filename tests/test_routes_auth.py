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


def test_admin_manage_users_page_accessible_by_admin(client, seed_users, login_as):
    login_as("admin")
    response = client.get("/users")
    assert response.status_code == 200
    assert b"Staff &amp; Healthcare Worker Accounts" in response.data or b"Staff & Healthcare Worker Accounts" in response.data


def test_admin_manage_users_forbidden_for_bhw(client, seed_users, login_as):
    login_as("bhw")
    response = client.get("/users", follow_redirects=False)
    assert response.status_code in (302, 303)


def test_admin_create_midwife_account(client, seed_users, login_as):
    from models import User
    login_as("admin")
    response = client.post("/users", data={
        "action": "create",
        "username": "new_midwife",
        "password": "password123",
        "full_name": "Midwife Clara",
        "role": "Midwife",
        "email": "clara@example.com",
        "contact_number": "09123456789"
    }, follow_redirects=True)
    assert response.status_code == 200
    user = User.query.filter_by(username="new_midwife").first()
    assert user is not None
    assert user.role == "Midwife"
    assert user.full_name == "Midwife Clara"


def test_admin_create_bhw_account(client, seed_users, login_as):
    from models import User
    login_as("admin")
    response = client.post("/users", data={
        "action": "create",
        "username": "new_bhw_worker",
        "password": "password123",
        "full_name": "BHW Pedro",
        "role": "BHW",
        "email": "pedro@example.com",
        "contact_number": "09987654321"
    }, follow_redirects=True)
    assert response.status_code == 200
    user = User.query.filter_by(username="new_bhw_worker").first()
    assert user is not None
    assert user.role == "BHW"
