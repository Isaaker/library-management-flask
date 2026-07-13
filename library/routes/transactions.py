from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required

from library.extensions import db
from library.cache import invalidate
from library.forms import IssueBookForm, ReturnBookForm
from library.models import Book, Member, Transaction
from library.routes.main import REPORTS_CACHE_KEY

bp = Blueprint("transactions", __name__)


@bp.route("/transactions")
@login_required
def transactions():
    all_tx = Transaction.query.order_by(Transaction.id.desc()).all()
    if all_tx:
        return render_template("transactions.html", transactions=all_tx)
    return render_template("transactions.html", warning="No se encontraron transacciones")


@bp.route("/issue_book", methods=["GET", "POST"])
@login_required
def issue_book():
    form = IssueBookForm()
    form.book_id.choices = [(b.id, b.title) for b in Book.query.order_by(Book.title).all()]
    form.member_id.choices = [(m.id, m.name) for m in Member.query.order_by(Member.name).all()]

    if not form.book_id.choices or not form.member_id.choices:
        flash("Se necesita al menos un libro y un socio para registrar un préstamo", "warning")

    if form.validate_on_submit():
        book = db.session.get(Book, form.book_id.data)
        member = db.session.get(Member, form.member_id.data)
        if book is None or member is None:
            flash("Libro o socio no válido", "danger")
            return render_template("issue_book.html", form=form)

        if book.available_quantity < 1:
            return render_template(
                "issue_book.html", form=form,
                error="No hay ejemplares disponibles de este libro",
            )

        tx = Transaction(book_id=book.id, member_id=member.id, per_day_fee=form.per_day_fee.data)
        book.available_quantity -= 1
        book.rented_count += 1

        db.session.add(tx)
        db.session.commit()
        invalidate(REPORTS_CACHE_KEY)

        flash("Libro prestado", "success")
        return redirect(url_for("transactions.transactions"))

    return render_template("issue_book.html", form=form)


@bp.route("/return_book/<int:transaction_id>", methods=["GET", "POST"])
@login_required
def return_book(transaction_id):
    tx = db.session.get(Transaction, transaction_id)
    if tx is None:
        flash("Esta transacción no existe", "danger")
        return redirect(url_for("transactions.transactions"))

    if tx.returned_on is not None:
        flash("Este libro ya fue devuelto", "warning")
        return redirect(url_for("transactions.transactions"))

    form = ReturnBookForm()
    difference = tx.days_borrowed
    total_charge = difference * tx.per_day_fee

    if form.validate_on_submit():
        transaction_debt = total_charge - form.amount_paid.data

        member = tx.member
        if member.outstanding_debt + transaction_debt > 500:
            return render_template(
                "return_book.html", form=form, total_charge=total_charge,
                difference=difference, transaction=tx,
                error="La deuda pendiente no puede superar 500",
            )

        tx.returned_on = datetime.utcnow()
        tx.total_charge = total_charge
        tx.amount_paid = form.amount_paid.data

        member.outstanding_debt += transaction_debt
        member.amount_spent += form.amount_paid.data

        tx.book.available_quantity += 1

        db.session.commit()
        invalidate(REPORTS_CACHE_KEY)

        flash("Libro devuelto", "success")
        return redirect(url_for("transactions.transactions"))

    return render_template(
        "return_book.html", form=form, total_charge=total_charge,
        difference=difference, transaction=tx,
    )
