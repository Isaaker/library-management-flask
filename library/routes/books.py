import urllib.parse

import requests
from flask import Blueprint, render_template, redirect, url_for, flash, current_app
from flask_login import login_required
from sqlalchemy.exc import IntegrityError

from library.extensions import db
from library.forms import AddBookForm, ImportBooksForm, SearchBookForm
from library.models import Book

bp = Blueprint("books", __name__)


@bp.route("/books")
@login_required
def books():
    all_books = Book.query.order_by(Book.id).all()
    if all_books:
        return render_template("books.html", books=all_books)
    return render_template("books.html", warning="No se encontraron libros")


@bp.route("/book/<int:id>")
@login_required
def view_book(id):
    book = db.session.get(Book, id)
    if book:
        return render_template("view_book_details.html", book=book)
    return render_template("view_book_details.html", warning="Este libro no existe")


@bp.route("/add_book", methods=["GET", "POST"])
@login_required
def add_book():
    form = AddBookForm()
    if form.validate_on_submit():
        book = Book(
            title=form.title.data.strip(),
            author=form.author.data.strip(),
            average_rating=form.average_rating.data,
            isbn=form.isbn.data or None,
            isbn13=form.isbn13.data or None,
            language_code=form.language_code.data or None,
            num_pages=form.num_pages.data,
            ratings_count=form.ratings_count.data or 0,
            text_reviews_count=form.text_reviews_count.data or 0,
            publication_date=form.publication_date.data,
            publisher=form.publisher.data or None,
            total_quantity=form.total_quantity.data,
            available_quantity=form.total_quantity.data,
        )
        db.session.add(book)
        db.session.commit()
        flash("Nuevo libro añadido", "success")
        return redirect(url_for("books.books"))

    return render_template("add_book.html", form=form)


@bp.route("/edit_book/<int:id>", methods=["GET", "POST"])
@login_required
def edit_book(id):
    book = db.session.get(Book, id)
    if book is None:
        flash("Este libro no existe", "danger")
        return redirect(url_for("books.books"))

    form = AddBookForm(obj=book)
    if form.validate_on_submit():
        # El nº de ejemplares disponibles se ajusta proporcionalmente al
        # cambio en la cantidad total (igual que en el proyecto original).
        delta = form.total_quantity.data - book.total_quantity
        book.available_quantity = max(book.available_quantity + delta, 0)

        book.title = form.title.data.strip()
        book.author = form.author.data.strip()
        book.average_rating = form.average_rating.data
        book.isbn = form.isbn.data or None
        book.isbn13 = form.isbn13.data or None
        book.language_code = form.language_code.data or None
        book.num_pages = form.num_pages.data
        book.ratings_count = form.ratings_count.data or 0
        book.text_reviews_count = form.text_reviews_count.data or 0
        book.publication_date = form.publication_date.data
        book.publisher = form.publisher.data or None
        book.total_quantity = form.total_quantity.data

        db.session.commit()
        flash("Libro actualizado", "success")
        return redirect(url_for("books.books"))

    return render_template("edit_book.html", form=form, book=book)


@bp.route("/delete_book/<int:id>", methods=["POST"])
@login_required
def delete_book(id):
    book = db.session.get(Book, id)
    if book is None:
        flash("Este libro no existe", "danger")
        return redirect(url_for("books.books"))

    try:
        db.session.delete(book)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("El libro no se pudo eliminar (tiene transacciones asociadas)", "danger")
        return redirect(url_for("books.books"))

    flash("Libro eliminado", "success")
    return redirect(url_for("books.books"))


@bp.route("/import_books", methods=["GET", "POST"])
@login_required
def import_books():
    form = ImportBooksForm()
    if form.validate_on_submit():
        base_url = current_app.config["FRAPPE_LIBRARY_API"]
        params = {"page": 1}
        if form.title.data:
            params["title"] = form.title.data
        if form.author.data:
            params["author"] = form.author.data
        if form.isbn.data:
            params["isbn"] = form.isbn.data
        if form.publisher.data:
            params["publisher"] = form.publisher.data

        imported = 0
        repeated = 0
        target = form.no_of_books.data
        max_pages = 50  # cota de seguridad para evitar bucles/DoS involuntario
        page_count = 0

        while imported < target and page_count < max_pages:
            page_count += 1
            try:
                resp = requests.get(
                    base_url, params=params, timeout=10,
                )
                resp.raise_for_status()
                res = resp.json()
            except (requests.RequestException, ValueError) as exc:
                flash(f"No se pudo contactar con la API externa: {exc}", "danger")
                break

            books_page = res.get("message") or []
            if not books_page:
                break

            for raw in books_page:
                external_id = raw.get("bookID")
                exists = Book.query.filter_by(isbn13=str(raw.get("isbn13") or "")).first() if raw.get("isbn13") else None
                if exists:
                    repeated += 1
                    continue

                try:
                    pub_date = raw.get("publication_date")
                    book = Book(
                        title=str(raw.get("title", ""))[:255],
                        author=str(raw.get("authors", ""))[:255],
                        average_rating=raw.get("average_rating"),
                        isbn=str(raw.get("isbn", ""))[:13] or None,
                        isbn13=str(raw.get("isbn13", ""))[:13] or None,
                        language_code=str(raw.get("language_code", ""))[:10] or None,
                        num_pages=raw.get("  num_pages") or raw.get("num_pages"),
                        ratings_count=raw.get("ratings_count") or 0,
                        text_reviews_count=raw.get("text_reviews_count") or 0,
                        publisher=str(raw.get("publisher", ""))[:255] or None,
                        total_quantity=form.quantity_per_book.data,
                        available_quantity=form.quantity_per_book.data,
                    )
                except Exception:
                    continue

                db.session.add(book)
                imported += 1
                if imported == target:
                    break

            params["page"] += 1

        db.session.commit()

        msg = f"{imported}/{target} libros importados. "
        msg_type = "success"
        if imported != target:
            msg_type = "warning"
            msg += f"{repeated} ya existían." if repeated else "No se encontraron más coincidencias."
        flash(msg, msg_type)
        return redirect(url_for("books.books"))

    return render_template("import_books.html", form=form)


@bp.route("/search_book", methods=["GET", "POST"])
@login_required
def search_book():
    form = SearchBookForm()
    if form.validate_on_submit():
        query = Book.query
        if form.title.data:
            query = query.filter(Book.title.ilike(f"%{form.title.data}%"))
        if form.author.data:
            query = query.filter(Book.author.ilike(f"%{form.author.data}%"))
        results = query.all() if (form.title.data or form.author.data) else []

        if not results:
            return render_template("search_book.html", form=form, warning="No se encontraron resultados")

        flash("Resultados encontrados", "success")
        return render_template("search_book.html", form=form, books=results)

    return render_template("search_book.html", form=form)
