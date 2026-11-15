import logging
import re

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from models import db, User
from utils import role_required, sanitize_input

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = sanitize_input(request.form.get('username', ''))
        password = request.form.get('password', '')

        if not username or not password:
            flash('Username and password are required.', 'danger')
            return render_template('login.html')

        if not re.match(r'^[a-zA-Z0-9_]{3,30}$', username):
            flash('Invalid username format.', 'danger')
            return render_template('login.html')

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            if not user.is_active:
                flash('Your account has been deactivated. Please contact the administrator.', 'warning')
                return render_template('login.html')
            login_user(user)
            logger.info(f'User {username} logged in from {request.remote_addr}')
            if user.role == 'Midwife':
                return redirect(url_for('midwife_dashboard'))
            if user.role == 'BHW':
                return redirect(url_for('bhw_dashboard'))
            return redirect(url_for('core.dashboard'))

        flash('Invalid username or password.', 'danger')

    return render_template('login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logger.info(f'User {current_user.username} logged out.')
    logout_user()
    return redirect(url_for('auth.login'))


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN ONLY: Healthcare Worker & Staff Account Management
# ─────────────────────────────────────────────────────────────────────────────
@auth_bp.route('/users', methods=['GET', 'POST'])
@login_required
@role_required('Admin')
def manage_users():
    """Admin-only portal to view, create, activate/deactivate Midwife and BHW accounts."""
    if request.method == 'POST':
        action = request.form.get('action', 'create')

        if action == 'create':
            username = sanitize_input(request.form.get('username', '')).strip().lower()
            password = request.form.get('password', '')
            full_name = sanitize_input(request.form.get('full_name', '')).strip()
            role = request.form.get('role', 'BHW').strip()
            email = sanitize_input(request.form.get('email', '')).strip() or None
            contact_number = sanitize_input(request.form.get('contact_number', '')).strip() or None

            # Validations
            if not username or not password or not full_name:
                flash('Full Name, Username, and Password are required.', 'danger')
                return redirect(url_for('auth.manage_users'))

            if not re.match(r'^[a-zA-Z0-9_]{3,30}$', username):
                flash('Username must be 3-30 characters (letters, numbers, underscores only).', 'danger')
                return redirect(url_for('auth.manage_users'))

            if len(password) < 6:
                flash('Password must be at least 6 characters long.', 'danger')
                return redirect(url_for('auth.manage_users'))

            if role not in ['Midwife', 'BHW', 'Admin']:
                flash('Invalid role selected. Allowed roles: Midwife, BHW, Admin.', 'danger')
                return redirect(url_for('auth.manage_users'))

            if User.query.filter_by(username=username).first():
                flash(f'Username "{username}" is already taken. Please choose another.', 'danger')
                return redirect(url_for('auth.manage_users'))

            if email and User.query.filter_by(email=email).first():
                flash(f'Email "{email}" is already in use by another account.', 'danger')
                return redirect(url_for('auth.manage_users'))

            new_user = User(
                username=username,
                password=generate_password_hash(password),
                full_name=full_name,
                role=role,
                email=email,
                contact_number=contact_number,
                is_active=True
            )
            db.session.add(new_user)
            db.session.commit()
            logger.info(f'Admin {current_user.username} created new {role} account: {username}')
            flash(f'✅ Successfully created {role} account for {full_name} (@{username})!', 'success')
            return redirect(url_for('auth.manage_users'))

        elif action == 'toggle_status':
            user_id = request.form.get('user_id', type=int)
            target_user = User.query.get(user_id)
            if not target_user:
                flash('User not found.', 'danger')
                return redirect(url_for('auth.manage_users'))

            if target_user.id == current_user.id:
                flash('Action not allowed: You cannot deactivate your own admin account.', 'warning')
                return redirect(url_for('auth.manage_users'))

            target_user.is_active = not target_user.is_active
            db.session.commit()
            status_text = 'activated' if target_user.is_active else 'deactivated'
            flash(f'Account for {target_user.full_name} has been {status_text}.', 'info')
            return redirect(url_for('auth.manage_users'))

        elif action == 'reset_password':
            user_id = request.form.get('user_id', type=int)
            new_password = request.form.get('new_password', '')
            if len(new_password) < 6:
                flash('New password must be at least 6 characters long.', 'danger')
                return redirect(url_for('auth.manage_users'))

            target_user = User.query.get(user_id)
            if not target_user:
                flash('User not found.', 'danger')
                return redirect(url_for('auth.manage_users'))

            target_user.password = generate_password_hash(new_password)
            db.session.commit()
            flash(f'Password reset successfully for @{target_user.username}.', 'success')
            return redirect(url_for('auth.manage_users'))

    # GET Request: Filter & Search
    role_filter = request.args.get('role', '').strip()
    search = request.args.get('search', '').strip()

    query = User.query
    if role_filter:
        query = query.filter_by(role=role_filter)
    if search:
        query = query.filter(
            (User.full_name.ilike(f'%{search}%')) |
            (User.username.ilike(f'%{search}%')) |
            (User.email.ilike(f'%{search}%'))
        )

    users = query.order_by(User.created_at.desc()).all()

    total_users = User.query.count()
    midwife_count = User.query.filter_by(role='Midwife').count()
    bhw_count = User.query.filter_by(role='BHW').count()
    admin_count = User.query.filter_by(role='Admin').count()

    return render_template(
        'admin_users.html',
        users=users,
        total_users=total_users,
        midwife_count=midwife_count,
        bhw_count=bhw_count,
        admin_count=admin_count,
        selected_role=role_filter,
        search_query=search
    )
