from io import BytesIO

from PIL import Image

from app import create_app


def _make_logo_bytes() -> BytesIO:
    img = Image.new("RGB", (40, 40), "red")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def test_qr_png():
    app = create_app()
    client = app.test_client()
    resp = client.post(
        "/api/qr",
        json={
            "data": "hello",
            "format": "png",
            "qr_color": "#1144aa",
            "border_color": "#ff6600",
        },
    )
    assert resp.status_code == 200
    assert resp.mimetype == "image/png"
    assert resp.data[:4] == b"\x89PNG"


def test_qr_svg():
    app = create_app()
    client = app.test_client()
    resp = client.post("/api/qr", json={"data": "hello", "format": "svg"})
    assert resp.status_code == 200
    assert resp.mimetype == "image/svg+xml"
    assert b"<svg" in resp.data[:200]


def test_qr_preview_returns_png_inline():
    app = create_app()
    client = app.test_client()
    resp = client.post(
        "/api/qr/preview",
        data={"data": "hello", "qr_color": "#112233", "border_color": "#000000"},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    assert resp.mimetype == "image/png"
    assert resp.data[:4] == b"\x89PNG"


def test_qr_png_with_logo_upload():
    app = create_app()
    client = app.test_client()
    resp = client.post(
        "/api/qr",
        data={
            "data": "hello",
            "format": "png",
            "logo": (_make_logo_bytes(), "logo.png"),
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    assert resp.mimetype == "image/png"


def test_svg_with_logo_returns_400():
    app = create_app()
    client = app.test_client()
    resp = client.post(
        "/api/qr",
        data={
            "data": "hello",
            "format": "svg",
            "logo": (_make_logo_bytes(), "logo.png"),
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
