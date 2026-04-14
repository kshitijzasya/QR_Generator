import os
from pathlib import Path

from flask import Flask

from .extensions import db, migrate
from .vault import init_vault_db


def _load_dotenv() -> None:
    """Load KEY=VALUE entries from project .env into process env."""
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if not env_file.exists():
        return

    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'").strip()
        if key and key not in os.environ:
            os.environ[key] = value


def create_app():
    _load_dotenv()
    app = Flask(__name__)
    database_uri = (os.getenv("DATABASE_URL") or "").strip()
    if not database_uri:
        database_uri = f"sqlite:///{Path(__file__).resolve().parent.parent / 'app.db'}"

    app.config["SQLALCHEMY_DATABASE_URI"] = database_uri
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    from . import models  # noqa: F401
    migrate.init_app(app, db)

    from .routes import bp

    app.register_blueprint(bp)
    return app
