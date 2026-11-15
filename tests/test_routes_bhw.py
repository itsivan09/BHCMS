from datetime import date

from models import HouseholdProfile, OperationTimbang


def test_bhw_dashboard_loads(client, seed_users, login_as):
    login_as("bhw")
    response = client.get("/bhw_dashboard")
    assert response.status_code == 200


def test_create_household_profile(client, seed_users, login_as):
    login_as("bhw")
    response = client.post(
        "/household-profile",
        data={
            "household_head_name": "Dela Cruz Juan",
            "purok": "Zone 1A-Danao",
            "address": "Patag",
            "number_of_members": "4",
            "water_source": "Deep well",
            "sanitation_type": "Toilet",
            "electricity": "on",
            "contact_number": "09171234567",
            "notes": "Test household",
        },
        follow_redirects=False,
    )
    assert response.status_code in (302, 303)
    assert HouseholdProfile.query.count() == 1


def test_operation_timbang_create(client, seed_users, login_as):
    login_as("bhw")
    response = client.post(
        "/operation-timbang",
        data={
            "full_name": "Dela Cruz Kid",
            "birth_date": "2015-05-01",
            "gender": "Male",
            "purok": "Zone 1A-Danao",
            "weight": "20",
            "height": "120",
            "notes": "Initial screening",
        },
        follow_redirects=False,
    )
    assert response.status_code in (302, 303)
    assert OperationTimbang.query.count() == 1
