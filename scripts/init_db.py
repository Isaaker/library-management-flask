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

from library import create_app
from library.extensions import db

app = create_app()

with app.app_context():
    db.create_all()
    print("Tablas creadas correctamente.")
