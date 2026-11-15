import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

try:
    import pymysql
    pymysql.install_as_MySQLdb()
except ImportError:
    pass
import logging
from flask import Flask, redirect, url_for, request, flash
from flask_login import LoginManager, current_user
from werkzeug.security import generate_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix
from models import db, User, Notification, Appointment
from config import Config
from datetime import datetime, date, timedelta
from sqlalchemy import inspect, text
from sqlalchemy.orm import joinedload
from flask_wtf.csrf import CSRFProtect, CSRFError
from routes import register_blueprints, register_legacy_endpoint_aliases
from utils import has_permission, send_email

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config.from_object(Config)

# Fix proxy headers so HTTPS and Custom Domain URLs work on Vercel
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

csrf = CSRFProtect(app)
app.config['SQLALCHEMY_DATABASE_URI'] = Config.SQLALCHEMY_DATABASE_URI

if os.environ.get('VERCEL'):
    UPLOAD_FOLDER = os.path.join('/tmp', 'uploads', 'events')
else:
    UPLOAD_FOLDER = os.path.join('static', 'uploads', 'events')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
try:
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
except OSError:
    pass


_last_appointment_email_reminder_run = None


def _appointment_email_html(patient_name, appt_date_str, appt_time_str, worker_name):
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#f9f9f9;padding:24px;border-radius:8px;">
        <div style="background:#0e7c86;padding:16px 24px;border-radius:8px 8px 0 0;">
            <h2 style="color:#fff;margin:0;">🏥 BHCMS Appointment Reminder</h2>
        </div>
        <div style="background:#fff;padding:24px;border-radius:0 0 8px 8px;border:1px solid #e0e0e0;">
            <p style="font-size:16px;">Hi <strong>{patient_name}</strong>,</p>
            <p style="font-size:15px;">This is a reminder that you have an upcoming appointment:</p>
            <table style="width:100%;border-collapse:collapse;margin:16px 0;">
                <tr><td style="padding:8px;background:#f0f8f9;font-weight:bold;width:40%;">📅 Date</td>
                    <td style="padding:8px;">{appt_date_str}</td></tr>
                <tr><td style="padding:8px;background:#f0f8f9;font-weight:bold;">⏰ Time</td>
                    <td style="padding:8px;">{appt_time_str}</td></tr>
                <tr><td style="padding:8px;background:#f0f8f9;font-weight:bold;">👤 Healthcare Worker</td>
                    <td style="padding:8px;">{worker_name}</td></tr>
            </table>
            <p style="color:#555;">Please arrive on time. If you need to reschedule, contact the health center.</p>
            <p style="color:#888;font-size:12px;">— Barangay Health Center Management System (BHCMS)</p>
        </div>
    </div>"""


def _today_time_window(today: date):
    today_start = datetime.combine(today, datetime.min.time())
    return today_start, today_start + timedelta(days=1)


def _get_today_sent_appointment_email_ids(today_start: datetime, tomorrow_start: datetime):
    return {
        row[0] for row in db.session.query(Notification.related_item_id)
        .filter(
            Notification.type == 'appointment',
            Notification.related_item_type == 'appointment_email_reminder',
            Notification.created_at >= today_start,
            Notification.created_at < tomorrow_start,
            Notification.related_item_id.isnot(None)
        )
        .all()
    }


def _queue_appointment_reminder_notification(appointment: Appointment, patient, patient_email: str, result: dict):
    if result.get('success'):
        db.session.add(Notification(
            user_id=appointment.health_worker_id,
            type='appointment',
            title='Appointment reminder email sent',
            message=f'Reminder email sent to {patient_email} for {patient.full_name} (appointment #{appointment.id}).',
            related_item_id=appointment.id,
            related_item_type='appointment_email_reminder'
        ))
        return True

    db.session.add(Notification(
        user_id=appointment.health_worker_id,
        type='system_alert',
        title='Appointment reminder email failed',
        message=f'Could not send reminder email to {patient.full_name}: {result.get("error", "Unknown error")}',
        related_item_id=appointment.id,
        related_item_type='appointment_email_reminder'
    ))
    return False


def run_daily_appointment_email_reminders():
    global _last_appointment_email_reminder_run
    if not app.config.get('MAIL_ENABLED', False):
        return
    if not app.config.get('MAIL_DAILY_REMINDER_ENABLED', True):
        return
    today = date.today()
    if _last_appointment_email_reminder_run == today:
        return

    tomorrow = today + timedelta(days=1)
    appointments = Appointment.query.options(
        joinedload(Appointment.patient),
        joinedload(Appointment.health_worker)
    ).filter_by(
        appointment_date=tomorrow,
        status='scheduled'
    ).all()

    today_start, tomorrow_start = _today_time_window(today)
    already_sent_ids = _get_today_sent_appointment_email_ids(today_start, tomorrow_start)

    queued_count = 0
    failed_count = 0

    for appointment in appointments:
        patient = appointment.patient
        # Only send if patient has an email recorded (you can add email field; skip for now if not present)
        patient_email = getattr(patient, 'email', None)
        if not patient_email:
            continue

        if appointment.id in already_sent_ids:
            continue

        appt_date_str = appointment.appointment_date.strftime('%B %d, %Y')
        appt_time_str = appointment.appointment_time.strftime('%I:%M %p')
        worker_name = appointment.health_worker.full_name

        email_html = _appointment_email_html(patient.full_name, appt_date_str, appt_time_str, worker_name)
        email_text = (
            f'BHCMS Reminder: Hi {patient.full_name}, your appointment is tomorrow '
            f'({appt_date_str}) at {appt_time_str} with {worker_name}. Please arrive on time.'
        )

        result = send_email(
            to_address=patient_email,
            subject=f'BHCMS Appointment Reminder – {appt_date_str}',
            body_html=email_html,
            body_text=email_text
        )

        if _queue_appointment_reminder_notification(appointment, patient, patient_email, result):
            queued_count += 1
            already_sent_ids.add(appointment.id)
        else:
            failed_count += 1

    if queued_count or failed_count:
        db.session.commit()
    _last_appointment_email_reminder_run = today
    logger.info(f'Daily appointment reminder email run complete. Sent={queued_count}, Failed={failed_count}')


def ensure_patient_email_column():
    try:
        inspector = inspect(db.engine)
        columns = {col['name'] for col in inspector.get_columns('patient')}
        if 'email' not in columns:
            db.session.execute(text('ALTER TABLE patient ADD COLUMN email VARCHAR(120)'))
            db.session.commit()
            logger.info('Schema update applied: added patient.email column.')
    except Exception as e:
        db.session.rollback()
        logger.warning(f'Schema check/update skipped for patient.email: {e}')


def ensure_performance_indexes():
    index_specs = {
        'consultation': [
            ('ix_consultation_patient_date', 'patient_id, date'),
            ('ix_consultation_worker_date', 'health_worker_id, date'),
        ],
        'operation_timbang': [
            ('ix_opt_patient_measurement_date', 'patient_id, measurement_date'),
            ('ix_opt_followup_measurement_date', 'requires_followup, measurement_date'),
        ],
        'prenatal_record': [
            ('ix_prenatal_patient_active', 'patient_id, is_active'),
            ('ix_prenatal_active_delivery', 'is_active, estimated_delivery_date'),
        ],
        'immunization_schedule': [
            ('ix_immunization_completed_scheduled', 'is_completed, scheduled_date'),
            ('ix_immunization_patient_completed', 'patient_id, is_completed'),
        ],
        'notification': [
            ('ix_notification_user_read_created', 'user_id, is_read, created_at'),
            ('ix_notification_related_type_created', 'related_item_type, related_item_id, type, created_at'),
        ],
        'appointment': [
            ('ix_appointment_worker_date_time_status', 'health_worker_id, appointment_date, appointment_time, status'),
            ('ix_appointment_date_status', 'appointment_date, status'),
        ],
    }

    try:
        inspector = inspect(db.engine)
        for table_name, table_indexes in index_specs.items():
            existing_indexes = {idx['name'] for idx in inspector.get_indexes(table_name)}
            for index_name, columns in table_indexes:
                if index_name in existing_indexes:
                    continue
                db.session.execute(text(f'CREATE INDEX {index_name} ON {table_name} ({columns})'))
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.warning(f'Performance index creation skipped: {e}')


@app.before_request
def auto_send_daily_appointment_reminders():
    if request.endpoint in ['static', 'favicon', 'core.favicon']:
        return
    if not current_user.is_authenticated:
        return

    try:
        run_daily_appointment_email_reminders()
    except Exception as e:
        db.session.rollback()
        logger.warning(f'Daily appointment email reminder run skipped: {e}')


@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    logger.warning(f'CSRF validation failed: {e.description}')
    flash('Security check failed. Please try again.', 'danger')
    return redirect(request.referrer or url_for('core.dashboard'))

@app.after_request
def set_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response

db.init_app(app)
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.init_app(app)
app.jinja_env.globals['has_permission'] = has_permission
register_blueprints(app)
register_legacy_endpoint_aliases(app)

@login_manager.user_loader
def load_user(user_id: int) -> User:
    return User.query.get(int(user_id))










# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        ensure_patient_email_column()
        ensure_performance_indexes()
        default_users = [
            ('admin', 'admin123', 'Admin', 'Admin User'),
            ('midwife', 'midwife123', 'Midwife', 'Midwife Maria'),
            ('bhw', 'bhw123', 'BHW', 'BHW Juan')
        ]
        created_any = False
        for username, pwd, role, name in default_users:
            if not User.query.filter_by(username=username).first():
                db.session.add(User(username=username, password=generate_password_hash(pwd), role=role, full_name=name))
                created_any = True
        if created_any:
            db.session.commit()
            print("✅ Default users ensured (admin/midwife/bhw)")
    print("🚀 Starting BHCMS Server...")
    print("👉 OPEN THIS LINK: http://127.0.0.1:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)