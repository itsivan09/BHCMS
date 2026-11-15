"""
Database Initialization Script for Supabase PostgreSQL.
Run this script once locally pointing to your Supabase DATABASE_URL
to create all tables, indexes, and initial admin/staff users.

Usage:
  # On Windows PowerShell:
  $env:DATABASE_URL="postgresql://postgres.[REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres?sslmode=require"
  python init_supabase.py
"""

import os
import sys
from werkzeug.security import generate_password_hash

# Ensure we import from current directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, ensure_patient_email_column, ensure_performance_indexes
from models import User

def init_database():
    print(f"Connecting to: {app.config['SQLALCHEMY_DATABASE_URI'][:30]}...")
    with app.app_context():
        print("Creating all tables in Supabase...")
        db.create_all()

        print("Ensuring columns & indexes...")
        ensure_patient_email_column()
        ensure_performance_indexes()

        default_users = [
            ('admin', 'admin123', 'Admin', 'Admin User'),
            ('midwife', 'midwife123', 'Midwife', 'Midwife Maria'),
            ('bhw', 'bhw123', 'BHW', 'BHW Juan')
        ]
        
        created_count = 0
        for username, pwd, role, name in default_users:
            if not User.query.filter_by(username=username).first():
                db.session.add(User(
                    username=username,
                    password=generate_password_hash(pwd),
                    role=role,
                    full_name=name
                ))
                created_count += 1
                print(f"  + Added user: {username} ({role})")
        
        if created_count > 0:
            db.session.commit()
            print(f"✅ Successfully seeded {created_count} default users.")
        else:
            print("ℹ️ Default users already exist.")

        print("\n🎉 Database setup complete! Supabase is ready for Vercel deployment.")

if __name__ == '__main__':
    init_database()
