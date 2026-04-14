from io import BytesIO

from PIL import Image

from app import create_app
from app.extensions import db


def make_app():
    return create_app()


def make_client():
    return make_app().test_client()


def make_logo_bytes() -> BytesIO:
    img = Image.new("RGB", (40, 40), "red")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def make_vault_app(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test-vault.db'}")
    app = create_app()
    with app.app_context():
        db.drop_all()
        db.create_all()
    return app


def create_test_user(client):
    resp = client.post(
        "/api/vault/users",
        json={
            "username": "demo-user",
            "name": "Demo User",
            "email": "demo@example.com",
            "password": "pass-123",
        },
    )
    assert resp.status_code == 201
    return resp.get_json()
