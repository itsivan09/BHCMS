from datetime import date
from pathlib import Path

import pytest
from flask import Flask
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash

from models import PUROK_CHOICES, Patient, User, db
from routes import register_blueprints, register_legacy_endpoint_aliases
from utils import has_permission


@pytest.fixture
def app_instance(tmp_path):
    test_db_path = tmp_path / "test_bhcms.sqlite"
    project_root = Path(__file__).resolve().parents[1]
    app = Flask(
        __name__,
        template_folder=str(project_root / "templates"),
        static_folder=str(project_root / "static"),
    )
    app.config.update(
        SECRET_KEY="test-secret-key",
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        MAIL_ENABLED=False,
        MAIL_DAILY_REMINDER_ENABLED=False,
        SQLALCHEMY_DATABASE_URI=f"sqlite:///{test_db_path}",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )

    db.init_app(app)
    CSRFProtect(app)

    login_manager = LoginManager()
    login_manager.login_view = "auth.login"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    app.jinja_env.globals["has_permission"] = has_permission
    register_blueprints(app)
    register_legacy_endpoint_aliases(app)

    with app.app_context():
        db.session.remove()
        db.drop_all()
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app_instance):
    return app_instance.test_client()


@pytest.fixture
def create_user(app_instance):
    def _create_user(username, role, password="pass123", full_name=None):
        user = User(
            username=username,
            password=generate_password_hash(password),
            role=role,
            full_name=full_name or f"{role} User",
        )
        db.session.add(user)
        db.session.commit()
        return user

    return _create_user


@pytest.fixture
def login_as(client):
    def _login(username, password="pass123"):
        return client.post(
            "/login",
            data={"username": username, "password": password},
            follow_redirects=False,
        )

    return _login


@pytest.fixture
def seed_users(app_instance, create_user):
    users = {
        "admin": create_user("admin", "Admin", full_name="Admin User"),
        "midwife": create_user("midwife", "Midwife", full_name="Midwife User"),
        "bhw": create_user("bhw", "BHW", full_name="BHW User"),
    }
    return users


@pytest.fixture
def sample_patient(app_instance):
    patient = Patient(
        full_name="Dela Cruz Maria",
        birth_date=date(1995, 5, 20),
        gender="Female",
        purok=PUROK_CHOICES[0],
        is_pregnant=False,
        email="maria@example.com",
        contact_number="09171234567",
    )
    db.session.add(patient)
    db.session.commit()
    return patient
