import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from library import create_app
from library.config import Config
from library.extensions import db
from library.models import User, Member, Book


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def _login(client, app, username="admin", password="supersecretpw"):
    with app.app_context():
        user = User(username=username, email=f"{username}@example.com", role="admin")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
    return client.post("/login", data={"username": username, "password": password}, follow_redirects=True)


def test_home_requires_login(client):
    resp = client.get("/", follow_redirects=True)
    assert resp.status_code == 200
    assert b"Iniciar sesi\xc3\xb3n" in resp.data


def test_login_and_view_books(client, app):
    resp = _login(client, app)
    assert resp.status_code == 200

    resp = client.get("/books")
    assert resp.status_code == 200
    assert "No se encontraron libros".encode("utf-8") in resp.data


def test_add_book(client, app):
    _login(client, app)
    resp = client.post(
        "/add_book",
        data={
            "title": "El Quijote",
            "author": "Miguel de Cervantes",
            "total_quantity": "3",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    with app.app_context():
        assert Book.query.count() == 1
        book = Book.query.first()
        assert book.available_quantity == 3


def test_wrong_password_rejected(client, app):
    with app.app_context():
        user = User(username="bob", email="bob@example.com", role="librarian")
        user.set_password("correcthorsebatterystaple")
        db.session.add(user)
        db.session.commit()

    resp = client.post("/login", data={"username": "bob", "password": "wrong"}, follow_redirects=True)
    assert b"incorrectos" in resp.data
