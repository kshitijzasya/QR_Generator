import io
import zipfile

from app.models import User

from conftest import create_test_user, make_vault_app


def test_vault_create_and_reveal_public_entry(monkeypatch, tmp_path):
    app = make_vault_app(monkeypatch, tmp_path)
    client = app.test_client()
    user = create_test_user(client)

    create_resp = client.post(
        "/api/vault/entries",
        json={"user_id": user["id"], "title": "Server URL", "category": "link", "content": "https://example.com", "is_secret": False},
    )
    assert create_resp.status_code == 201
    entry = create_resp.get_json()

    reveal_resp = client.post(f"/api/vault/entries/{entry['id']}/reveal", json={})
    assert reveal_resp.status_code == 200
    payload = reveal_resp.get_json()
    assert payload["content"] == "https://example.com"


def test_vault_create_and_reveal_secret_entry(monkeypatch, tmp_path):
    app = make_vault_app(monkeypatch, tmp_path)
    client = app.test_client()
    user = create_test_user(client)
    create_resp = client.post(
        "/api/vault/entries",
        json={
            "user_id": user["id"],
            "title": "Prod credentials",
            "category": "credential",
            "content": "username: demo\npassword: secret",
            "is_secret": True,
            "secret_key": "open-sesame",
            "secret_hint": "shared phrase",
        },
    )
    assert create_resp.status_code == 201
    entry = create_resp.get_json()

    bad_resp = client.post(f"/api/vault/entries/{entry['id']}/reveal", json={"secret_key": "wrong"})
    assert bad_resp.status_code == 400

    reveal_resp = client.post(f"/api/vault/entries/{entry['id']}/reveal", json={"secret_key": "open-sesame"})
    assert reveal_resp.status_code == 200
    payload = reveal_resp.get_json()
    assert "password: secret" in payload["content"]

    password_resp = client.post(f"/api/vault/entries/{entry['id']}/reveal", json={"password": "open-sesame"})
    assert password_resp.status_code == 200


def test_vault_import_csv(monkeypatch, tmp_path):
    app = make_vault_app(monkeypatch, tmp_path)
    client = app.test_client()
    user = create_test_user(client)
    file_data = io.BytesIO(b"title,url\nHome,https://example.com\nDocs,https://docs.example.com\n")
    resp = client.post(
        "/api/vault/import",
        data={"user_id": str(user["id"]), "category": "link", "file": (file_data, "links.csv")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 201
    payload = resp.get_json()
    assert payload["created_count"] == 2


def test_vault_import_docx(monkeypatch, tmp_path):
    app = make_vault_app(monkeypatch, tmp_path)
    client = app.test_client()
    user = create_test_user(client)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "word/document.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
            <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
              <w:body>
                <w:p><w:r><w:t>Vault import doc</w:t></w:r></w:p>
                <w:p><w:r><w:t>Second paragraph</w:t></w:r></w:p>
              </w:body>
            </w:document>
            """,
        )
    buffer.seek(0)
    resp = client.post(
        "/api/vault/import",
        data={"user_id": str(user["id"]), "category": "note", "file": (buffer, "notes.docx")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 201
    payload = resp.get_json()
    assert payload["created_count"] == 1


def test_vault_user_lookup_and_db_models(monkeypatch, tmp_path):
    app = make_vault_app(monkeypatch, tmp_path)
    client = app.test_client()

    lookup_resp = client.get("/api/vault/users/lookup?identifier=demo@example.com")
    assert lookup_resp.status_code == 200
    assert lookup_resp.get_json()["user"] is None

    user = create_test_user(client)
    lookup_resp = client.get("/api/vault/users/lookup?identifier=demo@example.com")
    assert lookup_resp.status_code == 200
    assert lookup_resp.get_json()["user"]["id"] == user["id"]

    with app.app_context():
        model_user = User.query.filter_by(email="demo@example.com").first()
        assert model_user is not None


def test_vault_generates_secret_key_when_missing(monkeypatch, tmp_path):
    app = make_vault_app(monkeypatch, tmp_path)
    client = app.test_client()
    user = create_test_user(client)

    resp = client.post(
        "/api/vault/entries",
        json={
            "user_id": user["id"],
            "title": "Auto generated secret",
            "category": "credential",
            "content": "token: abc123",
            "is_secret": True,
            "secret_key": "",
        },
    )
    assert resp.status_code == 201
    payload = resp.get_json()
    assert payload["generated_secret_key"]

    reveal_resp = client.post(
        f"/api/vault/entries/{payload['id']}/reveal",
        json={"secret_key": payload["generated_secret_key"]},
    )
    assert reveal_resp.status_code == 200
    assert "token: abc123" in reveal_resp.get_json()["content"]


def test_vault_update_public_entry(monkeypatch, tmp_path):
    app = make_vault_app(monkeypatch, tmp_path)
    client = app.test_client()
    user = create_test_user(client)

    create_resp = client.post(
        "/api/vault/entries",
        json={"user_id": user["id"], "title": "Old title", "category": "note", "content": "old content", "is_secret": False},
    )
    entry = create_resp.get_json()

    update_resp = client.put(
        f"/api/vault/entries/{entry['id']}",
        json={"title": "New title", "category": "note", "content": "new content", "is_secret": False},
    )
    assert update_resp.status_code == 200
    assert update_resp.get_json()["title"] == "New title"

    reveal_resp = client.post(f"/api/vault/entries/{entry['id']}/reveal", json={})
    assert reveal_resp.status_code == 200
    assert reveal_resp.get_json()["content"] == "new content"


def test_vault_delete_secret_entry_requires_key(monkeypatch, tmp_path):
    app = make_vault_app(monkeypatch, tmp_path)
    client = app.test_client()
    user = create_test_user(client)

    create_resp = client.post(
        "/api/vault/entries",
        json={
            "user_id": user["id"],
            "title": "Delete me",
            "category": "credential",
            "content": "private token",
            "is_secret": True,
            "secret_key": "open-sesame",
        },
    )
    entry = create_resp.get_json()

    bad_delete_resp = client.delete(f"/api/vault/entries/{entry['id']}", json={"secret_key": "wrong"})
    assert bad_delete_resp.status_code == 400

    delete_resp = client.delete(f"/api/vault/entries/{entry['id']}", json={"secret_key": "open-sesame"})
    assert delete_resp.status_code == 200
    assert delete_resp.get_json()["deleted"] is True

    reveal_resp = client.post(f"/api/vault/entries/{entry['id']}/reveal", json={"secret_key": "open-sesame"})
    assert reveal_resp.status_code == 404
