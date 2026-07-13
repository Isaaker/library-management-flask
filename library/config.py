"""
Configuración de la aplicación, leída siempre desde variables de entorno.

IMPORTANTE (seguridad): a diferencia del proyecto original, aquí NUNCA hay
credenciales ni secretos escritos en el código fuente. Todo se lee de
variables de entorno (en Vercel: Project Settings → Environment Variables;
en local: fichero .env, ver .env.example).
"""
import os


def _database_url() -> str:
    """Normaliza la URL de base de datos.

    Vercel Postgres / Neon / Supabase suelen exponer `POSTGRES_URL` o
    `DATABASE_URL` con el esquema `postgres://`, que SQLAlchemy 2.x ya no
    acepta (requiere `postgresql://`). Se corrige automáticamente.
    Si no hay ninguna configurada, se usa SQLite local como fallback para
    desarrollo (NO recomendado en producción/serverless).
    """
    url = (
        os.environ.get("DATABASE_URL")
        or os.environ.get("POSTGRES_URL")
        or os.environ.get("POSTGRES_PRISMA_URL")
        or "sqlite:///local_library.db"
    )
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif url.startswith("postgresql://") and "+psycopg2" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    if not SECRET_KEY:
        # En producción exigimos que SECRET_KEY esté definido explícitamente.
        if os.environ.get("VERCEL") or os.environ.get("FLASK_ENV") == "production":
            raise RuntimeError(
                "La variable de entorno SECRET_KEY es obligatoria en producción."
            )
        SECRET_KEY = "dev-only-insecure-secret-change-me"  # solo para desarrollo local

    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_ENGINE_OPTIONS = {
        # pool_pre_ping evita errores de conexión "stale" típicos de entornos
        # serverless (Vercel) donde la función puede reutilizar/recrear
        # instancias de forma impredecible.
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Cookies de sesión seguras
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("FLASK_ENV") == "production" or bool(
        os.environ.get("VERCEL")
    )
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 4  # 4 horas

    WTF_CSRF_TIME_LIMIT = None

    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB, límite de subida (ficheros MARC21)

    # API externa usada por "Importar libros"
    FRAPPE_LIBRARY_API = "https://frappe.io/api/method/frappe-library"

    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
