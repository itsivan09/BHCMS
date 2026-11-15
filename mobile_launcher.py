import socket
import sys
import webbrowser

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

def get_local_ip():
    """Detect local IP address of this computer on the local network/Wi-Fi."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def print_qr_code(url):
    """Render a clean text & visual launcher box for the mobile app URL."""
    print("=" * 64)
    print("📱 BHCMS MOBILE APPLICATION SERVER IS NOW RUNNING!")
    print("=" * 64)
    print(f"\n👉 LOCALHOST URL (THIS COMPUTER):  {url}")
    local_ip = get_local_ip()
    if local_ip != "127.0.0.1":
        mobile_url = f"http://{local_ip}:5000"
        print(f"📱 MOBILE NETWORK URL (ANY PHONE ON WI-FI): {mobile_url}\n")
        print("💡 HOW TO CONNECT FROM YOUR MOBILE PHONE / TABLET:")
        print("   1. Connect your mobile phone to the same Wi-Fi network.")
        print(f"   2. Open Chrome/Safari on your phone and go to: {mobile_url}")
        print("   3. Tap 'Add to Home Screen' to install as a full-screen Mobile App!")
    print("=" * 64 + "\n")

if __name__ == "__main__":
    from app import app, db, User, ensure_patient_email_column, ensure_performance_indexes
    from werkzeug.security import generate_password_hash

    with app.app_context():
        db.create_all()
        ensure_patient_email_column()
        ensure_performance_indexes()
        default_users = [
            ('admin', 'admin123', 'Admin', 'Admin User'),
            ('midwife', 'midwife123', 'Midwife', 'Midwife Maria'),
            ('bhw', 'bhw123', 'BHW', 'BHW Juan')
        ]
        for username, pwd, role, name in default_users:
            if not User.query.filter_by(username=username).first():
                db.session.add(User(username=username, password=generate_password_hash(pwd), role=role, full_name=name))
        db.session.commit()

    local_url = "http://127.0.0.1:5000"
    print_qr_code(local_url)
    
    # Run server listening on all network interfaces (0.0.0.0) so phones on Wi-Fi can connect
    app.run(host='0.0.0.0', port=5000, debug=False)
