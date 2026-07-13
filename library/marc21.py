"""
Soporte MARC21 para el catálogo de libros.

Usa la librería `pymarc` para:
  * Leer catálogos en formato MARC21 binario (ISO 2709, .mrc/.marc) o
    MARCXML (.xml) y convertir cada registro en un `Book`.
  * Exportar un `Book` de la biblioteca como un registro MARC21 válido
    (tanto en binario como en MARCXML), útil para intercambiar datos con
    otros sistemas bibliotecarios (ILS) que hablen MARC21/Z39.50.

Referencia de campos MARC21 bibliográficos usados:
  001 Número de control
  020 ISBN ($a = ISBN, a veces con $c precio/formato)
  100/700 Autor principal / secundarios
  245 Título ($a = título, $b = subtítulo)
  250 Edición
  260/264 Publicación (editorial $b, fecha $c)
  300 Descripción física ($a = nº de páginas)
  041 Código de idioma
"""
from __future__ import annotations

import io
import re
from datetime import date, datetime
from typing import Iterator

from pymarc import Record, Field, Subfield, marcxml
from pymarc.reader import MARCReader
from pymarc.exceptions import PymarcException

from library.models import Book


class Marc21ImportError(Exception):
    """Error controlado al parsear un fichero MARC21."""


def _extract_year(text: str | None) -> int | None:
    if not text:
        return None
    match = re.search(r"(1[5-9]\d{2}|20\d{2})", text)
    return int(match.group(1)) if match else None


def _record_to_book_kwargs(record: Record) -> dict:
    """Convierte un `pymarc.Record` en un diccionario de campos para `Book`."""
    title_field = record.get_fields("245")
    title = ""
    if title_field:
        sub_a = title_field[0].get_subfields("a")
        sub_b = title_field[0].get_subfields("b")
        title = " ".join([*(s.strip(" /:,") for s in sub_a), *(s.strip(" /:,") for s in sub_b)]).strip()
    if not title:
        title = "Sin título"

    authors = []
    for tag in ("100", "700"):
        for f in record.get_fields(tag):
            for a in f.get_subfields("a"):
                authors.append(a.strip(" ,."))
    author = ", ".join(authors) if authors else "Desconocido"

    isbn = None
    for f in record.get_fields("020"):
        for a in f.get_subfields("a"):
            candidate = re.sub(r"[^0-9Xx]", "", a)
            if candidate:
                isbn = candidate[:13]
                break
        if isbn:
            break

    publisher = None
    pub_year = None
    for tag in ("264", "260"):
        fields = record.get_fields(tag)
        if fields:
            b = fields[0].get_subfields("b")
            c = fields[0].get_subfields("c")
            publisher = b[0].strip(" ,:") if b else None
            pub_year = _extract_year(c[0] if c else None)
            break

    num_pages = None
    for f in record.get_fields("300"):
        a = f.get_subfields("a")
        if a:
            m = re.search(r"(\d+)", a[0])
            if m:
                num_pages = int(m.group(1))
        break

    language_code = None
    lang_fields = record.get_fields("041")
    if lang_fields:
        a = lang_fields[0].get_subfields("a")
        language_code = a[0][:10] if a else None
    elif record.leader and len(record.leader) >= 3:
        language_code = None

    control_number = None
    f001 = record.get_fields("001")
    if f001:
        control_number = str(f001[0].data)[:50]

    publication_date = date(pub_year, 1, 1) if pub_year else None

    return dict(
        title=title[:255],
        author=author[:255],
        isbn=(isbn or "")[:13] or None,
        isbn13=(isbn if isbn and len(isbn) == 13 else None),
        language_code=(language_code or "und")[:10],
        num_pages=num_pages,
        publication_date=publication_date,
        publisher=(publisher or "Desconocido")[:255],
        marc_control_number=control_number,
        marc_xml=marcxml.record_to_xml(record).decode("utf-8"),
    )


def parse_marc21_file(file_bytes: bytes, filename: str) -> Iterator[dict]:
    """Genera diccionarios de campos `Book` a partir de un fichero MARC21.

    Soporta tanto MARC21 binario (ISO 2709) como MARCXML, detectando el
    formato por la extensión y, si falla, por el contenido.
    """
    is_xml = filename.lower().endswith(".xml") or file_bytes.lstrip()[:1] == b"<"

    if is_xml:
        try:
            records = marcxml.parse_xml_to_array(io.BytesIO(file_bytes))
        except Exception as exc:  # pymarc puede lanzar varias excepciones XML
            raise Marc21ImportError(f"MARCXML inválido: {exc}") from exc
        for record in records:
            if record is not None:
                yield _record_to_book_kwargs(record)
        return

    try:
        reader = MARCReader(file_bytes, to_unicode=True, force_utf8=True)
        for record in reader:
            if record is None:
                continue
            yield _record_to_book_kwargs(record)
    except PymarcException as exc:
        raise Marc21ImportError(f"Fichero MARC21 inválido: {exc}") from exc


def book_to_marc_record(book: Book) -> Record:
    """Construye un `pymarc.Record` MARC21 a partir de un `Book`."""
    record = Record(force_utf8=True)
    record.leader = "00000nam a2200000 a 4500"

    record.add_field(Field(tag="001", data=book.marc_control_number or str(book.id)))

    if book.language_code:
        record.add_field(Field(tag="041", indicators=["0", " "], subfields=[Subfield("a", book.language_code)]))

    if book.isbn13 or book.isbn:
        record.add_field(Field(tag="020", indicators=[" ", " "], subfields=[Subfield("a", book.isbn13 or book.isbn)]))

    if book.author:
        record.add_field(Field(tag="100", indicators=["1", " "], subfields=[Subfield("a", book.author)]))

    title_subfields = [Subfield("a", book.title)]
    record.add_field(Field(tag="245", indicators=["1", "0"], subfields=title_subfields))

    pub_year = book.publication_date.year if isinstance(book.publication_date, date) else None
    pub_subfields = []
    if book.publisher:
        pub_subfields.append(Subfield("b", book.publisher))
    if pub_year:
        pub_subfields.append(Subfield("c", str(pub_year)))
    if pub_subfields:
        record.add_field(Field(tag="264", indicators=[" ", "1"], subfields=pub_subfields))

    if book.num_pages:
        record.add_field(
            Field(tag="300", indicators=[" ", " "], subfields=[Subfield("a", f"{book.num_pages} p.")])
        )

    record.add_field(
        Field(
            tag="942",
            indicators=[" ", " "],
            subfields=[
                Subfield("a", str(book.total_quantity)),
                Subfield("b", str(book.available_quantity)),
                Subfield("c", str(book.rented_count)),
            ],
        )
    )
    return record


def book_to_marcxml(book: Book) -> bytes:
    return marcxml.record_to_xml(book_to_marc_record(book))


def book_to_marc_binary(book: Book) -> bytes:
    return book_to_marc_record(book).as_marc()
