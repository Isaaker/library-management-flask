"""
Configuración de la aplicación, leída siempre desde variables de entorno.

IMPORTANTE (seguridad): a diferencia del proyecto original, aquí NUNCA hay
credenciales ni secretos escritos en el código fuente. Todo se lee de
variables de entorno (en Vercel: Project Settings → Environment Variables;
en local: fichero .env, ver .env.example).
"""
import os


def _redis_storage_uri() -> str | None:
    """Normaliza REDIS_URL para usarla como backend de Flask-Limiter (y caché).

    Vercel es de solo lectura (solo /tmp es escribible, y es efímero: no
    sobrevive entre invocaciones ni se comparte entre instancias). Eso hace
    inútil el backend por defecto `memory://` de Flask-Limiter en
    serverless: cada invocación puede ejecutarse en una instancia distinta,
    así que los contadores de intentos de login nunca se acumulan de verdad.
    Redis, al ser un servicio externo, sí es compartido entre invocaciones.

    Se admite tanto `REDIS_URL` (variable estándar que exponen Upstash,
    Redis Cloud, Vercel Marketplace, etc.) como alias comunes.
    """
    url = (
        os.environ.get("REDIS_URL")
        or os.environ.get("KV_URL")  # alias usado por algunos add-ons de Vercel
        or os.environ.get("REDISCLOUD_URL")
    )
    if not url:
        return None
    # `redis://` = texto plano, `rediss://` = TLS (Upstash y la mayoría de
    # proveedores gestionados lo exigen). Se respeta el esquema tal cual
    # venga en la variable de entorno, solo se valida que sea reconocible.
    if not (url.startswith("redis://") or url.startswith("rediss://") or url.startswith("unix://")):
        raise RuntimeError(
            "REDIS_URL tiene un esquema no soportado; debe empezar por redis:// o rediss://"
        )
    return url


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

    REDIS_URL = _redis_storage_uri()

    # Prioridad: RATELIMIT_STORAGE_URI explícita > REDIS_URL > memoria local.
    # "memory://" NO es fiable en Vercel (ver _redis_storage_uri arriba), así
    # que si se detecta que se está corriendo en Vercel sin Redis configurado,
    # se avisa en los logs en tiempo de arranque (ver library/__init__.py).
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI") or REDIS_URL or "memory://"
    RATELIMIT_STRATEGY = "fixed-window"
    # Cabecera para poder usar Redis con TLS de proveedores que usan
    # certificados no verificados por la CA por defecto del sistema (algunos
    # planes gratuitos de Upstash/Redis Cloud). Se puede forzar con
    # REDIS_INSECURE_TLS=1 si el proveedor lo requiere; por defecto se valida.
    REDIS_INSECURE_TLS = os.environ.get("REDIS_INSECURE_TLS") == "1"

    # Caché opcional (ver library/cache.py). Se activa automáticamente si hay
    # Redis disponible; si no, la app funciona igual mas sin caché.
    CACHE_ENABLED = REDIS_URL is not None
