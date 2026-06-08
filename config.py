import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY')
    if not SECRET_KEY:
        raise RuntimeError('SECRET_KEY environment variable is required. Generate one with: python -c "import secrets; print(secrets.token_hex(32))"')

    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', '').replace('postgres://', 'postgresql://')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    DEBUG = os.getenv('DEBUG', 'False') == 'True'

    # Auto-detect production: Railway sets PORT and RAILWAY_ENVIRONMENT
    IS_PRODUCTION = bool(os.getenv('PORT')) or os.getenv('RAILWAY_ENVIRONMENT') == 'production'

    # CSRF disabled in local debug mode (enabled automatically in production)
    WTF_CSRF_ENABLED = not DEBUG or IS_PRODUCTION
    WTF_CSRF_TIME_LIMIT = 3600  # 1 hour

    # Session hardening
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = IS_PRODUCTION
    SESSION_COOKIE_SAMESITE = 'Strict'
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)
    SESSION_COOKIE_NAME = 'LibSession'

    # Upload hardening
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5MB
    UPLOAD_EXTENSIONS = ('.pdf', '.epub', '.txt')
    UPLOAD_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'static', 'uploads')
