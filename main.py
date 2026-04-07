from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from urllib.parse import quote
import html
import sqlite3
import uuid
from datetime import datetime
from io import BytesIO

import requests
from PIL import Image

app = FastAPI()

BASE_URL = "https://whatsapp-preview-generator.onrender.com"

# Original portrait image URL
SOURCE_IMAGE_URL = (
    "https://zcdhhxgmbzqhpfjgwhkg.supabase.co/storage/v1/object/public/"
    "generated-images/000cea25-634b-41c7-b4d6-f3547e7a6e2a/0.png"
)

# Final redirect target
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


def build_description(word: str) -> str:
    return f"Discover {word} like never before."


def crop_and_resize_cover(img: Image.Image, target_width: int, target_height: int) -> Image.Image:
    """
    Resize using 'cover' behavior:
    - scale image until target area is fully covered
    - crop center
    """
    src_width, src_height = img.size
    src_ratio = src_width / src_height
    target_ratio = target_width / target_height

    if src_ratio > target_ratio:
        # Source is wider than target -> fit height, crop sides
        new_height = target_height
        new_width = int(new_height * src_ratio)
    else:
        # Source is taller/narrower than target -> fit width, crop top/bottom
        new_width = target_width
        new_height = int(new_width / src_ratio)

    resized = img.resize((new_width, new_height), Image.LANCZOS)

    left = (new_width - target_width) // 2
    top = (new_height - target_height) // 2
    right = left + target_width
    bottom = top + target_height

    return resized.crop((left, top, right, bottom))


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


@app.get("/og-image", response_class=Response)
def og_image():
    """
    Fetch the portrait source image, convert it to a WhatsApp-friendly 1200x630 image.
    """
    resp = requests.get(SOURCE_IMAGE_URL, timeout=20)
    resp.raise_for_status()

    img = Image.open(BytesIO(resp.content)).convert("RGB")
    img = crop_and_resize_cover(img, 1200, 630)

    output = BytesIO()
    img.save(output, format="JPEG", quality=90, optimize=True)
    output.seek(0)

    return Response(content=output.read(), media_type="image/jpeg")


@app.get("/p/{word}", response_class=HTMLResponse)
def preview(word: str, request: Request):
    clean_word = word.strip()
    safe_word = html.escape(clean_word)
    description = html.escape(build_description(clean_word))
    page_url = str(request.url)
    og_image_url = f"{BASE_URL}/og-image"

    uid = request.cookies.get("uid")
    is_new_user = False

    if not uid:
        uid = str(uuid.uuid4())
        is_new_user = True

    # Optional lightweight bot filter so obvious preview crawlers don't inflate stats
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
