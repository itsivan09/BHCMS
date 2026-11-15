import logging
import re

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash

from models import User
from utils import sanitize_input

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

        if not re.match(r'^[a-zA-Z0-9_]{3,20}$', username):
            flash('Invalid username format.', 'danger')
            return render_template('login.html')

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
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
