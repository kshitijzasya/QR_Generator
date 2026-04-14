import app.asset_converter as asset_converter_module

from app.assets import analyze_page_assets
from app.asset_converter import convert_page_structure

from conftest import make_client


def test_assets_analyze_html_success():
    client = make_client()
    html = """
    <html lang="en">
      <head>
        <title>Landing Page Example</title>
        <meta name="description" content="A useful landing page description for testing this extractor output." />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="canonical" href="https://example.com/page" />
        <link rel="stylesheet" href="/styles/main.css" />
        <link rel="preload" href="/fonts/site.woff2" as="font" />
        <script src="/app.js"></script>
        <style>.hero { color: red; }</style>
      </head>
      <body>
        <h1>Main heading</h1>
        <h2>Support heading</h2>
        <p>Hello page copy for analysis.</p>
        <img src="/hero.png" alt="Hero image" loading="lazy" />
        <a href="/about">About</a>
        <a href="https://external.example.org/post">External</a>
      </body>
    </html>
    """
    resp = client.post(
        "/api/assets/analyze",
        json={"html": html, "base_url": "https://example.com/page"},
    )
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["page"]["title"] == "Landing Page Example"
    assert payload["page"]["canonical"] == "https://example.com/page"
    assert payload["assets"]["scripts"]["count"] == 1
    assert payload["assets"]["stylesheets"]["count"] == 1
    assert payload["assets"]["images"]["count"] == 1
    assert payload["assets"]["fonts"]["count"] == 1
    assert payload["scores"]["seo"] > 0
    assert payload["scores"]["performance"] > 0


def test_assets_analyze_requires_input():
    client = make_client()
    resp = client.post("/api/assets/analyze", json={})
    assert resp.status_code == 400


def test_assets_convert_requires_html():
    client = make_client()
    resp = client.post("/api/assets/convert", json={"html": "", "target_stack": "react"})
    assert resp.status_code == 400


def test_assets_convert_returns_fallback_output():
    client = make_client()
    resp = client.post(
        "/api/assets/convert",
        json={"html": "<section><h1>Hello</h1></section>", "target_stack": "react"},
    )
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["target_stack"] == "react"
    assert payload["source"] == "deterministic-fallback"
    assert "dangerouslySetInnerHTML" in payload["output"]


def test_convert_page_structure_uses_ai_payload(monkeypatch):
    asset_converter_module.OpenAI = object()
    monkeypatch.setattr("app.asset_converter._nvidia_api_key", lambda: "token")

    class FakeCompletions:
        @staticmethod
        def create(**kwargs):
            return type(
                "Response",
                (),
                {
                    "choices": [
                        type(
                            "Choice",
                            (),
                            {
                                "message": type(
                                    "Message",
                                    (),
                                    {
                                        "content": '{"file_name":"ConvertedPage.jsx","language":"jsx","output":"export default function ConvertedPage(){ return <div>Hello</div>; }"}'
                                    },
                                )()
                            },
                        )()
                    ]
                },
            )()

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        def __init__(self, **kwargs):
            self.chat = FakeChat()

    monkeypatch.setattr("app.asset_converter.OpenAI", FakeClient)

    payload = convert_page_structure("<div>Hello</div>", "react", "keep it simple")
    assert payload["source"] == "ai-model"
    assert payload["file_name"] == "ConvertedPage.jsx"
    assert "<div>Hello</div>" in payload["output"]


def test_analyze_page_assets_fetches_url(monkeypatch):
    html = b"""
    <html>
      <head>
        <title>Remote Page</title>
        <meta name="description" content="remote description content that is long enough for the score checker" />
        <link rel="stylesheet" href="/site.css" />
      </head>
      <body>
        <h1>Remote</h1>
        <img src="/hero.jpg" />
      </body>
    </html>
    """

    class FakeResponse:
        def __init__(self):
            self.headers = {"Content-Type": "text/html; charset=utf-8"}
            self.status = 200

        def geturl(self):
            return "https://example.com/final"

        def read(self, _limit):
            return html

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("app.assets.urlopen", lambda request, timeout=10: FakeResponse())

    payload = analyze_page_assets(url="https://example.com/start")
    assert payload["fetch"]["final_url"] == "https://example.com/final"
    assert payload["page"]["title"] == "Remote Page"
    assert payload["assets"]["stylesheets"]["count"] == 1
    assert payload["assets"]["images"]["missing_alt_count"] == 1
