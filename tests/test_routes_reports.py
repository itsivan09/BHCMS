from datetime import datetime

from models import Consultation, db


def test_reports_page_and_apis(client, seed_users, login_as, sample_patient):
    login_as("admin")

    consultation = Consultation(
        patient_id=sample_patient.id,
        health_worker_id=seed_users["admin"].id,
        chief_complaint="Cough",
        diagnosis="Common Cold",
        date=datetime.utcnow(),
    )
    db.session.add(consultation)
    db.session.commit()

    page = client.get("/reports")
    assert page.status_code == 200

    morbidity = client.get("/api/morbidity-stats")
    assert morbidity.status_code == 200
    assert morbidity.is_json

    demographics = client.get("/api/demographic-report")
    assert demographics.status_code == 200
    assert demographics.is_json


def test_report_exports(client, seed_users, login_as):
    login_as("admin")

    resp_csv_patients = client.get("/export/patients.csv")
    resp_xlsx_patients = client.get("/export/patients.xlsx")
    resp_csv_inventory = client.get("/export/inventory.csv")
    resp_xlsx_inventory = client.get("/export/inventory.xlsx")

    assert resp_csv_patients.status_code == 200
    assert resp_xlsx_patients.status_code == 200
    assert resp_csv_inventory.status_code == 200
    assert resp_xlsx_inventory.status_code == 200
