from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from urllib.parse import quote
import html
import sqlite3
import uuid
from datetime import datetime
from io import BytesIO

import requests
from PIL import Image, ImageFilter, ImageDraw, ImageFont

app = FastAPI()

BASE_URL = "https://whatsapp-preview-generator.onrender.com"

# ✅ HARDCODED IMAGE
IMAGE_URL = "https://zcdhhxgmbzqhpfjgwhkg.supabase.co/storage/v1/object/public/generated-images/96b09442-fc9f-4319-b08b-efbc50f734cb/0.png"

# ✅ HARDCODED CAPTION
CAPTION = """A single trader entered April 8 with over $84 million in Bitcoin shorts. Entry was between $66,975 and $67,264. Bitcoin ran to $72,767, and the account closed at $914. Across the market, $596 million in positions cleared inside 24 hours, with shorts absorbing the bulk. That is what a crowded position looks like when the squeeze arrives without warning.
Bitcoin Multipliers on Deriv Trader. Up to 800x. Your loss stays at your stake."""

CLICK_TARGET = (
    "https://partner-sandbox-tracking.deriv.com/click"
    "?a=2676&o=1&c=3&link_id=1"
)

DB_FILE = "clicks.db"


# ---------------- DB ----------------

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clicks (
            id TEXT PRIMARY KEY,
            word TEXT,
            uid TEXT,
            timestamp TEXT,
            device_type TEXT
        )
    """)

    conn.commit()
    conn.close()


init_db()


def record_click(word, uid, device):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO clicks VALUES (?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), word, uid, datetime.utcnow().isoformat(), device),
    )
    conn.commit()
    conn.close()


def get_stats():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM clicks")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT uid) FROM clicks")
    unique = cursor.fetchone()[0]

    cursor.execute("""
        SELECT device_type, COUNT(*)
        FROM clicks
        GROUP BY device_type
    """)
    device_data = cursor.fetchall()

    cursor.execute("""
        SELECT word, timestamp, device_type
        FROM clicks
        ORDER BY timestamp DESC
        LIMIT 50
    """)
    recent = cursor.fetchall()

    conn.close()
    return total, unique, device_data, recent


# ---------------- HELPERS ----------------

def get_font(size, bold=False):
    try:
        if bold:
            return ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size
            )
        return ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size
        )
    except:
        return ImageFont.load_default()


def wrap_text(text, font, max_width, draw):
    words = text.split()
    lines = []
    current = ""

    for word in words:
        test = word if not current else current + " " + word
        bbox = draw.textbbox((0, 0), test, font=font)

        if bbox[2] <= max_width:
            current = test
        else:
            lines.append(current)
            current = word

    if current:
        lines.append(current)

    return lines


def detect_device(user_agent):
    ua = (user_agent or "").lower()

    if "ipad" in ua or "tablet" in ua:
        return "tablet"
    if "mobile" in ua or "iphone" in ua or "android" in ua:
        return "mobile"
    if "windows" in ua or "macintosh" in ua:
        return "desktop"

    return "unknown"


# ---------------- OG IMAGE ----------------

def build_og_image(word):
    W, H = 1200, 630

    resp = requests.get(IMAGE_URL, timeout=20)
    img = Image.open(BytesIO(resp.content)).convert("RGB")

    # Blurred background
    bg = img.resize((W, H), Image.LANCZOS)
    bg = bg.filter(ImageFilter.GaussianBlur(30))

    # Foreground fit
    ratio = min(W / img.width, H / img.height)
    new_size = (int(img.width * ratio), int(img.height * ratio))
    fg = img.resize(new_size, Image.LANCZOS)

    x = (W - new_size[0]) // 2
    y = (H - new_size[1]) // 2
    bg.paste(fg, (x, y))

    # Gradient overlay
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)

    for i in range(H):
        alpha = int(180 * (i / H))
        od.rectangle((0, i, W, i + 1), fill=(0, 0, 0, alpha))

    bg = Image.alpha_composite(bg.convert("RGBA"), overlay)

    draw = ImageDraw.Draw(bg)

    title = word.title()
    title_font = get_font(60, bold=True)
    desc_font = get_font(30)

    # Title
    draw.text((40, H - 200), title, font=title_font, fill=(255, 255, 255))

    # Caption
    lines = wrap_text(CAPTION, desc_font, W - 80, draw)
    y_text = H - 120

    for line in lines[:3]:
        draw.text((40, y_text), line, font=desc_font, fill=(220, 220, 220))
        y_text += 36

    output = BytesIO()
    bg.convert("RGB").save(output, format="JPEG", quality=90)
    output.seek(0)

    return output.read()


# ---------------- ROUTES ----------------

@app.get("/share")
def share(word: str):
    url = f"{BASE_URL}/p/{quote(word)}"
    return RedirectResponse(f"https://wa.me/?text={quote(url)}")


@app.get("/og-image/{word}")
def og_image(word: str):
    return Response(build_og_image(word), media_type="image/jpeg")


@app.get("/p/{word}", response_class=HTMLResponse)
def preview(word: str, request: Request):
    clean_word = word.strip()
    og_image_url = f"{BASE_URL}/og-image/{quote(clean_word)}"
    page_url = str(request.url)

    uid = request.cookies.get("uid") or str(uuid.uuid4())
    device = detect_device(request.headers.get("user-agent", ""))

    if "whatsapp" not in request.headers.get("user-agent", "").lower():
        record_click(clean_word, uid, device)

    html_content = f"""
    <html>
    <head>
        <meta property="og:title" content="{clean_word}" />
        <meta property="og:description" content="Tap to view" />
        <meta property="og:image" content="{og_image_url}" />
        <meta property="og:url" content="{page_url}" />

        <meta http-equiv="refresh" content="0; url={CLICK_TARGET}" />
    </head>
    <body></body>
    </html>
    """

    response = HTMLResponse(html_content)
    response.set_cookie("uid", uid, max_age=31536000)

    return response


@app.get("/stats", response_class=HTMLResponse)
def stats():
    total, unique, device_data, recent = get_stats()

    device_html = "".join(f"<li>{d}: {c}</li>" for d, c in device_data)

    rows = "".join(
        f"<tr><td>{w}</td><td>{t}</td><td>{d}</td></tr>"
        for w, t, d in recent
    )

    return f"""
    <h1>Analytics</h1>
    <p>Total Clicks: {total}</p>
    <p>Unique Users: {unique}</p>

    <h2>Device Breakdown</h2>
    <ul>{device_html}</ul>

    <h2>Recent</h2>
    <table border="1">
        <tr><th>Word</th><th>Time</th><th>Device</th></tr>
        {rows}
    </table>
    """
