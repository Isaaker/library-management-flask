from flask import Blueprint, render_template, redirect, url_for, flash, send_file, current_app, abort
from flask_login import login_required
import io

from library.extensions import db
from library.forms import ImportMarc21Form
from library.models import Book
from library.marc21 import parse_marc21_file, Marc21ImportError, book_to_marcxml, book_to_marc_binary

bp = Blueprint("marc21", __name__)

MAX_RECORDS_PER_IMPORT = 500  # cota de seguridad ante ficheros enormes


@bp.route("/marc21/import", methods=["GET", "POST"])
@login_required
def import_marc21():
    form = ImportMarc21Form()
    if form.validate_on_submit():
        upload = form.marc_file.data
        filename = upload.filename or "catalogo.mrc"
        file_bytes = upload.read()

        if not file_bytes:
            flash("El fichero está vacío", "danger")
            return render_template("import_marc21.html", form=form)

        imported = 0
        skipped = 0
        try:
            for kwargs in parse_marc21_file(file_bytes, filename):
                if imported >= MAX_RECORDS_PER_IMPORT:
                    flash(
                        f"Se alcanzó el límite de {MAX_RECORDS_PER_IMPORT} registros por importación; "
                        "divide el fichero en lotes más pequeños.",
                        "warning",
                    )
                    break

                if kwargs.get("marc_control_number"):
                    existing = Book.query.filter_by(
                        marc_control_number=kwargs["marc_control_number"]
                    ).first()
                    if existing:
                        skipped += 1
                        continue

                qty = form.quantity_per_book.data
                book = Book(total_quantity=qty, available_quantity=qty, **kwargs)
                db.session.add(book)
                imported += 1

            db.session.commit()
        except Marc21ImportError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
            return render_template("import_marc21.html", form=form)
        except Exception as exc:
            db.session.rollback()
            current_app.logger.exception("Error importando MARC21")
            flash("Error inesperado al procesar el fichero MARC21", "danger")
            return render_template("import_marc21.html", form=form)

        msg = f"{imported} registros MARC21 importados."
        if skipped:
            msg += f" {skipped} ya existían (mismo número de control 001)."
        flash(msg, "success")
        return redirect(url_for("books.books"))

    return render_template("import_marc21.html", form=form)


@bp.route("/marc21/export")
@login_required
def export_catalog():
    """Exporta todo el catálogo como un fichero MARCXML único."""
    from pymarc import marcxml as pymarc_xml

    books = Book.query.order_by(Book.id).all()
    if not books:
        flash("No hay libros en el catálogo para exportar", "warning")
        return redirect(url_for("books.books"))

    buf = io.BytesIO()
    writer = pymarc_xml.XMLWriter(buf)
    for b in books:
        from library.marc21 import book_to_marc_record
        writer.write(book_to_marc_record(b))
    writer.close(close_fh=False)
    buf.seek(0)

    return send_file(
        buf,
        mimetype="application/marcxml+xml",
        as_attachment=True,
        download_name="catalogo_marc21.xml",
    )


@bp.route("/marc21/export/<int:id>")
@login_required
def export_book(id):
    book = db.session.get(Book, id)
    if book is None:
        abort(404)

    data = book_to_marcxml(book)
    return send_file(
        io.BytesIO(data),
        mimetype="application/marcxml+xml",
        as_attachment=True,
        download_name=f"libro_{book.id}_marc21.xml",
    )
