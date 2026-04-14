from flask import Blueprint, Response, jsonify, render_template, request

from .asset_converter import convert_page_structure
from .assets import analyze_page_assets
from .qr import make_qr
from .seo import generate_seo_content
from .code import generate_code_content
from .vault import create_user, create_vault_entry, delete_vault_entry, find_or_create_user, find_user_by_identifier, import_vault_file, list_vault_entries, reveal_vault_entry, update_vault_entry

bp = Blueprint("main", __name__)


def _get_payload_data(req) -> dict:
    if req.is_json:
        payload = req.get_json(silent=True) or {}
        return {
            "data": payload.get("data", ""),
            "format": payload.get("format", ""),
            "qr_color": payload.get("qr_color", ""),
            "border_color": payload.get("border_color", ""),
            "logo_bytes": None,
        }

    logo_file = req.files.get("logo")
    logo_bytes = logo_file.read() if logo_file and logo_file.filename else None
    return {
        "data": req.form.get("data", ""),
        "format": req.form.get("format", ""),
        "qr_color": req.form.get("qr_color", ""),
        "border_color": req.form.get("border_color", ""),
        "logo_bytes": logo_bytes,
    }


@bp.route("/")
def index():
    return render_template("index.html")

@bp.route("/seo")
def seo():
    return render_template("seo.html")


@bp.route("/code")
def code():
    return render_template("code.html")


@bp.route("/assets")
def assets():
    return render_template("assets.html")


@bp.route("/vault")
def vault():
    return render_template("vault.html")


@bp.route("/api/qr", methods=["POST"])
def qr_api():
    payload = _get_payload_data(request)
    data = payload["data"]
    fmt = payload["format"]

    if not data:
        return jsonify({"error": "data is required"}), 400

    try:
        buffer, mime = make_qr(
            data=data,
            fmt=fmt,
            qr_color=payload["qr_color"],
            border_color=payload["border_color"],
            logo_bytes=payload["logo_bytes"],
        )
    except ValueError as exc:
        return jsonify({"error": str(exc).lower()}), 400

    file_ext = (fmt or "png").lower()
    if file_ext == "jpg":
        file_ext = "jpeg"
    filename = f"qrcode.{file_ext}"
    headers = {"Content-Disposition": f"attachment; filename=\"{filename}\""}
    return Response(buffer.getvalue(), mimetype=mime, headers=headers)


@bp.route("/api/qr/preview", methods=["POST"])
def qr_preview_api():
    payload = _get_payload_data(request)
    if not payload["data"]:
        return jsonify({"error": "data is required"}), 400

    try:
        # Preview is always returned as PNG so it can be rendered directly in UI.
        buffer, mime = make_qr(
            data=payload["data"],
            fmt="png",
            qr_color=payload["qr_color"],
            border_color=payload["border_color"],
            logo_bytes=payload["logo_bytes"],
        )
    except ValueError as exc:
        return jsonify({"error": str(exc).lower()}), 400

    return Response(buffer.getvalue(), mimetype=mime)


@bp.route("/api/seo/generate", methods=["POST"])
def seo_generate_api():
    payload = request.get_json(silent=True) or {}
    topic = payload.get("topic", "")
    platform = payload.get("platform", "youtube")
    live = payload.get("live", True)
    content_format = payload.get("content_format", "long")
    allow_fallback = payload.get("allow_fallback", False)
    use_own_key = bool(payload.get("use_own_key", False))
    youtube_api_key = (payload.get("youtube_api_key", "") or "").strip()
    is_youtube = str(platform).strip().lower() == "youtube"

    if is_youtube and use_own_key and not youtube_api_key and not bool(allow_fallback):
        return jsonify({"error": "youtube_api_key is required when use_own_key is true unless allow_fallback is enabled"}), 400

    try:
        result = generate_seo_content(
            topic=topic,
            platform=platform,
            prefer_live=bool(live),
            youtube_api_key=youtube_api_key if is_youtube and use_own_key else "",
            use_env_fallback=(not is_youtube) or (not use_own_key) or (bool(allow_fallback) and not youtube_api_key),
            content_format=content_format,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if is_youtube and bool(live) and not bool(allow_fallback) and result.get("source") != "youtube-live":
        return jsonify({"error": result.get("live_error", "YouTube live fetch failed")}), 502

    return jsonify(result)

@bp.route("/api/code/generate", methods=["POST"])
def code_generate_api():
    payload = request.get_json(silent=True) or {}
    task = payload.get("task", "")
    framework = payload.get("framework")
    language = payload.get("language")
    conversation_id = payload.get("conversation_id", "")
    fresh_conversation = bool(payload.get("fresh_conversation", False))

    if not task:
        return jsonify({"error": "Prompt not provided for context"}), 400

    try:
        result = generate_code_content(
            prompt=task,
            framework=framework,
            language=language,
            conversation_id=conversation_id,
            fresh_conversation=fresh_conversation,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 502

    if result is None:
        return jsonify({"error": "Code generation is not configured"}), 503
    
    return jsonify(result)


@bp.route("/api/assets/analyze", methods=["POST"])
def assets_analyze_api():
    payload = request.get_json(silent=True) or {}

    try:
        result = analyze_page_assets(
            url=payload.get("url", ""),
            html=payload.get("html", ""),
            base_url=payload.get("base_url", ""),
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 502

    return jsonify(result)


@bp.route("/api/assets/convert", methods=["POST"])
def assets_convert_api():
    payload = request.get_json(silent=True) or {}

    try:
        result = convert_page_structure(
            html=payload.get("html", ""),
            target_stack=payload.get("target_stack", ""),
            notes=payload.get("notes", ""),
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 502

    return jsonify(result)


@bp.route("/api/vault/entries", methods=["GET"])
def vault_entries_list_api():
    user_id = request.args.get("user_id", type=int)
    if not user_id:
        return jsonify({"error": "user_id is required"}), 400
    try:
        result = list_vault_entries(user_id)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404
    return jsonify(result)


@bp.route("/api/vault/users/lookup", methods=["GET"])
def vault_user_lookup_api():
    identifier = request.args.get("identifier", "")
    try:
        result = find_user_by_identifier(identifier)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"user": result})


@bp.route("/api/vault/users", methods=["POST"])
def vault_user_create_api():
    payload = request.get_json(silent=True) or {}
    try:
        result = create_user(
            username=payload.get("username", ""),
            name=payload.get("name", ""),
            email=payload.get("email", ""),
            password=payload.get("password", ""),
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(result), 201


@bp.route("/api/vault/session", methods=["POST"])
def vault_user_session_api():
    payload = request.get_json(silent=True) or {}
    try:
        result = find_or_create_user(
            identifier=payload.get("identifier", ""),
            username=payload.get("username", ""),
            name=payload.get("name", ""),
            email=payload.get("email", ""),
            password=payload.get("password", ""),
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(result)


@bp.route("/api/vault/entries", methods=["POST"])
def vault_entries_create_api():
    payload = request.get_json(silent=True) or {}
    try:
        result = create_vault_entry(
            user_id=int(payload.get("user_id", 0) or 0),
            title=payload.get("title", ""),
            category=payload.get("category", ""),
            content=payload.get("content", ""),
            is_secret=bool(payload.get("is_secret", False)),
            secret_key=payload.get("secret_key", "") or payload.get("password", ""),
            secret_hint=payload.get("secret_hint", ""),
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(result), 201


@bp.route("/api/vault/entries/<int:entry_id>/reveal", methods=["POST"])
def vault_entry_reveal_api(entry_id: int):
    payload = request.get_json(silent=True) or {}
    try:
        result = reveal_vault_entry(entry_id, secret_key=payload.get("secret_key", "") or payload.get("password", ""))
    except ValueError as exc:
        status_code = 404 if "not found" in str(exc).lower() else 400
        return jsonify({"error": str(exc)}), status_code
    return jsonify(result)


@bp.route("/api/vault/entries/<int:entry_id>", methods=["PUT"])
def vault_entry_update_api(entry_id: int):
    payload = request.get_json(silent=True) or {}
    try:
        result = update_vault_entry(
            asset_id=entry_id,
            title=payload.get("title", ""),
            category=payload.get("category", ""),
            content=payload.get("content", ""),
            is_secret=bool(payload.get("is_secret", False)),
            secret_key=payload.get("secret_key", "") or payload.get("password", ""),
            secret_hint=payload.get("secret_hint", ""),
        )
    except ValueError as exc:
        status_code = 404 if "not found" in str(exc).lower() else 400
        return jsonify({"error": str(exc)}), status_code
    return jsonify(result)


@bp.route("/api/vault/entries/<int:entry_id>", methods=["DELETE"])
def vault_entry_delete_api(entry_id: int):
    payload = request.get_json(silent=True) or {}
    try:
        result = delete_vault_entry(entry_id, secret_key=payload.get("secret_key", "") or payload.get("password", ""))
    except ValueError as exc:
        status_code = 404 if "not found" in str(exc).lower() else 400
        return jsonify({"error": str(exc)}), status_code
    return jsonify(result)


@bp.route("/api/vault/import", methods=["POST"])
def vault_import_api():
    file_obj = request.files.get("file")
    category = request.form.get("category", "imported")
    user_id = request.form.get("user_id", type=int)
    if file_obj is None or not file_obj.filename:
        return jsonify({"error": "File is required"}), 400
    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    try:
        result = import_vault_file(user_id, file_obj.filename, file_obj.read(), category=category)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify(result), 201
