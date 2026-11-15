import os
from datetime import timedelta

class Config:
    """
    Base configuration for Barangay Health CMS.
    Compatible with both local MySQL/SQLite and production Supabase PostgreSQL / Vercel.
    """
    # Security
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secure-secret-key-change-in-production-2024'
    
    # Database - Supports Supabase / PostgreSQL and local MySQL/SQLite
    db_uri = os.environ.get('DATABASE_URL') or os.environ.get('SQLALCHEMY_DATABASE_URI') or 'mysql+pymysql://root:@127.0.0.1:3307/bhcms_db'
    if db_uri.startswith('postgres://'):
        db_uri = db_uri.replace('postgres://', 'postgresql://', 1)
    
    SQLALCHEMY_DATABASE_URI = db_uri
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }
    
    # CSRF Protection
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None
    
    # Session Configuration
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    SESSION_COOKIE_SECURE = os.environ.get('FLASK_ENV') == 'production' or bool(os.environ.get('VERCEL'))
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Application Settings
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file upload
    SEND_FILE_MAX_AGE_DEFAULT = 31536000  # Cache static files for 1 year
    
    # Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')

    # Supabase Cloud Storage (for serverless file uploads)
    SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
    SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')

    # Email (Configured via Environment Variables)
    MAIL_ENABLED = os.environ.get('MAIL_ENABLED', 'false').lower() == 'true'
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', '587'))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    MAIL_SENDER_NAME = os.environ.get('MAIL_SENDER_NAME', 'BHCMS Health Center')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', os.environ.get('MAIL_USERNAME', ''))
    MAIL_DAILY_REMINDER_ENABLED = os.environ.get('MAIL_DAILY_REMINDER_ENABLED', 'false').lower() == 'true'

    # SMS (Semaphore or Textbelt; set values via environment variables)
    SMS_ENABLED = os.environ.get('SMS_ENABLED', 'false').lower() == 'true'
    SMS_PROVIDER = os.environ.get('SMS_PROVIDER', 'textbelt').lower()
    SMS_API_KEY = os.environ.get('SMS_API_KEY', 'textbelt')
    SMS_SENDER_NAME = os.environ.get('SMS_SENDER_NAME', 'BHCMS')
    SMS_TIMEOUT_SECONDS = int(os.environ.get('SMS_TIMEOUT_SECONDS', '15'))
    SMS_DAILY_REMINDER_ENABLED = os.environ.get('SMS_DAILY_REMINDER_ENABLED', 'false').lower() == 'true'


class DevelopmentConfig(Config):
    """Development configuration with debug mode enabled."""
    DEBUG = True
    TESTING = False


class ProductionConfig(Config):
    """Production configuration with strict security settings."""
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True


class TestingConfig(Config):
    """Testing configuration with in-memory database."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


# Select configuration based on environment
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

Config = config[os.environ.get('FLASK_ENV', 'development')]
