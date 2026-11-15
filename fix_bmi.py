from app import db
from models import OperationTimbang
from script_utils import run_in_app_context

def recalculate_all_bmi() -> int:
    records = OperationTimbang.query.all()
    print(f"Found {len(records)} records to check...")

    count = 0
    for record in records:
        old_bmi = record.bmi
        
        # This calls your CORRECT logic in models.py
        # It converts cm -> m and updates self.bmi
        new_bmi = record.calculate_bmi()
        
        # Update the status (Normal/Underweight/etc) based on the new BMI
        record.assess_nutritional_status()
        
        print(f"ID {record.id}: Old BMI {old_bmi} -> New BMI {new_bmi}")
        count += 1

    db.session.commit()
    print("------------------------------------------------")
    print(f"Success! Updated {count} records.")
    return count


def main() -> None:
    run_in_app_context(recalculate_all_bmi)


if __name__ == "__main__":
    main()