import argparse
import re

from models import db, Patient
from script_utils import run_in_app_context
from utils import is_valid_full_name_format


def normalize_name(value: str) -> str:
    if not value:
        return value
    normalized = re.sub(r"\s*-\s*", " ", value.strip())
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = re.sub(r"\s+\.", ".", normalized)
    return normalized.strip()


def migrate(dry_run: bool = False) -> tuple[int, int, list[tuple[int, str, str]]]:
    updated = 0
    skipped = 0
    skipped_items: list[tuple[int, str, str]] = []

    patients = Patient.query.order_by(Patient.id).all()
    for patient in patients:
        old_name = (patient.full_name or "").strip()
        new_name = normalize_name(old_name)

        if old_name == new_name:
            continue

        if not is_valid_full_name_format(new_name):
            skipped += 1
            skipped_items.append((patient.id, old_name, new_name))
            continue

        updated += 1
        if not dry_run:
            patient.full_name = new_name

    if not dry_run and updated > 0:
        db.session.commit()

    return updated, skipped, skipped_items


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize patient names by removing dash separators.")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change without writing to the database.")
    args = parser.parse_args()

    def run_migration():
        return migrate(dry_run=args.dry_run)

    updated, skipped, skipped_items = run_in_app_context(run_migration)

    mode = "DRY RUN" if args.dry_run else "APPLIED"
    print(f"[{mode}] Patient names updated: {updated}")
    print(f"[{mode}] Patient names skipped: {skipped}")

    if skipped_items:
        print("Skipped records (first 10):")
        for patient_id, old_name, new_name in skipped_items[:10]:
            print(f"- ID {patient_id}: '{old_name}' -> '{new_name}'")


if __name__ == "__main__":
    main()
