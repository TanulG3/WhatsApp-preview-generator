from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from urllib.parse import quote
import html
import sqlite3
import uuid
from datetime import datetime
from io import BytesIO
import os

import requests
from PIL import Image, ImageFilter, ImageDraw, ImageFont

app = FastAPI()

BASE_URL = "https://whatsapp-preview-generator.onrender.com"

SOURCE_IMAGE_URL = (
    "https://zcdhhxgmbzqhpfjgwhkg.supabase.co/storage/v1/object/public/"
    "generated-images/000cea25-634b-41c7-b4d6-f3547e7a6e2a/0.png"
)

CLICK_TARGET = (
    "https://partner-sandbox-tracking.deriv.com/click"
    "?a=2676&o=1&c=3&link_id=1"
)

DB_FILE = "clicks.db"


def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS clicks (
            id TEXT PRIMARY KEY,
            word TEXT NOT NULL,
            uid TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


init_db()


def record_click(word: str, uid: str) -> None:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO clicks (id, word, uid, timestamp)
        VALUES (?, ?, ?, ?)
        """,
        (str(uuid.uuid4()), word, uid, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def get_stats():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM clicks")
    total_clicks = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT uid) FROM clicks")
    unique_users = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT word, timestamp
        FROM clicks
        ORDER BY timestamp DESC
        LIMIT 50
        """
    )
    recent_clicks = cursor.fetchall()

    conn.close()
    return total_clicks, unique_users, recent_clicks


def build_title(word: str) -> str:
    return word.strip().title()


def build_description(word: str) -> str:
    return f"Discover {word.strip()} like never before."


def get_font(size: int, bold: bool = False):
    candidates = []
    if bold:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        ]
    else:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        ]

    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size=size)

    return ImageFont.load_default()


def rounded_mask(size, radius):
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, size[0], size[1]), radius=radius, fill=255)
    return mask


def wrap_text(text, font, max_width, draw):
    words = text.split()
    lines = []
    current = ""

    for word in words:
        test = word if not current else current + " " + word
        bbox = draw.textbbox((0, 0), test, font=font)
        width = bbox[2] - bbox[0]
        if width <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word

    if current:
        lines.append(current)

    return lines


def draw_vertical_gradient(width, height, top_color, bottom_color):
    img = Image.new("RGB", (width, height), top_color)
    draw = ImageDraw.Draw(img)

    for y in range(height):
        ratio = y / max(height - 1, 1)
        r = int(top_color[0] * (1 - ratio) + bottom_color[0] * ratio)
        g = int(top_color[1] * (1 - ratio) + bottom_color[1] * ratio)
        b = int(top_color[2] * (1 - ratio) + bottom_color[2] * ratio)
        draw.line((0, y, width, y), fill=(r, g, b))

    return img


def add_soft_glow(base_img):
    glow = Image.new("RGBA", base_img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(glow)

    draw.ellipse((40, 80, 480, 560), fill=(60, 90, 255, 55))
    draw.ellipse((780, 330, 1160, 660), fill=(80, 255, 200, 45))
    draw.ellipse((500, -40, 980, 260), fill=(120, 120, 255, 30))

    glow = glow.filter(ImageFilter.GaussianBlur(70))
    return Image.alpha_composite(base_img.convert("RGBA"), glow)


def fit_image_inside(img, max_w, max_h):
    ratio = min(max_w / img.width, max_h / img.height)
    new_w = max(1, int(img.width * ratio))
    new_h = max(1, int(img.height * ratio))
    return img.resize((new_w, new_h), Image.LANCZOS)


def build_og_image(word: str):
    W, H = 1200, 630

    # Background
    bg = draw_vertical_gradient(W, H, (8, 12, 18), (16, 32, 34))
    bg = add_soft_glow(bg)

    # Main white content card
    card_x, card_y = 130, 56
    card_w, card_h = 940, 440
    card_radius = 28

    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle(
        (card_x + 10, card_y + 14, card_x + card_w + 10, card_y + card_h + 14),
        radius=card_radius,
        fill=(0, 0, 0, 90),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    composed = Image.alpha_composite(bg.convert("RGBA"), shadow)

    draw = ImageDraw.Draw(composed)
    draw.rounded_rectangle(
        (card_x, card_y, card_x + card_w, card_y + card_h),
        radius=card_radius,
        fill=(246, 247, 242, 255),
    )

    # Left image area: make it as large as possible while leaving text room
    padding = 26
    gap = 28
    img_area_x = card_x + padding
    img_area_y = card_y + padding
    img_area_w = 360
    img_area_h = card_h - (padding * 2)

    text_area_x = img_area_x + img_area_w + gap
    text_area_y = img_area_y + 18
    text_area_w = card_x + card_w - padding - text_area_x
    text_area_h = img_area_h - 30

    # Fetch source portrait image
    resp = requests.get(SOURCE_IMAGE_URL, timeout=20)
    resp.raise_for_status()
    src = Image.open(BytesIO(resp.content)).convert("RGB")

    # Fit image fully visible and as large as possible
    fitted = fit_image_inside(src, img_area_w, img_area_h)

    # Image frame with rounded corners
    img_frame = Image.new("RGBA", (img_area_w, img_area_h), (0, 0, 0, 0))
    frame_draw = ImageDraw.Draw(img_frame)
    frame_draw.rounded_rectangle(
        (0, 0, img_area_w, img_area_h),
        radius=22,
        fill=(18, 18, 18, 255),
    )

    # Center fitted image in frame
    paste_x = (img_area_w - fitted.width) // 2
    paste_y = (img_area_h - fitted.height) // 2

    # Slight inner shadow effect
    frame_shadow = Image.new("RGBA", (img_area_w, img_area_h), (0, 0, 0, 0))
    fsd = ImageDraw.Draw(frame_shadow)
    fsd.rounded_rectangle(
        (4, 6, img_area_w - 4, img_area_h - 2),
        radius=22,
        fill=(0, 0, 0, 40),
    )
    frame_shadow = frame_shadow.filter(ImageFilter.GaussianBlur(10))
    img_frame = Image.alpha_composite(img_frame, frame_shadow)

    inner = Image.new("RGBA", (img_area_w, img_area_h), (0, 0, 0, 0))
    inner.paste(fitted.convert("RGBA"), (paste_x, paste_y))

    mask = rounded_mask((img_area_w, img_area_h), 22)
    img_frame = Image.composite(inner, img_frame, mask)

    composed.alpha_composite(img_frame, (img_area_x, img_area_y))

    # Text
    title = build_title(word)
    description = build_description(word)

    title_font = get_font(54, bold=True)
    desc_font = get_font(34, bold=False)
    domain_font = get_font(28, bold=False)
    link_icon_font = get_font(30, bold=False)

    text_draw = ImageDraw.Draw(composed)

    # Title
    text_draw.text(
        (text_area_x, text_area_y),
        title,
        font=title_font,
        fill=(14, 18, 20, 255),
    )

    # Description
    title_bbox = text_draw.textbbox((text_area_x, text_area_y), title, font=title_font)
    desc_y = title_bbox[3] + 26
    desc_lines = wrap_text(description, desc_font, text_area_w, text_draw)

    current_y = desc_y
    for line in desc_lines[:3]:
        text_draw.text(
            (text_area_x, current_y),
            line,
            font=desc_font,
            fill=(92, 96, 102, 255),
        )
        line_bbox = text_draw.textbbox((text_area_x, current_y), line, font=desc_font)
        current_y = line_bbox[3] + 16

    # Domain row
    domain = "whatsapp-preview-generator.onrender.com"
    domain_y = card_y + card_h - 96

    text_draw.text(
        (text_area_x, domain_y),
        "🔗",
        font=link_icon_font,
        fill=(16, 18, 20, 255),
        embedded_color=True,
    )

    text_draw.text(
        (text_area_x + 46, domain_y - 1),
        domain,
        font=domain_font,
        fill=(16, 18, 20, 255),
    )

    # Export
    out = BytesIO()
    composed.convert("RGB").save(out, format="JPEG", quality=92, optimize=True)
    out.seek(0)
    return out.read()


@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>WhatsApp Preview Generator</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 720px;
                margin: 50px auto;
                padding: 20px;
                line-height: 1.5;
            }
            input {
                padding: 10px 12px;
                font-size: 16px;
                width: 250px;
                max-width: 100%;
            }
            button {
                padding: 10px 14px;
                font-size: 16px;
                cursor: pointer;
                margin-left: 8px;
            }
            a {
                color: #0a66c2;
                text-decoration: none;
            }
        </style>
    </head>
    <body>
        <h1>WhatsApp Preview Generator</h1>
        <form action="/share" method="get">
            <input name="word" placeholder="Enter a word" required />
            <button type="submit">Share to WhatsApp</button>
        </form>

        <p style="margin-top: 20px;">
            <a href="/stats">View Stats</a>
        </p>
    </body>
    </html>
    """


@app.get("/share")
def share(word: str = Query(..., min_length=1)):
    preview_url = f"{BASE_URL}/p/{quote(word.strip())}"
    whatsapp_text = quote(preview_url)
    return RedirectResponse(url=f"https://wa.me/?text={whatsapp_text}")


@app.get("/og-image/{word}", response_class=Response)
def og_image(word: str):
    image_bytes = build_og_image(word.strip())
    return Response(content=image_bytes, media_type="image/jpeg")


@app.get("/p/{word}", response_class=HTMLResponse)
def preview(word: str, request: Request):
    clean_word = word.strip()
    safe_word = html.escape(build_title(clean_word))
    description = html.escape(build_description(clean_word))
    page_url = str(request.url)
    og_image_url = f"{BASE_URL}/og-image/{quote(clean_word)}"

    uid = request.cookies.get("uid")
    is_new_user = False

    if not uid:
        uid = str(uuid.uuid4())
        is_new_user = True

    user_agent = request.headers.get("user-agent", "").lower()
    is_probable_bot = any(
        token in user_agent
        for token in [
            "bot",
            "crawler",
            "spider",
            "preview",
            "facebookexternalhit",
            "whatsapp",
        ]
    )

    if not is_probable_bot:
        record_click(clean_word, uid)

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>{safe_word}</title>

        <meta property="og:type" content="website" />
        <meta property="og:title" content="{safe_word}" />
        <meta property="og:description" content="{description}" />
        <meta property="og:image" content="{og_image_url}" />
        <meta property="og:url" content="{page_url}" />

        <meta name="twitter:card" content="summary_large_image" />
        <meta name="twitter:title" content="{safe_word}" />
        <meta name="twitter:description" content="{description}" />
        <meta name="twitter:image" content="{og_image_url}" />

        <meta http-equiv="refresh" content="0; url={CLICK_TARGET}" />
        <script>
            window.location.replace("{CLICK_TARGET}");
        </script>
    </head>
    <body>
        Redirecting...
    </body>
    </html>
    """

    response = HTMLResponse(content=html_content)

    if is_new_user:
        response.set_cookie(
            key="uid",
            value=uid,
            max_age=60 * 60 * 24 * 365,
            httponly=True,
            samesite="Lax",
        )

    return response


@app.get("/stats", response_class=HTMLResponse)
def stats():
    total_clicks, unique_users, recent_clicks = get_stats()

    rows = "".join(
        f"<tr><td>{html.escape(word)}</td><td>{html.escape(timestamp)}</td></tr>"
        for word, timestamp in recent_clicks
    )

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>Analytics</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                max-width: 900px;
                margin: 40px auto;
                padding: 20px;
            }}
            table {{
                border-collapse: collapse;
                width: 100%;
                margin-top: 20px;
            }}
            th, td {{
                border: 1px solid #ddd;
                padding: 10px;
                text-align: left;
            }}
            th {{
                background: #f5f5f5;
            }}
        </style>
    </head>
    <body>
        <h1>Analytics</h1>

        <p><strong>Total Clicks:</strong> {total_clicks}</p>
        <p><strong>Unique Users:</strong> {unique_users}</p>

        <h2>Recent Clicks</h2>
        <table>
            <tr>
                <th>Word</th>
                <th>Timestamp (UTC)</th>
            </tr>
            {rows}
        </table>
    </body>
    </html>
    """
