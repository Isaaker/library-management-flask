from datetime import date

from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import (
    StringField, FloatField, IntegerField, DateField, SelectField,
    PasswordField, BooleanField, EmailField,
)
from wtforms import validators as v


class LoginForm(FlaskForm):
    username = StringField("Usuario", [v.InputRequired(), v.Length(min=3, max=80)])
    password = PasswordField("Contraseña", [v.InputRequired()])
    remember = BooleanField("Recordarme")


class RegisterForm(FlaskForm):
    username = StringField("Usuario", [v.InputRequired(), v.Length(min=3, max=80),
                                        v.Regexp(r"^[A-Za-z0-9_.-]+$", message="Solo letras, números, punto, guion y guion bajo")])
    email = EmailField("Email", [v.InputRequired(), v.Email(), v.Length(max=255)])
    password = PasswordField("Contraseña", [v.InputRequired(), v.Length(min=10, max=128,
                              message="La contraseña debe tener al menos 10 caracteres")])
    confirm = PasswordField("Confirmar contraseña", [v.InputRequired(), v.EqualTo("password", message="Las contraseñas no coinciden")])


class AddMemberForm(FlaskForm):
    name = StringField("Nombre", [v.InputRequired(), v.Length(min=1, max=50)])
    email = EmailField("Email", [v.InputRequired(), v.Email(), v.Length(min=6, max=120)])


class AddBookForm(FlaskForm):
    title = StringField("Título", [v.InputRequired(), v.Length(min=1, max=255)])
    author = StringField("Autor(es)", [v.InputRequired(), v.Length(min=1, max=255)])
    average_rating = FloatField("Valoración media", [v.Optional(), v.NumberRange(min=0, max=5)])
    isbn = StringField("ISBN", [v.Optional(), v.Length(min=10, max=13)])
    isbn13 = StringField("ISBN13", [v.Optional(), v.Length(min=13, max=13)])
    language_code = StringField("Idioma", [v.Optional(), v.Length(max=10)])
    num_pages = IntegerField("Nº de páginas", [v.Optional(), v.NumberRange(min=1)])
    ratings_count = IntegerField("Nº de valoraciones", [v.Optional(), v.NumberRange(min=0)])
    text_reviews_count = IntegerField("Nº de reseñas", [v.Optional(), v.NumberRange(min=0)])
    publication_date = DateField("Fecha de publicación", [v.Optional()])
    publisher = StringField("Editorial", [v.Optional(), v.Length(max=255)])
    total_quantity = IntegerField("Cantidad total", [v.InputRequired(), v.NumberRange(min=1)])


class ImportBooksForm(FlaskForm):
    no_of_books = IntegerField("Nº de libros*", [v.InputRequired(), v.NumberRange(min=1, max=200)])
    quantity_per_book = IntegerField("Cantidad por libro*", [v.InputRequired(), v.NumberRange(min=1, max=1000)])
    title = StringField("Título", [v.Optional(), v.Length(min=2, max=255)])
    author = StringField("Autor(es)", [v.Optional(), v.Length(min=2, max=255)])
    isbn = StringField("ISBN", [v.Optional(), v.Length(min=10, max=13)])
    publisher = StringField("Editorial", [v.Optional(), v.Length(min=2, max=255)])


class ImportMarc21Form(FlaskForm):
    marc_file = FileField("Fichero MARC21 (.mrc, .marc, .xml)", [
        FileRequired(message="Selecciona un fichero"),
        FileAllowed(["mrc", "marc", "xml", "dat"], "Solo se admiten ficheros .mrc, .marc o .xml"),
    ])
    quantity_per_book = IntegerField("Cantidad de ejemplares por libro", [v.InputRequired(), v.NumberRange(min=1, max=1000)], default=1)


class IssueBookForm(FlaskForm):
    book_id = SelectField("Libro", choices=[], coerce=int)
    member_id = SelectField("Socio", choices=[], coerce=int)
    per_day_fee = FloatField("Tarifa diaria", [v.InputRequired(), v.NumberRange(min=0.01)])


class ReturnBookForm(FlaskForm):
    amount_paid = FloatField("Importe pagado", [v.InputRequired(), v.NumberRange(min=0)])


class SearchBookForm(FlaskForm):
    title = StringField("Título", [v.Optional(), v.Length(max=255)])
    author = StringField("Autor(es)", [v.Optional(), v.Length(max=255)])
