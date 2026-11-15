import argparse
import statistics
import time
from collections import OrderedDict
from datetime import date, datetime, timedelta
from typing import Callable

from sqlalchemy import text

from app import app
from models import db, Consultation, ImmunizationSchedule, Notification, Patient, PrenatalRecord


DEFAULT_WARMUP = 3
DEFAULT_RUNS = 25


def ms(seconds: float) -> float:
    return round(seconds * 1000.0, 2)


def _percentile_95(samples: list[float]) -> float:
    if len(samples) >= 20:
        return statistics.quantiles(samples, n=20)[18]
    return max(samples)


def timed_runs(label: str, fn: Callable[[], object], warmup: int, runs: int) -> None:
    for _ in range(warmup):
        fn()

    samples: list[float] = []
    for _ in range(runs):
        start = time.perf_counter()
        fn()
        end = time.perf_counter()
        samples.append(end - start)

    avg = statistics.mean(samples)
    p95 = _percentile_95(samples)
    minimum = min(samples)
    maximum = max(samples)

    print(f"{label:<45} avg={ms(avg):>8.2f}ms  p95={ms(p95):>8.2f}ms  min={ms(minimum):>8.2f}ms  max={ms(maximum):>8.2f}ms")


def benchmark_dashboard_like_queries(warmup: int, runs: int) -> None:
    today = date.today()
    today_start = datetime.combine(today, datetime.min.time())
    tomorrow_start = today_start + timedelta(days=1)
    patient_id = Patient.query.with_entities(Patient.id).order_by(Patient.id.asc()).limit(1).scalar()

    def q_upcoming_vaccines():
        return ImmunizationSchedule.query.filter(
            ImmunizationSchedule.scheduled_date.between(today, today + timedelta(days=7)),
            ImmunizationSchedule.is_completed.is_(False),
        ).all()

    def q_overdue_vaccines():
        return ImmunizationSchedule.query.filter(
            ImmunizationSchedule.scheduled_date < today,
            ImmunizationSchedule.is_completed.is_(False),
        ).all()

    def q_auto_notify_duplicate_check():
        return {
            row[0]
            for row in Notification.query.with_entities(Notification.related_item_id)
            .filter(
                Notification.type == "appointment",
                Notification.related_item_type == "immunization",
                Notification.created_at >= today_start,
                Notification.created_at < tomorrow_start,
                Notification.related_item_id.isnot(None),
            )
            .all()
        }

    def q_prenatal_active_delivery():
        return PrenatalRecord.query.filter_by(is_active=True).order_by(PrenatalRecord.estimated_delivery_date.asc()).all()

    def q_consultation_patient_date():
        if not patient_id:
            return []
        return Consultation.query.filter_by(patient_id=patient_id).order_by(Consultation.date.desc()).limit(30).all()

    benchmark_queries = OrderedDict([
        ("Upcoming vaccines (7-day window)", q_upcoming_vaccines),
        ("Overdue vaccines", q_overdue_vaccines),
        ("Notification duplicate check (today)", q_auto_notify_duplicate_check),
        ("Prenatal active ordered by EDD", q_prenatal_active_delivery),
        ("Recent consultations by patient", q_consultation_patient_date),
    ])

    print("\n=== Benchmark: Dashboard-like ORM Queries ===")
    for label, query_fn in benchmark_queries.items():
        timed_runs(label, query_fn, warmup, runs)


def benchmark_index_health() -> None:
    expected_indexes = [
        ("consultation", "ix_consultation_patient_date"),
        ("consultation", "ix_consultation_worker_date"),
        ("operation_timbang", "ix_opt_patient_measurement_date"),
        ("operation_timbang", "ix_opt_followup_measurement_date"),
        ("prenatal_record", "ix_prenatal_patient_active"),
        ("prenatal_record", "ix_prenatal_active_delivery"),
        ("immunization_schedule", "ix_immunization_completed_scheduled"),
        ("immunization_schedule", "ix_immunization_patient_completed"),
        ("notification", "ix_notification_user_read_created"),
        ("notification", "ix_notification_related_type_created"),
        ("appointment", "ix_appointment_worker_date_time_status"),
        ("appointment", "ix_appointment_date_status"),
    ]

    print("\n=== Index Presence Check (MySQL) ===")
    found = 0
    for table_name, index_name in expected_indexes:
        row = db.session.execute(
            text(
                """
                SELECT COUNT(*)
                FROM information_schema.statistics
                WHERE table_schema = DATABASE()
                  AND table_name = :table_name
                  AND index_name = :index_name
                """
            ),
            {"table_name": table_name, "index_name": index_name},
        ).scalar()
        ok = (row or 0) > 0
        status = "OK" if ok else "MISSING"
        print(f"{table_name:<22} {index_name:<40} {status}")
        if ok:
            found += 1

    print(f"\nIndexes found: {found}/{len(expected_indexes)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark key BHCMS database query paths.")
    parser.add_argument("--warmup", type=int, default=DEFAULT_WARMUP, help=f"Warmup runs per query (default: {DEFAULT_WARMUP})")
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS, help=f"Measured runs per query (default: {DEFAULT_RUNS})")
    args = parser.parse_args()

    with app.app_context():
        benchmark_index_health()
        benchmark_dashboard_like_queries(args.warmup, args.runs)

    print("\nDone. Re-run this script after any DB/index changes and compare avg/p95.")


if __name__ == "__main__":
    main()
