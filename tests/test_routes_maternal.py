from datetime import date, timedelta

from models import ImmunizationSchedule, InventoryItem, PrenatalRecord, db


def test_prenatal_enroll(client, seed_users, login_as, sample_patient):
    login_as("midwife")

    response = client.post(
        "/prenatal/enroll",
        data={
            "patient_id": str(sample_patient.id),
            "lmp": (date.today() - timedelta(days=70)).isoformat(),
            "gravida": "1",
            "para": "0",
        },
        follow_redirects=False,
    )

    assert response.status_code in (302, 303)
    assert PrenatalRecord.query.filter_by(patient_id=sample_patient.id, is_active=True).first() is not None


def test_immunization_schedule_and_complete(client, seed_users, login_as, sample_patient):
    login_as("midwife")

    vaccine_stock = InventoryItem(
        name="BCG Vaccine",
        category="Vaccine",
        quantity=5,
        min_stock_level=1,
        unit="dose",
    )
    db.session.add(vaccine_stock)
    db.session.commit()

    create_resp = client.post(
        "/immunization_schedule",
        data={
            "patient_id": str(sample_patient.id),
            "vaccine_name": "BCG",
            "dose_number": "1",
            "scheduled_date": (date.today() + timedelta(days=1)).isoformat(),
            "notes": "First dose",
        },
        follow_redirects=False,
    )
    assert create_resp.status_code in (302, 303)

    sched = ImmunizationSchedule.query.filter_by(patient_id=sample_patient.id, vaccine_name="BCG").first()
    assert sched is not None

    complete_resp = client.post(f"/immunization/{sched.id}/complete", follow_redirects=False)
    assert complete_resp.status_code in (302, 303)

    db.session.refresh(sched)
    assert sched.is_completed is True


def test_midwife_dashboard_skips_broken_prenatal_rows(client, seed_users, login_as, sample_patient, monkeypatch):
    login_as("midwife")

    sample_patient.is_pregnant = True
    db.session.add(sample_patient)
    db.session.commit()

    record = PrenatalRecord(
        patient_id=sample_patient.id,
        weeks_of_pregnancy=10,
        estimated_delivery_date=date.today() + timedelta(days=200),
        gravidity=1,
        parity=0,
        is_active=True,
    )
    db.session.add(record)
    db.session.commit()

    def _raise_days_error(self):
        raise ValueError("bad prenatal record")

    monkeypatch.setattr(PrenatalRecord, "days_until_delivery", _raise_days_error)

    response = client.get("/midwife_dashboard")

    assert response.status_code == 200
