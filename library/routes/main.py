from flask import Blueprint, render_template
from flask_login import login_required

from library.models import Member, Book

bp = Blueprint("main", __name__)


@bp.route("/")
@login_required
def index():
    return render_template("home.html")


@bp.route("/reports")
@login_required
def reports():
    members = (
        Member.query.order_by(Member.amount_spent.desc()).limit(5).all()
    )
    books = (
        Book.query.order_by(Book.rented_count.desc()).limit(5).all()
    )
    warning = ""
    if not members:
        warning += "No se encontraron socios. "
    if not books:
        warning += "No se encontraron libros."
    return render_template("reports.html", members=members, books=books, warning=warning)
