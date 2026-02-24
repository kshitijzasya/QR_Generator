from flask import Blueprint, Response, jsonify, render_template, request

from .qr import make_qr

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
