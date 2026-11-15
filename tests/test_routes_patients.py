from datetime import date

from models import Patient, db


def test_add_patient_success(client, seed_users, login_as):
    login_as("admin")

    response = client.post(
        "/patients",
        data={
            "full_name": "Dela Cruz Juan",
            "birth_date": "2000-01-01",
            "gender": "Male",
            "purok": "Zone 1A-Danao",
            "address": "Patag",
            "email": "juan@example.com",
            "contact_number": "09171234567",
        },
        follow_redirects=False,
    )

    assert response.status_code in (200, 302, 303)
    assert Patient.query.filter_by(full_name="Dela Cruz Juan").first() is not None


def test_patient_history_api(client, seed_users, login_as, sample_patient):
    login_as("admin")
    response = client.get(f"/api/patient/{sample_patient.id}/history")
    assert response.status_code == 200
    assert response.is_json


def test_update_patient_success(client, seed_users, login_as, sample_patient):
    login_as("admin")
    response = client.post(
        "/patient/update",
        data={
            "patient_id": sample_patient.id,
            "full_name": "Dela Cruz Maria",
            "birth_date": sample_patient.birth_date.isoformat(),
            "gender": "Female",
            "purok": "Zone 1A-Danao",
            "address": "Updated Address",
            "email": "maria.updated@example.com",
            "contact_number": "09170000000",
        },
        follow_redirects=False,
    )
    assert response.status_code in (302, 303)
    db.session.refresh(sample_patient)
    assert sample_patient.address == "Updated Address"
