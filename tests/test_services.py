from types import SimpleNamespace

from services.export_service import build_inventory_rows, build_patients_rows, rows_to_csv_bytes, rows_to_xlsx_bytes
from services.reporting_service import build_demographic_payload, build_morbidity_payload


def test_build_morbidity_payload_returns_sorted_counts():
    consultations = [
        SimpleNamespace(diagnosis="Flu"),
        SimpleNamespace(diagnosis="Flu"),
        SimpleNamespace(diagnosis="Cough"),
    ]
    payload = build_morbidity_payload(consultations)
    assert payload["total_consultations"] == 3
    assert payload["labels"][0] == "Flu"
    assert payload["datasets"][0]["data"][0] == 2


def test_build_demographic_payload_contains_expected_keys():
    patients = [
        SimpleNamespace(birth_date=__import__("datetime").date(2020, 1, 1), gender="Male", purok="Zone 1"),
        SimpleNamespace(birth_date=__import__("datetime").date(1990, 1, 1), gender="Female", purok="Zone 2"),
    ]
    payload = build_demographic_payload(patients, pregnant_patients_count=1)
    assert payload["total_patients"] == 2
    assert payload["pregnant_patients"] == 1
    assert "gender_distribution" in payload


def test_export_helpers_produce_bytes():
    now = __import__("datetime").datetime.now()
    patients = [
        SimpleNamespace(
            id=1,
            full_name="Dela Cruz Maria",
            birth_date=__import__("datetime").date(1995, 5, 20),
            age=30,
            gender="Female",
            purok="Zone 1",
            address="Patag",
            contact_number="09171234567",
            is_pregnant=False,
            created_at=now,
        )
    ]
    items = [
        SimpleNamespace(
            id=1,
            name="Paracetamol",
            category="Medicine",
            quantity=10,
            unit="tablet",
            min_stock_level=5,
            expiry_date=None,
            price_per_unit=2.0,
            is_expired=False,
            is_low_stock=False,
            created_at=now,
        )
    ]

    patient_rows = build_patients_rows(patients)
    inventory_rows = build_inventory_rows(items)

    assert rows_to_csv_bytes(patient_rows).getvalue().startswith(b"ID")
    assert len(rows_to_xlsx_bytes("Patients", patient_rows).getvalue()) > 0
    assert len(rows_to_xlsx_bytes("Inventory", inventory_rows).getvalue()) > 0
