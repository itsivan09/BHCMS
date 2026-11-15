from app import db
from models import Patient, HouseholdProfile
from script_utils import run_in_app_context

# CONFIGURATION: Map the OLD name to the NEW name here
# Format: 'Old Name': 'New Name'
ZONE_MAPPING = {
    'Zone-1A Danao': 'Zone 1',
    'Zone-1B Mother Of Devine Mercy Village': 'Zone 1B',
    'Zone-2 Danao': 'Zone 2',
    # Add all your changes here...
}

def update_zones():
    print("--- Starting Zone Update ---")
    
    print("Updating Patients...")
    for old_name, new_name in ZONE_MAPPING.items():
        count = Patient.query.filter_by(purok=old_name).update({Patient.purok: new_name})
        if count > 0:
            print(f"Updated {count} patients from '{old_name}' to '{new_name}'")

    print("Updating Households...")
    for old_name, new_name in ZONE_MAPPING.items():
        count = HouseholdProfile.query.filter_by(purok=old_name).update({HouseholdProfile.purok: new_name})
        if count > 0:
            print(f"Updated {count} households from '{old_name}' to '{new_name}'")

    db.session.commit()
    print("--- Success! Database Updated ---")

if __name__ == "__main__":
    run_in_app_context(update_zones)