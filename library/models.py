"""
Modelos de datos (SQLAlchemy ORM).

Se sustituye el acceso directo con MySQLdb del proyecto original por un ORM,
lo que elimina por completo el riesgo de inyección SQL (todas las consultas
usan parámetros ligados automáticamente) y hace la app compatible con
Postgres (recomendado en Vercel, p.ej. Neon / Supabase / Vercel Postgres),
MySQL o SQLite.
"""
from datetime import datetime, date

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from library.extensions import db


class User(db.Model, UserMixin):
    """Usuario del sistema (bibliotecario / administrador).

    El proyecto original no tenía autenticación: cualquiera podía crear,
    editar o borrar libros y socios. Se añade un modelo de usuario con
    contraseña hasheada (scrypt/werkzeug) y control de acceso por rol.
    """
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="librarian")  # admin | librarian
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


class Member(db.Model):
    __tablename__ = "members"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False, unique=True, index=True)
    registered_on = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    outstanding_debt = db.Column(db.Float, nullable=False, default=0)
    amount_spent = db.Column(db.Float, nullable=False, default=0)

    transactions = db.relationship("Transaction", back_populates="member")

    def __repr__(self):
        return f"<Member {self.id} {self.name}>"


class Book(db.Model):
    __tablename__ = "books"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False, index=True)
    author = db.Column(db.String(255), nullable=False, index=True)
    average_rating = db.Column(db.Float, nullable=True)
    isbn = db.Column(db.String(13), nullable=True, index=True)
    isbn13 = db.Column(db.String(13), nullable=True, index=True)
    language_code = db.Column(db.String(10), nullable=True)
    num_pages = db.Column(db.Integer, nullable=True)
    ratings_count = db.Column(db.Integer, nullable=False, default=0)
    text_reviews_count = db.Column(db.Integer, nullable=False, default=0)
    publication_date = db.Column(db.Date, nullable=True)
    publisher = db.Column(db.String(255), nullable=True)
    total_quantity = db.Column(db.Integer, nullable=False, default=1)
    available_quantity = db.Column(db.Integer, nullable=False, default=1)
    rented_count = db.Column(db.Integer, nullable=False, default=0)

    # --- Soporte MARC21 ---
    # Registro MARC21 completo asociado al libro, almacenado como MARCXML.
    # Permite importar catálogos MARC21 (.mrc / .xml) y volver a exportar
    # cada libro como un registro MARC21 válido (ISO 2709 o MARCXML).
    marc_control_number = db.Column(db.String(50), nullable=True, index=True)  # campo 001
    marc_xml = db.Column(db.Text, nullable=True)  # registro MARCXML completo (si procede de import)

    transactions = db.relationship("Transaction", back_populates="book")

    def __repr__(self):
        return f"<Book {self.id} {self.title}>"


class Transaction(db.Model):
    __tablename__ = "transactions"

    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey("books.id"), nullable=False, index=True)
    member_id = db.Column(db.Integer, db.ForeignKey("members.id"), nullable=False, index=True)
    per_day_fee = db.Column(db.Float, nullable=False)
    borrowed_on = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    returned_on = db.Column(db.DateTime, nullable=True)
    total_charge = db.Column(db.Float, nullable=True)
    amount_paid = db.Column(db.Float, nullable=True)

    book = db.relationship("Book", back_populates="transactions")
    member = db.relationship("Member", back_populates="transactions")

    @property
    def days_borrowed(self) -> int:
        end = self.returned_on or datetime.utcnow()
        return max((end - self.borrowed_on).days, 0)
