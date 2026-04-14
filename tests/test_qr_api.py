from conftest import make_client, make_logo_bytes


def test_qr_png():
    client = make_client()
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
    client = make_client()
    resp = client.post("/api/qr", json={"data": "hello", "format": "svg"})
    assert resp.status_code == 200
    assert resp.mimetype == "image/svg+xml"
    assert b"<svg" in resp.data[:200]


def test_qr_preview_returns_png_inline():
    client = make_client()
    resp = client.post(
        "/api/qr/preview",
        data={"data": "hello", "qr_color": "#112233", "border_color": "#000000"},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    assert resp.mimetype == "image/png"
    assert resp.data[:4] == b"\x89PNG"


def test_qr_png_with_logo_upload():
    client = make_client()
    resp = client.post(
        "/api/qr",
        data={
            "data": "hello",
            "format": "png",
            "logo": (make_logo_bytes(), "logo.png"),
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    assert resp.mimetype == "image/png"


def test_svg_with_logo_returns_400():
    client = make_client()
    resp = client.post(
        "/api/qr",
        data={
            "data": "hello",
            "format": "svg",
            "logo": (make_logo_bytes(), "logo.png"),
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400


def test_qr_api_requires_data():
    client = make_client()
    resp = client.post("/api/qr", json={"data": "", "format": "png"})
    assert resp.status_code == 400
