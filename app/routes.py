from flask import Blueprint, Response, jsonify, render_template, request

from .qr import make_qr
from .seo import generate_seo_content

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

    if use_own_key and not youtube_api_key and not bool(allow_fallback):
        return jsonify({"error": "youtube_api_key is required when use_own_key is true unless allow_fallback is enabled"}), 400

    try:
        result = generate_seo_content(
            topic=topic,
            platform=platform,
            prefer_live=bool(live),
            youtube_api_key=youtube_api_key if use_own_key else "",
            use_env_fallback=(not use_own_key) or (bool(allow_fallback) and not youtube_api_key),
            content_format=content_format,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if bool(live) and not bool(allow_fallback) and result.get("source") != "youtube-live":
        return jsonify({"error": result.get("live_error", "YouTube live fetch failed")}), 502

    return jsonify(result)
