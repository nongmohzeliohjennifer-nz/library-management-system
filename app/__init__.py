from flask import Flask, session, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

THEME_COLORS = {
    'indigo': {'primary': '#4f46e5', 'glow': 'rgba(79, 70, 229, 0.35)', 'text': '#c7d2fe', 'text-muted': '#818cf8'},
    'emerald': {'primary': '#10b981', 'glow': 'rgba(16, 185, 129, 0.35)', 'text': '#a7f3d0', 'text-muted': '#34d399'},
    'ruby': {'primary': '#ef4444', 'glow': 'rgba(239, 68, 68, 0.35)', 'text': '#fecaca', 'text-muted': '#f87171'},
    'sapphire': {'primary': '#3b82f6', 'glow': 'rgba(59, 130, 246, 0.35)', 'text': '#bfdbfe', 'text-muted': '#60a5fa'},
    'amber': {'primary': '#f59e0b', 'glow': 'rgba(245, 158, 11, 0.35)', 'text': '#fde68a', 'text-muted': '#fbbf24'},
}

def create_app():
    app = Flask(__name__, template_folder='../templates', static_folder='../static')
    app.config.from_object(Config)

    # Initialize Extensions
    db.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'info'

    # Register Blueprints
    from app.auth.routes import auth_bp
    from app.library_dashboard.routes import dash_bp
    from app.api.routes import api_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(dash_bp)
    app.register_blueprint(api_bp, url_prefix='/api')

    @app.context_processor
    def inject_globals():
        from app.translations import translations
        lang = session.get('lang', 'en')
        if current_user.is_authenticated and hasattr(current_user, 'language'):
            lang = current_user.language
        t = translations.get(lang, translations['en'])

        theme = 'indigo'
        if current_user.is_authenticated and hasattr(current_user, 'theme_preference'):
            theme = current_user.theme_preference
        elif 'theme' in session:
            theme = session['theme']
        colors = THEME_COLORS.get(theme, THEME_COLORS['indigo'])

        def _(key):
            return t.get(key, key)

        return dict(_=_, t=translations, current_lang=lang, theme_name=theme, theme_colors=colors, THEME_COLORS=THEME_COLORS)

    @app.before_request
    def set_language():
        if 'lang' in request.args:
            lang = request.args['lang']
            if lang in ('en', 'fr'):
                session['lang'] = lang
                if current_user.is_authenticated:
                    from app.models import User
                    user = User.query.get(current_user.id)
                    if user:
                        user.language = lang
                        db.session.commit()

    @app.before_request
    def set_theme():
        if 'theme' in request.args:
            theme = request.args['theme']
            if theme in THEME_COLORS:
                session['theme'] = theme
                if current_user.is_authenticated:
                    from app.models import User
                    user = User.query.get(current_user.id)
                    if user:
                        user.theme_preference = theme
                        db.session.commit()

    @app.after_request
    def set_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Server'] = 'Secure-Library-App'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://fonts.googleapis.com https://fonts.gstatic.com; font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com; img-src 'self' data: https://images.unsplash.com; frame-ancestors 'self' https://huggingface.co https://*.hf.space;"
        return response

    # Auto-create tables and seed on startup (idempotent)
    with app.app_context():
        db.create_all()
        from app.models import Book
        if Book.query.first() is None:
            sample = [
                Book(title="To Kill a Mockingbird", author="Harper Lee", isbn="978-0446310789", genre="Fiction"),
                Book(title="1984", author="George Orwell", isbn="978-0451524935", genre="Dystopian"),
                Book(title="The Great Gatsby", author="F. Scott Fitzgerald", isbn="978-0743273565", genre="Classic"),
                Book(title="The Hobbit", author="J.R.R. Tolkien", isbn="978-0547928227", genre="Fantasy"),
                Book(title="Pride and Prejudice", author="Jane Austen", isbn="978-0141439518", genre="Romance"),
            ]
            for b in sample:
                db.session.add(b)
            db.session.commit()
            print("Seeded sample books.")

    return app
