import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

print("--- 1. CHECKING PYTHON LIBRARIES ---")
try:
    import flask
    import flask_sqlalchemy
    import pymysql
    import openpyxl
    import pdfkit
    print("✅ All libraries are installed!")
except ImportError as e:
    print(f"❌ MISSING LIBRARY: {e}")
    print("👉 FIX: Run 'pip install flask flask-sqlalchemy pymysql openpyxl pdfkit'")
    sys.exit()

print("\n--- 2. CHECKING DATABASE CONNECTION ---")
try:
    import pymysql
    # Try connecting to project MySQL config (User: root, No Password)
    connection = pymysql.connect(host='127.0.0.1', port=3307, user='root', password='')
    print("✅ Successfully connected to XAMPP MySQL!")
    
    # Check if database exists
    cursor = connection.cursor()
    cursor.execute("SHOW DATABASES LIKE 'bhcms_db'")
    result = cursor.fetchone()
    
    if result:
        print("✅ Database 'bhcms_db' exists!")
    else:
        print("❌ Database 'bhcms_db' is MISSING.")
        print("👉 FIX: Go to http://localhost/phpmyadmin and create a database named 'bhcms_db'")
        
    connection.close()
except Exception as e:
    print(f"❌ CONNECTION FAILED: {e}")
    print("👉 FIX: Make sure MySQL is running on 127.0.0.1:3307 and accepting connections.")