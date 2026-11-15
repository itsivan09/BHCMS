"""
Database reset script to rebuild the database with updated schema.
This will drop all tables and recreate them from the updated models.
"""

import sys
from app import db
from script_utils import run_in_app_context

def reset_database():
    """Drop all tables and recreate them with the new schema."""
    print("⚠️  WARNING: This will delete all data in the database!")
    confirm = input("Type 'YES' to continue: ")

    if confirm.upper() != 'YES':
        print("Cancelled.")
        sys.exit(0)

    print("\n🗑️  Dropping all tables...")
    db.drop_all()

    print("✅ Creating new tables with updated schema...")
    db.create_all()

    print("✅ Database reset complete!")

if __name__ == '__main__':
    run_in_app_context(reset_database)