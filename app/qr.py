from io import BytesIO

from PIL import Image, ImageDraw, ImageOps
import qrcode
import qrcode.image.svg


SUPPORTED_FORMATS = {"png", "jpeg", "jpg", "svg"}
DEFAULT_QR_COLOR = "#000000"
DEFAULT_BORDER_COLOR = "#000000"
DEFAULT_BG_COLOR = "#ffffff"


def _normalize_format(fmt: str) -> str:
    if not fmt:
        return "png"
    fmt = fmt.lower().strip()
    if fmt == "jpg":
        return "jpeg"
    return fmt


def _normalize_color(value: str, fallback: str) -> str:
    value = (value or "").strip()
    if not value:
        return fallback
    if not value.startswith("#"):
        value = f"#{value}"
    if len(value) != 7:
        raise ValueError("Invalid color")
    int(value[1:], 16)
    return value


def _apply_logo(base_img: Image.Image, logo_bytes: bytes | None) -> Image.Image:
    if not logo_bytes:
        return base_img

    logo = Image.open(BytesIO(logo_bytes)).convert("RGBA")
    qr_size = min(base_img.size)
    logo_size = max(32, qr_size // 5)
    logo.thumbnail((logo_size, logo_size), Image.Resampling.LANCZOS)

    # Add white rounded padding so the logo does not clash with QR modules.
    padded_size = (logo.width + 16, logo.height + 16)
    padded_logo = Image.new("RGBA", padded_size, (255, 255, 255, 0))
    rounded_bg = Image.new("RGBA", padded_size, (255, 255, 255, 255))
    mask = Image.new("L", padded_size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, padded_size[0], padded_size[1]), radius=10, fill=255)
    padded_logo.paste(rounded_bg, (0, 0), mask)
    padded_logo.paste(
        logo,
        ((padded_size[0] - logo.width) // 2, (padded_size[1] - logo.height) // 2),
        logo,
    )

    x = (base_img.size[0] - padded_size[0]) // 2
    y = (base_img.size[1] - padded_size[1]) // 2
    base_img.paste(padded_logo, (x, y), padded_logo)
    return base_img


def make_qr(
    data: str,
    fmt: str,
    qr_color: str = DEFAULT_QR_COLOR,
    border_color: str = DEFAULT_BORDER_COLOR,
    logo_bytes: bytes | None = None,
) -> tuple[BytesIO, str]:
    fmt = _normalize_format(fmt)
    if fmt not in SUPPORTED_FORMATS:
        raise ValueError("Unsupported format")

    qr_color = _normalize_color(qr_color, DEFAULT_QR_COLOR)
    border_color = _normalize_color(border_color, DEFAULT_BORDER_COLOR)

    if fmt == "svg":
        if logo_bytes:
            raise ValueError("Logo is not supported for SVG format")
        if border_color != DEFAULT_BORDER_COLOR:
            raise ValueError("Custom border color is not supported for SVG format")

        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(
            image_factory=qrcode.image.svg.SvgImage,
            fill_color=qr_color,
            back_color=DEFAULT_BG_COLOR,
        )
        buffer = BytesIO()
        img.save(buffer)
        buffer.seek(0)
        return buffer, "image/svg+xml"

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color=qr_color, back_color=DEFAULT_BG_COLOR).convert("RGB")

    # Draw a visible outer border ring in caller-selected color.
    img = ImageOps.expand(img, border=8, fill=border_color)

    if logo_bytes:
        try:
            img = _apply_logo(img.convert("RGBA"), logo_bytes).convert("RGB")
        except Exception as exc:  # noqa: BLE001
            raise ValueError("Invalid logo file") from exc

    buffer = BytesIO()
    img.save(buffer, format=fmt.upper())
    buffer.seek(0)
    mime = "image/png" if fmt == "png" else "image/jpeg"
    return buffer, mime
