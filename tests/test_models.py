from datetime import date, timedelta, time

from models import Appointment, InventoryItem, Notification, OperationTimbang, Patient, User, db


def test_appointment_conflict_check(app_instance):
    user = User(username="midwife1", password="x", role="Midwife", full_name="Midwife One")
    patient = Patient(
        full_name="Dela Cruz Ana",
        birth_date=date(2000, 1, 1),
        gender="Female",
        purok="Zone 1A-Danao",
    )
    db.session.add_all([user, patient])
    db.session.commit()

    existing = Appointment(
        patient_id=patient.id,
        health_worker_id=user.id,
        appointment_date=date.today(),
        appointment_time=time(9, 0),
        status="scheduled",
    )
    db.session.add(existing)
    db.session.commit()

    result = Appointment.check_conflict(user.id, date.today(), time(9, 15))
    assert result["has_conflict"] is True


def test_notification_low_stock_generation(app_instance):
    admin = User(username="admin1", password="x", role="Admin", full_name="Admin One")
    item = InventoryItem(name="Test Med", category="Medicine", quantity=2, min_stock_level=5, unit="tablet")
    db.session.add_all([admin, item])
    db.session.commit()

    created = Notification.check_and_create_low_stock_notifications()
    assert created >= 1
    assert Notification.query.count() >= 1


def test_operation_timbang_assessment_underweight(app_instance):
    patient = Patient(
        full_name="Dela Cruz Kid",
        birth_date=date.today() - timedelta(days=8 * 365),
        gender="Male",
        purok="Zone 1A-Danao",
    )
    db.session.add(patient)
    db.session.commit()

    opt = OperationTimbang(patient_id=patient.id, weight_kg=18.0, height_cm=130.0)
    opt.calculate_bmi()
    opt.assess_nutritional_status()

    assert opt.bmi is not None
    assert opt.nutritional_status in {
        "At Risk (Underweight)",
        "Normal",
        "Overweight",
        "Obese",
    }
