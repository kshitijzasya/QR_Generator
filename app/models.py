from __future__ import annotations

from datetime import datetime, timezone

from .extensions import db


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False, index=True)
    name = db.Column(db.String(160), nullable=False, default="")
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password = db.Column(db.String(255), nullable=False, default="")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    assets = db.relationship("VaultAsset", back_populates="user", cascade="all, delete-orphan")


class VaultAsset(db.Model):
    __tablename__ = "vault_assets"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(120), nullable=False, default="note")
    is_secret = db.Column(db.Boolean, nullable=False, default=False)
    secret_hint = db.Column(db.String(255), nullable=False, default="")
    secret_salt = db.Column(db.Text, nullable=False, default="")
    secret_key_hash = db.Column(db.Text, nullable=False, default="")
    secret = db.Column(db.Text, nullable=False)
    source_type = db.Column(db.String(50), nullable=False, default="manual")
    import_batch = db.Column(db.String(64), nullable=False, default="")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    user = db.relationship("User", back_populates="assets")
