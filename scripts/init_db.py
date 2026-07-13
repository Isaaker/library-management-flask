"""
Crea las tablas en la base de datos configurada (DATABASE_URL).

Uso:
    python scripts/init_db.py

Equivalente a `flask --app run init-db`, pero sin depender del CLI de Flask
(útil en contenedores o pipelines de CI/CD).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine

from library import create_app
from library.extensions import db

app = create_app()

# Para crear tablas (DDL) se usa la conexión SIN pooler (DATABASE_URL_UNPOOLED
# / POSTGRES_URL_NON_POOLING en Neon), ya que PgBouncer en modo "transaction
# pooling" (el que usa la URL normal, pensada para la app) puede dar
# problemas con operaciones de sesión que algunas herramientas de esquema
# necesitan. Se usa un engine de SQLAlchemy aparte, sin tocar el motor que
# ya tiene inicializado Flask-SQLAlchemy para el resto de la app.
with app.app_context():
    engine = create_engine(app.config["SQLALCHEMY_DATABASE_URI_UNPOOLED"])
    db.metadata.create_all(bind=engine)
    engine.dispose()
    print("Tablas creadas correctamente (usando conexión sin pooler).")
