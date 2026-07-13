import logging

from flask import Flask, render_template
from flask_talisman import Talisman

from library.config import Config
from library.extensions import db, login_manager, csrf, limiter


def create_app(config_object: type = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object)

    # --- Extensiones ---
    db.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Inicia sesión para continuar"
    login_manager.login_message_category = "warning"

    @login_manager.user_loader
    def load_user(user_id):
        from library.models import User
        return db.session.get(User, int(user_id))

    # --- Cabeceras de seguridad (Talisman) ---
    # Fuerza HTTPS, HSTS, X-Content-Type-Options, X-Frame-Options y una
    # Content-Security-Policy que solo permite los CDN de Bootstrap ya usados
    # por las plantillas. `force_https` se desactiva en local para no romper
    # el desarrollo en http://127.0.0.1.
    is_production = bool(app.config.get("SESSION_COOKIE_SECURE"))
    csp = {
        "default-src": "'self'",
        "script-src": ["'self'", "https://cdn.jsdelivr.net"],
        "style-src": ["'self'", "https://cdn.jsdelivr.net", "'unsafe-inline'"],
        "img-src": ["'self'", "data:"],
        "font-src": ["'self'", "https://cdn.jsdelivr.net"],
    }
    Talisman(
        app,
        force_https=is_production,
        strict_transport_security=is_production,
        content_security_policy=csp,
        session_cookie_secure=is_production,
    )

    # --- Blueprints ---
    from library.routes.auth import bp as auth_bp
    from library.routes.main import bp as main_bp
    from library.routes.members import bp as members_bp
    from library.routes.books import bp as books_bp
    from library.routes.transactions import bp as transactions_bp
    from library.routes.marc21 import bp as marc21_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(members_bp)
    app.register_blueprint(books_bp)
    app.register_blueprint(transactions_bp)
    app.register_blueprint(marc21_bp)

    # --- Manejo de errores ---
    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        app.logger.exception("Error interno")
        return render_template("errors/500.html"), 500

    @app.errorhandler(429)
    def rate_limited(e):
        return render_template("errors/429.html"), 429

    @app.errorhandler(413)
    def too_large(e):
        return render_template("errors/413.html"), 413

    # --- CLI: inicialización de base de datos ---
    @app.cli.command("init-db")
    def init_db():
        """Crea las tablas en la base de datos configurada."""
        db.create_all()
        print("Base de datos inicializada.")

    @app.cli.command("create-admin")
    def create_admin():
        """Crea (o promueve) un usuario administrador de forma interactiva."""
        import getpass
        from library.models import User

        username = input("Usuario: ").strip()
        email = input("Email: ").strip().lower()
        password = getpass.getpass("Contraseña: ")

        user = User.query.filter_by(username=username).first()
        if user is None:
            user = User(username=username, email=email, role="admin")
        else:
            user.role = "admin"
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        print(f"Usuario administrador '{username}' listo.")

    if not app.debug:
        logging.basicConfig(level=logging.INFO)

    return app
