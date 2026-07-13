from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user

from library.extensions import db, limiter
from library.forms import LoginForm, RegisterForm
from library.models import User

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")  # mitiga fuerza bruta sobre credenciales
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data.strip()).first()
        # Mensaje de error genérico a propósito: no revelar si fue el
        # usuario o la contraseña lo que falló (evita enumeración de usuarios).
        if user is None or not user.is_active or not user.check_password(form.password.data):
            flash("Usuario o contraseña incorrectos", "danger")
            return render_template("auth/login.html", form=form)

        login_user(user, remember=form.remember.data)
        flash(f"Bienvenido/a, {user.username}", "success")
        next_url = request.args.get("next")
        # Solo se redirige a rutas relativas internas, nunca a URLs externas
        # (evita ataques de "open redirect").
        if next_url and next_url.startswith("/"):
            return redirect(next_url)
        return redirect(url_for("main.index"))

    return render_template("auth/login.html", form=form)


@bp.route("/register", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def register():
    # El primer usuario registrado se convierte en administrador; a partir de
    # ahí, solo un administrador autenticado puede dar de alta nuevas cuentas.
    has_users = User.query.first() is not None
    if has_users and not (current_user.is_authenticated and current_user.is_admin):
        flash("El registro público está deshabilitado. Contacta con un administrador.", "warning")
        return redirect(url_for("auth.login"))

    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter((User.username == form.username.data) | (User.email == form.email.data)).first():
            flash("El usuario o email ya existe", "danger")
            return render_template("auth/register.html", form=form)

        user = User(
            username=form.username.data.strip(),
            email=form.email.data.strip().lower(),
            role="admin" if not has_users else "librarian",
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash("Cuenta creada. Ya puedes iniciar sesión.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html", form=form)


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Sesión cerrada", "success")
    return redirect(url_for("auth.login"))
