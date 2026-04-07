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


def wrap_text(text, font, max_width, draw):
    words = text.split()
    lines = []
    current = ""

    for word in words:
        trial = word if not current else current + " " + word
        bbox = draw.textbbox((0, 0), trial, font=font)
        width = bbox[2] - bbox[0]
        if width <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word

    if current:
        lines.append(current)

    return lines


def rounded_rectangle_mask(size, radius):
    mask = Image.new("L", size, 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle((0, 0, size[0], size[1]), radius=radius, fill=255)
    return mask


def build_og_image(word: str):
    # Higher-res, same WhatsApp-friendly aspect ratio
    W, H = 1600, 840

    # Background
    bg = Image.new("RGB", (W, H), (10, 14, 18))
    bg_rgba = bg.convert("RGBA")

    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((60, 100, 700, 760), fill=(40, 90, 255, 45))
    gd.ellipse((980, 160, 1560, 760), fill=(50, 220, 170, 35))
    gd.ellipse((500, -80, 1200, 260), fill=(110, 120, 255, 20))
    glow = glow.filter(ImageFilter.GaussianBlur(90))
    bg_rgba = Image.alpha_composite(bg_rgba, glow)

    # Content region
    outer_margin_x = 55
    outer_margin_y = 40
    content_x1 = outer_margin_x
    content_y1 = outer_margin_y
    content_x2 = W - outer_margin_x
    content_y2 = H - outer_margin_y
    content_w = content_x2 - content_x1
    content_h = content_y2 - content_y1

    gap = 24
    left_w = (content_w - gap) // 2
    right_w = content_w - gap - left_w

    left_x = content_x1
    left_y = content_y1
    right_x = left_x + left_w + gap
    right_y = content_y1

    panel_radius = 34

    # Shadows
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle(
        (left_x + 8, left_y + 12, left_x + left_w + 8, left_y + content_h + 12),
        radius=panel_radius,
        fill=(0, 0, 0, 90),
    )
    sd.rounded_rectangle(
        (right_x + 8, right_y + 12, right_x + right_w + 8, right_y + content_h + 12),
        radius=panel_radius,
        fill=(0, 0, 0, 90),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(22))
    bg_rgba = Image.alpha_composite(bg_rgba, shadow)

    draw = ImageDraw.Draw(bg_rgba)

    # Right text card
    draw.rounded_rectangle(
        (right_x, right_y, right_x + right_w, right_y + content_h),
        radius=panel_radius,
        fill=(245, 246, 242, 255),
    )

    # Fetch source image
    resp = requests.get(SOURCE_IMAGE_URL, timeout=20)
    resp.raise_for_status()
    src = Image.open(BytesIO(resp.content)).convert("RGB")

    # Left image panel
    left_panel = Image.new("RGBA", (left_w, content_h), (18, 18, 18, 255))
    lp_draw = ImageDraw.Draw(left_panel)
    lp_draw.rounded_rectangle(
        (0, 0, left_w, content_h),
        radius=panel_radius,
        fill=(18, 18, 18, 255),
    )

    # Fit image fully visible within left panel
    inner_pad = 18
    max_w = left_w - inner_pad * 2
    max_h = content_h - inner_pad * 2
    ratio = min(max_w / src.width, max_h / src.height)
    new_w = int(src.width * ratio)
    new_h = int(src.height * ratio)
    fitted = src.resize((new_w, new_h), Image.LANCZOS).convert("RGBA")

    img_x = (left_w - new_w) // 2
    img_y = (content_h - new_h) // 2

    img_mask = rounded_rectangle_mask((new_w, new_h), 24)
    left_panel.paste(fitted, (img_x, img_y), mask=img_mask)

    # Subtle overlay for consistency
    left_overlay = Image.new("RGBA", (left_w, content_h), (0, 0, 0, 0))
    lod = ImageDraw.Draw(left_overlay)
    lod.rounded_rectangle(
        (0, 0, left_w, content_h),
        radius=panel_radius,
        fill=(0, 0, 0, 18),
    )
    left_panel = Image.alpha_composite(left_panel, left_overlay)

    bg_rgba.alpha_composite(left_panel, (left_x, left_y))

    # Text in right card
    title = build_title(word)
    description = build_description(word)

    title_font = get_font(84, bold=True)
    desc_font = get_font(48, bold=False)

    td = ImageDraw.Draw(bg_rgba)

    text_pad_x = 46
    text_pad_top = 88
    text_x = right_x + text_pad_x
    text_y = right_y + text_pad_top
    text_max_w = right_w - text_pad_x * 2

    td.text(
        (text_x, text_y),
        title,
        font=title_font,
        fill=(18, 22, 24, 255),
    )

    title_bbox = td.textbbox((text_x, text_y), title, font=title_font)
    desc_y = title_bbox[3] + 28

    desc_lines = wrap_text(description, desc_font, text_max_w, td)
    current_y = desc_y
    for line in desc_lines[:3]:
        td.text(
            (text_x, current_y),
            line,
            font=desc_font,
            fill=(92, 96, 102, 255),
        )
        line_bbox = td.textbbox((text_x, current_y), line, font=desc_font)
        current_y = line_bbox[3] + 14

    out = BytesIO()
    bg_rgba.convert("RGB").save(out, format="JPEG", quality=92, optimize=True)
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
        <title></title>

        <meta property="og:type" content="website" />
        <meta property="og:title" content="" />
        <meta property="og:description" content="" />
        <meta property="og:image" content="{og_image_url}" />
        <meta property="og:url" content="{page_url}" />

        <meta name="twitter:card" content="summary_large_image" />
        <meta name="twitter:title" content="" />
        <meta name="twitter:description" content="" />
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
