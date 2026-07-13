from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required
from sqlalchemy.exc import IntegrityError

from library.extensions import db
from library.forms import AddMemberForm
from library.models import Member

bp = Blueprint("members", __name__)


@bp.route("/members")
@login_required
def members():
    all_members = Member.query.order_by(Member.id).all()
    if all_members:
        return render_template("members.html", members=all_members)
    return render_template("members.html", warning="No se encontraron socios")


@bp.route("/member/<int:id>")
@login_required
def view_member(id):
    member = db.session.get(Member, id)
    if member:
        return render_template("view_member_details.html", member=member)
    return render_template("view_member_details.html", warning="Este socio no existe")


@bp.route("/add_member", methods=["GET", "POST"])
@login_required
def add_member():
    form = AddMemberForm()
    if form.validate_on_submit():
        member = Member(name=form.name.data.strip(), email=form.email.data.strip().lower())
        db.session.add(member)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("Ya existe un socio con ese email", "danger")
            return render_template("add_member.html", form=form)

        flash("Nuevo socio añadido", "success")
        return redirect(url_for("members.members"))

    return render_template("add_member.html", form=form)


@bp.route("/edit_member/<int:id>", methods=["GET", "POST"])
@login_required
def edit_member(id):
    member = db.session.get(Member, id)
    if member is None:
        flash("Este socio no existe", "danger")
        return redirect(url_for("members.members"))

    form = AddMemberForm(obj=member)
    if form.validate_on_submit():
        member.name = form.name.data.strip()
        member.email = form.email.data.strip().lower()
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("Ya existe un socio con ese email", "danger")
            return render_template("edit_member.html", form=form, member=member)

        flash("Socio actualizado", "success")
        return redirect(url_for("members.members"))

    return render_template("edit_member.html", form=form, member=member)


@bp.route("/delete_member/<int:id>", methods=["POST"])
@login_required
def delete_member(id):
    member = db.session.get(Member, id)
    if member is None:
        flash("Este socio no existe", "danger")
        return redirect(url_for("members.members"))

    try:
        db.session.delete(member)
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        flash("El socio no se pudo eliminar (tiene transacciones asociadas)", "danger")
        return redirect(url_for("members.members"))

    flash("Socio eliminado", "success")
    return redirect(url_for("members.members"))
