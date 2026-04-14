from __future__ import annotations

from base64 import b64decode, b64encode
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET
import csv
import hashlib
import io
import json
import re
import zipfile

from sqlalchemy import or_

from .extensions import db
from .models import User, VaultAsset


PBKDF2_ROUNDS = 200_000


def _normalize_text(value: str) -> str:
    return (value or "").strip()


def _serialize_user(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "username": user.username,
        "name": user.name,
        "email": user.email,
        "created_at": user.created_at.isoformat() if user.created_at else "",
        "updated_at": user.updated_at.isoformat() if user.updated_at else "",
    }


def _serialize_asset_summary(asset: VaultAsset) -> dict[str, Any]:
    return {
        "id": asset.id,
        "user_id": asset.user_id,
        "title": asset.title,
        "category": asset.category,
        "is_secret": bool(asset.is_secret),
        "secret_hint": asset.secret_hint,
        "source_type": asset.source_type,
        "import_batch": asset.import_batch,
        "created_at": asset.created_at.isoformat() if asset.created_at else "",
        "updated_at": asset.updated_at.isoformat() if asset.updated_at else "",
    }


def _derive_secret_hash(secret_key: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", secret_key.encode("utf-8"), salt, PBKDF2_ROUNDS, dklen=32)


def _stream_cipher(data: bytes, secret_key: str, salt: bytes) -> bytes:
    key_material = _derive_secret_hash(secret_key, salt)
    output = bytearray()
    counter = 0
    while len(output) < len(data):
        block = hashlib.sha256(key_material + salt + counter.to_bytes(4, "big")).digest()
        output.extend(block)
        counter += 1
    return bytes(a ^ b for a, b in zip(data, output[: len(data)]))


def _encrypt_content(content: str, secret_key: str) -> tuple[str, str, str]:
    salt = hashlib.sha256(f"{secret_key}:{content}".encode("utf-8")).digest()[:16]
    encrypted = _stream_cipher(content.encode("utf-8"), secret_key, salt)
    secret_hash = _derive_secret_hash(secret_key, salt)
    return b64encode(salt).decode("ascii"), b64encode(secret_hash).decode("ascii"), b64encode(encrypted).decode("ascii")


def _decrypt_content(secret_key: str, salt_text: str, hash_text: str, cipher_text: str) -> str:
    salt = b64decode(salt_text.encode("ascii"))
    expected_hash = b64decode(hash_text.encode("ascii"))
    if _derive_secret_hash(secret_key, salt) != expected_hash:
        raise ValueError("Invalid secret key")
    cipher_bytes = b64decode(cipher_text.encode("ascii"))
    plain = _stream_cipher(cipher_bytes, secret_key, salt)
    return plain.decode("utf-8")


def _to_secret_payload(content: str, is_secret: bool, secret_key: str) -> tuple[str, str, str, str]:
    payload = {"content": content}
    secret_salt = ""
    secret_hash = ""
    if is_secret:
        secret_salt, secret_hash, encrypted = _encrypt_content(content, secret_key)
        payload = {"content": encrypted}
    return json.dumps(payload), secret_salt, secret_hash, content


def _asset_or_404(asset_id: int) -> VaultAsset:
    asset = db.session.get(VaultAsset, asset_id)
    if asset is None:
        raise ValueError("Vault entry not found")
    return asset


def _user_or_404(user_id: int) -> User:
    user = db.session.get(User, user_id)
    if user is None:
        raise ValueError("User not found")
    return user


def _is_email(value: str) -> bool:
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value))


def init_vault_db() -> None:
    # Schema is managed through Flask-Migrate migrations.
    return None


def find_user_by_identifier(identifier: str) -> dict[str, Any] | None:
    clean_identifier = _normalize_text(identifier)
    if not clean_identifier:
      raise ValueError("Email or username is required")

    user = User.query.filter(or_(User.email == clean_identifier, User.username == clean_identifier)).first()
    return _serialize_user(user) if user else None


def create_user(username: str, name: str, email: str, password: str) -> dict[str, Any]:
    clean_username = _normalize_text(username)
    clean_name = _normalize_text(name)
    clean_email = _normalize_text(email)
    clean_password = _normalize_text(password)

    if not clean_username:
        raise ValueError("Username is required")
    if not clean_email:
        raise ValueError("Email is required")
    if not clean_password:
        raise ValueError("Password is required")

    existing = User.query.filter(or_(User.email == clean_email, User.username == clean_username)).first()
    if existing is not None:
        raise ValueError("User already exists")

    user = User(username=clean_username, name=clean_name, email=clean_email, password=clean_password)
    db.session.add(user)
    db.session.commit()
    return _serialize_user(user)


def find_or_create_user(identifier: str, username: str = "", name: str = "", email: str = "", password: str = "") -> dict[str, Any]:
    existing = find_user_by_identifier(identifier)
    if existing:
        return {"user": existing, "created": False}

    clean_identifier = _normalize_text(identifier)
    generated_username = _normalize_text(username) or (clean_identifier.split("@", 1)[0] if _is_email(clean_identifier) else clean_identifier)
    generated_email = _normalize_text(email) or (clean_identifier if _is_email(clean_identifier) else f"{clean_identifier}@vault.local")
    user = create_user(username=generated_username, name=name, email=generated_email, password=password or "vault-user")
    return {"user": user, "created": True}


def list_vault_entries(user_id: int) -> list[dict[str, Any]]:
    _user_or_404(user_id)
    assets = VaultAsset.query.filter_by(user_id=user_id).order_by(VaultAsset.updated_at.desc(), VaultAsset.id.desc()).all()
    return [_serialize_asset_summary(asset) for asset in assets]


def create_vault_entry(
    user_id: int,
    title: str,
    category: str,
    content: str,
    is_secret: bool = False,
    secret_key: str = "",
    secret_hint: str = "",
    source_type: str = "manual",
    import_batch: str = "",
) -> dict[str, Any]:
    _user_or_404(user_id)

    clean_title = _normalize_text(title)
    clean_category = _normalize_text(category) or "note"
    clean_content = _normalize_text(content)
    clean_hint = _normalize_text(secret_hint)
    clean_secret_key = _normalize_text(secret_key)

    if not clean_title:
        raise ValueError("Title is required")
    if not clean_content:
        raise ValueError("Content is required")
    generated_secret_key = clean_secret_key
    if is_secret and not generated_secret_key:
        generated_secret_key = hashlib.sha256(f"{clean_title}:{clean_content}".encode("utf-8")).hexdigest()[:16]

    secret_payload, secret_salt, secret_key_hash, plain_content = _to_secret_payload(clean_content, bool(is_secret), generated_secret_key)

    asset = VaultAsset(
        user_id=user_id,
        title=clean_title,
        category=clean_category,
        is_secret=bool(is_secret),
        secret_hint=clean_hint,
        secret_salt=secret_salt,
        secret_key_hash=secret_key_hash,
        secret=secret_payload,
        source_type=source_type,
        import_batch=import_batch,
    )
    db.session.add(asset)
    db.session.commit()

    summary = _serialize_asset_summary(asset)
    if is_secret:
        summary["generated_secret_key"] = generated_secret_key
    else:
        summary["content"] = plain_content
    return summary


def reveal_vault_entry(asset_id: int, secret_key: str = "") -> dict[str, Any]:
    asset = _asset_or_404(asset_id)
    payload = json.loads(asset.secret or "{}")
    content = str(payload.get("content", ""))
    if asset.is_secret:
        clean_secret_key = _normalize_text(secret_key)
        if not clean_secret_key:
            raise ValueError("Secret key is required")
        content = _decrypt_content(clean_secret_key, asset.secret_salt, asset.secret_key_hash, content)

    summary = _serialize_asset_summary(asset)
    summary["content"] = content
    return summary


def update_vault_entry(
    asset_id: int,
    title: str,
    category: str,
    content: str,
    is_secret: bool = False,
    secret_key: str = "",
    secret_hint: str = "",
) -> dict[str, Any]:
    asset = _asset_or_404(asset_id)
    was_secret = bool(asset.is_secret)

    clean_title = _normalize_text(title)
    clean_category = _normalize_text(category) or "note"
    clean_content = _normalize_text(content)
    clean_hint = _normalize_text(secret_hint)
    clean_secret_key = _normalize_text(secret_key)

    if not clean_title:
        raise ValueError("Title is required")
    if not clean_content:
        raise ValueError("Content is required")

    if was_secret and not clean_secret_key:
        raise ValueError("Secret key is required to update this entry")

    next_secret_key = clean_secret_key
    if bool(is_secret) and not next_secret_key:
        next_secret_key = hashlib.sha256(f"{clean_title}:{clean_content}".encode("utf-8")).hexdigest()[:16]

    secret_payload, secret_salt, secret_key_hash, plain_content = _to_secret_payload(clean_content, bool(is_secret), next_secret_key)

    asset.title = clean_title
    asset.category = clean_category
    asset.is_secret = bool(is_secret)
    asset.secret_hint = clean_hint
    asset.secret_salt = secret_salt
    asset.secret_key_hash = secret_key_hash
    asset.secret = secret_payload
    db.session.add(asset)
    db.session.commit()

    summary = _serialize_asset_summary(asset)
    if asset.is_secret:
        if not was_secret and not clean_secret_key:
            summary["generated_secret_key"] = next_secret_key
    else:
        summary["content"] = plain_content
    return summary


def delete_vault_entry(asset_id: int, secret_key: str = "") -> dict[str, Any]:
    asset = _asset_or_404(asset_id)

    if asset.is_secret:
        clean_secret_key = _normalize_text(secret_key)
        if not clean_secret_key:
            raise ValueError("Secret key is required")
        payload = json.loads(asset.secret or "{}")
        _decrypt_content(clean_secret_key, asset.secret_salt, asset.secret_key_hash, str(payload.get("content", "")))

    title = asset.title
    db.session.delete(asset)
    db.session.commit()
    return {"deleted": True, "id": asset_id, "title": title}


def _safe_title_from_values(values: list[str], fallback: str) -> str:
    for value in values:
        if _normalize_text(value):
            return _normalize_text(value)[:120]
    return fallback


def _rows_to_entries(rows: list[dict[str, Any]], user_id: int, fallback_category: str, batch_id: str) -> list[dict[str, Any]]:
    created: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        normalized = {str(key): "" if value is None else str(value) for key, value in row.items()}
        title = _safe_title_from_values(
            [normalized.get("title", ""), normalized.get("name", ""), normalized.get("label", ""), normalized.get("url", ""), normalized.get("link", "")],
            f"Imported entry {index}",
        )
        content = "\n".join(f"{key}: {value}" for key, value in normalized.items() if _normalize_text(value))
        if not content:
            continue
        created.append(
            create_vault_entry(
                user_id=user_id,
                title=title,
                category=fallback_category,
                content=content,
                is_secret=False,
                source_type="import",
                import_batch=batch_id,
            )
        )
    return created


def _parse_csv_bytes(data: bytes) -> list[dict[str, Any]]:
    text = data.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames:
        return [dict(row) for row in reader]
    simple_reader = csv.reader(io.StringIO(text))
    return [{"value": ", ".join(row)} for row in simple_reader if row]


def _parse_json_bytes(data: bytes) -> list[dict[str, Any]]:
    payload = json.loads(data.decode("utf-8"))
    if isinstance(payload, list):
        return [item if isinstance(item, dict) else {"value": item} for item in payload]
    if isinstance(payload, dict):
        return [payload]
    return [{"value": payload}]


def _parse_plaintext_bytes(data: bytes) -> list[dict[str, Any]]:
    text = data.decode("utf-8", errors="replace").strip()
    chunks = [chunk.strip() for chunk in text.split("\n\n") if chunk.strip()]
    return [{"value": chunk} for chunk in chunks]


def _xlsx_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    values: list[str] = []
    for node in root.findall("x:si", namespace):
        text_parts = [item.text or "" for item in node.findall(".//x:t", namespace)]
        values.append("".join(text_parts))
    return values


def _parse_xlsx_bytes(data: bytes) -> list[dict[str, Any]]:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        shared_strings = _xlsx_shared_strings(archive)
        sheet_names = sorted(name for name in archive.namelist() if name.startswith("xl/worksheets/sheet") and name.endswith(".xml"))
        rows: list[dict[str, Any]] = []
        namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        for sheet_name in sheet_names:
            root = ET.fromstring(archive.read(sheet_name))
            for row in root.findall(".//x:sheetData/x:row", namespace):
                values: list[str] = []
                for cell in row.findall("x:c", namespace):
                    cell_type = cell.attrib.get("t", "")
                    value_node = cell.find("x:v", namespace)
                    raw = value_node.text if value_node is not None else ""
                    if cell_type == "s" and raw.isdigit():
                        idx = int(raw)
                        values.append(shared_strings[idx] if idx < len(shared_strings) else "")
                    else:
                        values.append(raw or "")
                if any(_normalize_text(item) for item in values):
                    rows.append({f"col_{index + 1}": value for index, value in enumerate(values)})
        return rows


def _parse_docx_bytes(data: bytes) -> list[dict[str, Any]]:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        document_xml = archive.read("word/document.xml")
    root = ET.fromstring(document_xml)
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:p", namespace):
        parts = [node.text or "" for node in paragraph.findall(".//w:t", namespace)]
        text = "".join(parts).strip()
        if text:
            paragraphs.append(text)
    return [{"value": "\n".join(paragraphs)}] if paragraphs else []


def import_vault_file(user_id: int, filename: str, file_bytes: bytes, category: str = "imported") -> dict[str, Any]:
    _user_or_404(user_id)
    clean_name = _normalize_text(filename)
    if not clean_name:
        raise ValueError("Filename is required")
    if not file_bytes:
        raise ValueError("File is empty")

    lower_name = clean_name.lower()
    if lower_name.endswith(".csv"):
        rows = _parse_csv_bytes(file_bytes)
    elif lower_name.endswith(".json"):
        rows = _parse_json_bytes(file_bytes)
    elif lower_name.endswith(".txt") or lower_name.endswith(".md"):
        rows = _parse_plaintext_bytes(file_bytes)
    elif lower_name.endswith(".xlsx"):
        rows = _parse_xlsx_bytes(file_bytes)
    elif lower_name.endswith(".docx"):
        rows = _parse_docx_bytes(file_bytes)
    else:
        raise ValueError("Unsupported import file. Use csv, json, txt, md, xlsx, or docx")

    batch_id = hashlib.sha1(f"{clean_name}:{user_id}".encode("utf-8")).hexdigest()[:12]
    created = _rows_to_entries(rows, user_id=user_id, fallback_category=_normalize_text(category) or "imported", batch_id=batch_id)
    if not created:
        raise ValueError("No usable rows found in import file")

    return {
        "batch_id": batch_id,
        "created_count": len(created),
        "entries": created,
        "source_file": clean_name,
    }
