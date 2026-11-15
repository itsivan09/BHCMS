from datetime import date, timedelta

from models import Appointment, db


def test_book_appointment(client, seed_users, login_as, sample_patient):
    login_as("admin")

    response = client.post(
        "/appointment/book",
        data={
            "patient_name": sample_patient.full_name,
            "worker_name": seed_users["midwife"].full_name,
            "reason": "Routine checkup",
            "appointment_date": (date.today() + timedelta(days=1)).isoformat(),
            "appointment_time": "09:30",
            "contact_number": "09171234567",
            "email": sample_patient.email,
        },
        follow_redirects=False,
    )

    assert response.status_code in (302, 303)
    assert Appointment.query.count() == 1


def test_check_appointment_availability(client, seed_users, login_as):
    login_as("admin")
    response = client.get(
        "/appointment/check-availability",
        query_string={
            "worker_name": seed_users["midwife"].full_name,
            "date": (date.today() + timedelta(days=1)).isoformat(),
            "time": "10:00",
        },
    )
    assert response.status_code == 200
    assert response.is_json


def test_cancel_and_complete_appointment(client, seed_users, login_as, sample_patient):
    login_as("admin")

    appt = Appointment(
        patient_id=sample_patient.id,
        health_worker_id=seed_users["midwife"].id,
        appointment_date=date.today() + timedelta(days=1),
        appointment_time=__import__("datetime").time(11, 0),
        status="scheduled",
    )
    db.session.add(appt)
    db.session.commit()

    cancel_resp = client.post(f"/appointment/{appt.id}/cancel", follow_redirects=False)
    assert cancel_resp.status_code in (302, 303)

    appt.status = "scheduled"
    db.session.commit()

    complete_resp = client.post(f"/appointment/{appt.id}/complete", follow_redirects=False)
    assert complete_resp.status_code in (302, 303)
