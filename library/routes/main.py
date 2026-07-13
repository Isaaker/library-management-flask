from flask import Blueprint, render_template
from flask_login import login_required

from library.cache import cached_json
from library.models import Member, Book

bp = Blueprint("main", __name__)

REPORTS_CACHE_KEY = "reports:top5"
REPORTS_CACHE_TTL = 30  # segundos: dato agregado, no necesita estar al segundo


@bp.route("/")
@login_required
def index():
    return render_template("home.html")


@bp.route("/reports")
@login_required
def reports():
    def build():
        members = Member.query.order_by(Member.amount_spent.desc()).limit(5).all()
        books = Book.query.order_by(Book.rented_count.desc()).limit(5).all()
        return {
            "members": [
                {"id": m.id, "name": m.name, "amount_spent": m.amount_spent} for m in members
            ],
            "books": [
                {
                    "id": b.id, "title": b.title, "author": b.author,
                    "total_quantity": b.total_quantity,
                    "available_quantity": b.available_quantity,
                    "rented_count": b.rented_count,
                }
                for b in books
            ],
        }

    # Los resultados se cachean en Redis (si está configurado) durante
    # REPORTS_CACHE_TTL segundos; si no hay Redis, se consulta la base de
    # datos directamente en cada petición sin ningún cambio de comportamiento.
    data = cached_json(REPORTS_CACHE_KEY, REPORTS_CACHE_TTL, build)

    warning = ""
    if not data["members"]:
        warning += "No se encontraron socios. "
    if not data["books"]:
        warning += "No se encontraron libros."
    return render_template("reports.html", members=data["members"], books=data["books"], warning=warning)
