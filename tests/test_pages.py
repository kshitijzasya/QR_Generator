from conftest import make_client


def test_index_page():
    resp = make_client().get("/")
    assert resp.status_code == 200
    assert b'id="app"' in resp.data


def test_seo_page():
    resp = make_client().get("/seo")
    assert resp.status_code == 200
    assert b'id="seo-app"' in resp.data


def test_code_page():
    resp = make_client().get("/code")
    assert resp.status_code == 200
    assert b'id="code-app"' in resp.data


def test_assets_page():
    resp = make_client().get("/assets")
    assert resp.status_code == 200
    assert b'id="assets-app"' in resp.data


def test_vault_page():
    resp = make_client().get("/vault")
    assert resp.status_code == 200
    assert b'id="vault-app"' in resp.data
