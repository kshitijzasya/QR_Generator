# QR Generator (Flask Microservice)

Small Flask microservice that generates QR codes (PNG/JPEG/SVG) for any text or URL.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python run.py
```

Open `http://localhost:5000` and submit a URL/text to download a QR code.
The web UI now generates a preview first, then lets you choose download format.

## API

`POST /api/qr`

- Form or JSON fields:
  - `data` (required)
  - `format` (optional: png, jpeg, svg)
  - `qr_color` (optional hex color, default `#000000`)
  - `border_color` (optional hex color, default `#000000`)
  - `logo` (optional image upload via multipart form; PNG/JPEG output only)

`POST /api/qr/preview`

- Form fields:
  - `data` (required)
  - `qr_color` (optional)
  - `border_color` (optional)
  - `logo` (optional)
- Returns PNG inline for UI preview.

Notes:
- Generated QR content does not expire because it is static data encoded in the image.
- For SVG output, custom border color and logo upload are not supported.

Example JSON request:

```bash
curl -X POST http://localhost:5000/api/qr \
  -H 'Content-Type: application/json' \
  -d '{"data":"https://forms.gle/abc","format":"png","qr_color":"#0d47a1","border_color":"#ff9800"}' \
  --output qrcode.png
```

Example multipart request with logo:

```bash
curl -X POST http://localhost:5000/api/qr \
  -F 'data=https://forms.gle/abc' \
  -F 'format=png' \
  -F 'qr_color=#0d47a1' \
  -F 'border_color=#ff9800' \
  -F 'logo=@/absolute/path/logo.png' \
  --output qrcode.png
```

## SEO Mode (Live YouTube Data)

Set your YouTube Data API key before running:

```bash
export YOUTUBE_API_KEY=your_api_key_here
```

Pages:
- `GET /seo` for the SEO UI

API:
- `POST /api/seo/generate`
  - JSON fields:
    - `topic` (required)
    - `platform` (optional, default `youtube`)
    - `live` (optional, default `true`)

Example:

```bash
curl -X POST http://localhost:5000/api/seo/generate \
  -H 'Content-Type: application/json' \
  -d '{"platform":"youtube","topic":"how to start calisthenics","live":true}'
```

If `YOUTUBE_API_KEY` is missing or YouTube API fails, the endpoint falls back to local rule-based output and includes `source` and `live_error` in the response.
