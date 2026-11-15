import logging
import json
import re
import os
from typing import Optional
from functools import wraps
from flask import request, redirect, url_for, flash, current_app, has_app_context
from flask_login import current_user
from models import AuditLog

logger = logging.getLogger(__name__)

NAME_WORD_PATTERN = r"[A-ZÑ][a-zñ]*"
NAME_PART_PATTERN = rf"{NAME_WORD_PATTERN}(?: {NAME_WORD_PATTERN})*"
MIDDLE_INITIAL_PATTERN = r"[A-Z]\."

FULL_NAME_PATTERNS = [
    re.compile(rf"^{NAME_PART_PATTERN} {NAME_PART_PATTERN}$", re.IGNORECASE),
    re.compile(rf"^{NAME_PART_PATTERN} {NAME_PART_PATTERN} {NAME_PART_PATTERN}$", re.IGNORECASE),
    re.compile(rf"^{NAME_PART_PATTERN} {NAME_PART_PATTERN} {MIDDLE_INITIAL_PATTERN}$", re.IGNORECASE),
    re.compile(rf"^{NAME_PART_PATTERN} {NAME_PART_PATTERN} {NAME_PART_PATTERN} {MIDDLE_INITIAL_PATTERN}$", re.IGNORECASE),
    re.compile(rf"^{NAME_PART_PATTERN} - {NAME_PART_PATTERN}$", re.IGNORECASE),
    re.compile(rf"^{NAME_PART_PATTERN} - {NAME_PART_PATTERN} - {NAME_PART_PATTERN}$", re.IGNORECASE),
    re.compile(rf"^{NAME_PART_PATTERN} - {NAME_PART_PATTERN} - {MIDDLE_INITIAL_PATTERN}$", re.IGNORECASE),
    re.compile(rf"^{NAME_PART_PATTERN} - {NAME_PART_PATTERN} - {NAME_PART_PATTERN} - {MIDDLE_INITIAL_PATTERN}$", re.IGNORECASE)
]


def sanitize_input(value):
    """Sanitize user input to prevent XSS attacks."""
    if not value:
        return value
    return value.strip() if isinstance(value, str) else value


def is_valid_full_name_format(value: str) -> bool:
    if not isinstance(value, str):
        return False
    clean_value = value.strip()
    return any(pattern.fullmatch(clean_value) for pattern in FULL_NAME_PATTERNS)


def role_required(*roles):
    """
    Decorator to restrict access to specific user roles.
    Usage: @role_required('Midwife', 'Admin')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Please log in first.', 'danger')
                return redirect(url_for('auth.login'))

            if current_user.role not in roles:
                logger.warning(f'Access denied: User {current_user.username} (role: {current_user.role}) tried to access {request.path}')
                allowed_roles = ', '.join(roles)
                flash(f'Access denied. This page is only for {allowed_roles}.', 'danger')
                return redirect(url_for('core.dashboard'))

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def log_user_action(action_name: str, details_fn=None):

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                result = f(*args, **kwargs)

                details = None
                if details_fn and result:
                    try:
                        details = details_fn(result)
                        if not isinstance(details, str):
                            details = json.dumps(details) if details else None
                    except Exception as e:
                        logger.warning(f'Error in details_fn for audit log: {str(e)}')
                        details = None

                ip_address = request.remote_addr
                user_id = current_user.id if current_user.is_authenticated else None
                AuditLog.log_action(
                    user_id=user_id,
                    action=action_name,
                    details=details,
                    ip_address=ip_address
                )

                logger.info(f'Audit: {action_name} by user {user_id} from {ip_address}')
                return result

            except Exception as e:
                try:
                    user_id = current_user.id if current_user.is_authenticated else None
                    ip_address = request.remote_addr
                    AuditLog.log_action(
                        user_id=user_id,
                        action=action_name,
                        details=f'ERROR: {str(e)[:500]}',
                        ip_address=ip_address
                    )
                except Exception:
                    pass
                raise
        return decorated_function
    return decorator


def has_permission(user, permission: str) -> bool:
    """Simple permission check: Admin has all, Midwife has delete/edit, BHW limited.
    Adjust rules here centrally.
    """
    if not user or not getattr(user, 'role', None):
        return False
    role = user.role
    if role == 'Admin':
        return True
    if role == 'Midwife':
        return permission in ['delete', 'edit', 'view']
    if role == 'BHW':
        return permission in ['view', 'create']
    return False


def permission_required(permission: str):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Please log in first.', 'danger')
                return redirect(url_for('auth.login'))
            if not has_permission(current_user, permission):
                flash('Access denied.', 'danger')
                return redirect(url_for('core.dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def normalize_ph_contact_number(raw_number: str) -> Optional[str]:
    if not raw_number:
        return None

    number = re.sub(r'\D', '', str(raw_number))
    if not number:
        return None

    if number.startswith('0') and len(number) == 11:
        return f'+63{number[1:]}'
    if number.startswith('63') and len(number) == 12:
        return f'+{number}'
    if number.startswith('9') and len(number) == 10:
        return f'+63{number}'
    if str(raw_number).strip().startswith('+63') and len(number) == 12:
        return f'+{number}'

    return None


def _load_mail_config() -> dict:
    if has_app_context():
        return {
            'mail_enabled': bool(current_app.config.get('MAIL_ENABLED', False)),
            'mail_server': str(current_app.config.get('MAIL_SERVER', 'smtp.gmail.com')),
            'mail_port': int(current_app.config.get('MAIL_PORT', 587)),
            'mail_use_tls': bool(current_app.config.get('MAIL_USE_TLS', True)),
            'mail_username': str(current_app.config.get('MAIL_USERNAME', '')),
            'mail_password': str(current_app.config.get('MAIL_PASSWORD', '')),
            'sender_name': str(current_app.config.get('MAIL_SENDER_NAME', 'BHCMS')),
            'default_sender': str(current_app.config.get('MAIL_DEFAULT_SENDER', current_app.config.get('MAIL_USERNAME', ''))),
        }

    mail_username = os.environ.get('MAIL_USERNAME', '')
    return {
        'mail_enabled': os.environ.get('MAIL_ENABLED', 'false').lower() == 'true',
        'mail_server': os.environ.get('MAIL_SERVER', 'smtp.gmail.com'),
        'mail_port': int(os.environ.get('MAIL_PORT', '587')),
        'mail_use_tls': os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true',
        'mail_username': mail_username,
        'mail_password': os.environ.get('MAIL_PASSWORD', ''),
        'sender_name': os.environ.get('MAIL_SENDER_NAME', 'BHCMS'),
        'default_sender': os.environ.get('MAIL_DEFAULT_SENDER', mail_username),
    }


def send_email(to_address: str, subject: str, body_html: str, body_text: str = None) -> dict:
    """Send an email via Gmail SMTP (App Password).
    Configure MAIL_USERNAME and MAIL_PASSWORD (App Password) in environment variables or config.py.
    """
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    config = _load_mail_config()
    mail_enabled = config['mail_enabled']
    mail_server = config['mail_server']
    mail_port = config['mail_port']
    mail_use_tls = config['mail_use_tls']
    mail_username = config['mail_username']
    mail_password = config['mail_password']
    sender_name = config['sender_name']
    default_sender = config['default_sender']

    if not mail_enabled:
        return {'success': False, 'error': 'Email is disabled. Set MAIL_ENABLED=true to enable.'}
    if not mail_username or not mail_password:
        return {'success': False, 'error': 'SMTP is not configured. Set MAIL_USERNAME and MAIL_PASSWORD (Gmail App Password).'}
    if not to_address or '@' not in to_address:
        return {'success': False, 'error': 'Invalid recipient email address.'}

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f'{sender_name} <{default_sender}>'
        msg['To'] = to_address

        if body_text:
            msg.attach(MIMEText(body_text, 'plain'))
        msg.attach(MIMEText(body_html, 'html'))

        with smtplib.SMTP(mail_server, mail_port, timeout=30) as smtp:
            if mail_use_tls:
                smtp.starttls()
            smtp.login(mail_username, mail_password)
            smtp.sendmail(default_sender, to_address, msg.as_string())

        logger.info(f'Email sent to {to_address}: {subject}')
        return {'success': True, 'recipient': to_address}
    except smtplib.SMTPAuthenticationError:
        return {'success': False, 'error': 'Gmail authentication failed. Make sure you are using a Gmail App Password (not your regular password). Enable 2FA and generate one at myaccount.google.com/apppasswords'}
    except smtplib.SMTPException as e:
        return {'success': False, 'error': f'SMTP error: {str(e)}'}
    except Exception as e:
        return {'success': False, 'error': f'Email send failed: {str(e)}'}