from models import Consultation


def test_add_consultation_and_view_history(client, seed_users, login_as, sample_patient):
    login_as("midwife")

    response = client.post(
        f"/patient/{sample_patient.id}/consultation/add",
        data={
            "chief_complaint": "Headache",
            "diagnosis": "Migraine",
            "consultation_type": "General",
            "notes": "Rest and hydration",
            "temperature": "36.8",
            "blood_pressure_systolic": "120",
            "blood_pressure_diastolic": "80",
        },
        follow_redirects=False,
    )
    assert response.status_code in (302, 303)
    assert Consultation.query.filter_by(patient_id=sample_patient.id).count() == 1

    history = client.get(f"/patient/{sample_patient.id}/consultations")
    assert history.status_code == 200
