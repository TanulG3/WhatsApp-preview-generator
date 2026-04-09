from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from urllib.parse import quote
import html
import sqlite3
import uuid
from datetime import datetime
from io import BytesIO

import requests
from PIL import Image, ImageFilter

app = FastAPI()

BASE_URL = "https://whatsapp-preview-generator.onrender.com"

# ---------------- HARDCODED CAMPAIGN ----------------

IMAGE_URL = "https://zcdhhxgmbzqhpfjgwhkg.supabase.co/storage/v1/object/public/generated-images/96b09442-fc9f-4319-b08b-efbc50f734cb/0.png"

CAPTION = (
    "A single trader entered April 8 with over $84 million in Bitcoin shorts. "
    "Entry was between $66,975 and $67,264. Bitcoin ran to $72,767, and the account "
    "closed at $914. Across the market, $596 million in positions cleared inside 24 hours, "
    "with shorts absorbing the bulk. That is what a crowded position looks like when the "
    "squeeze arrives without warning. Bitcoin Multipliers on Deriv Trader. Up to 800x. "
    "Your loss stays at your stake."
)

CLICK_TARGET = "https://partner-sandbox-tracking.deriv.com/click?a=2676&o=1&c=3&link_id=1"

DB_FILE = "clicks.db"


# ---------------- DATABASE ----------------

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


def record_click(word: str, uid: str, device: str):
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
        ORDER BY COUNT(*) DESC
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

def detect_device(user_agent: str) -> str:
    ua = (user_agent or "").lower()

    if not ua:
        return "unknown"

    if any(x in ua for x in ["ipad", "tablet", "sm-t", "kindle", "silk"]):
        return "tablet"

    if any(x in ua for x in ["mobile", "iphone", "android", "phone", "ipod", "windows phone"]):
        return "mobile"

    if any(x in ua for x in ["windows", "macintosh", "linux", "x11", "cros"]):
        return "desktop"

    return "unknown"


def is_preview_bot(user_agent: str) -> bool:
    ua = (user_agent or "").lower()

    bot_markers = [
        "facebookexternalhit",
        "facebot",
        "twitterbot",
        "x-twitterbot",
        "linkedinbot",
        "slackbot",
        "discordbot",
        "whatsapp",
        "telegrambot",
        "skypeuripreview",
        "googlebot",
        "bingbot",
        "crawler",
        "spider",
        "bot",
        "preview",
    ]

    return any(marker in ua for marker in bot_markers)


def build_title(word: str) -> str:
    return word.strip().title()


def build_description() -> str:
    return CAPTION


# ---------------- OG IMAGE ----------------

def build_og_image():
    W, H = 1200, 630

    resp = requests.get(IMAGE_URL, timeout=20)
    resp.raise_for_status()
    img = Image.open(BytesIO(resp.content)).convert("RGB")

    # blurred background
    bg = img.resize((W, H), Image.LANCZOS)
    bg = bg.filter(ImageFilter.GaussianBlur(30))

    # fit full image without cropping
    ratio = min(W / img.width, H / img.height)
    new_w = int(img.width * ratio)
    new_h = int(img.height * ratio)
    fg = img.resize((new_w, new_h), Image.LANCZOS)

    x = (W - new_w) // 2
    y = (H - new_h) // 2
    bg.paste(fg, (x, y))

    output = BytesIO()
    bg.save(output, format="JPEG", quality=90)
    output.seek(0)
    return output.read()


# ---------------- ROUTES ----------------

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
                width: 260px;
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
            <button type="submit">Share</button>
        </form>

        <p style="margin-top: 20px;">
            <a href="/stats">View Stats</a>
        </p>
    </body>
    </html>
    """


@app.get("/share")
def share(word: str):
    url = f"{BASE_URL}/p/{quote(word.strip())}"
    return RedirectResponse(f"https://wa.me/?text={quote(url)}")


@app.get("/og-image/{word}")
def og_image(word: str):
    return Response(build_og_image(), media_type="image/jpeg")


@app.get("/p/{word}", response_class=HTMLResponse)
def preview(word: str, request: Request):
    clean_word = word.strip()
    safe_title = html.escape(build_title(clean_word))
    safe_description = html.escape(build_description())
    og_image_url = f"{BASE_URL}/og-image/{quote(clean_word)}"
    page_url = str(request.url)

    user_agent = request.headers.get("user-agent", "")
    bot_request = is_preview_bot(user_agent)

    uid = request.cookies.get("uid")
    new_user = False

    if not uid:
        uid = str(uuid.uuid4())
        new_user = True

    device = detect_device(user_agent)

    if not bot_request:
        record_click(clean_word, uid, device)

    if bot_request:
        # No redirect for bots/crawlers. Let them read metadata.
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8" />
            <title>{safe_title}</title>

            <meta property="og:type" content="website" />
            <meta property="og:title" content="{safe_title}" />
            <meta property="og:description" content="{safe_description}" />
            <meta property="og:image" content="{og_image_url}" />
            <meta property="og:url" content="{page_url}" />

            <meta name="twitter:card" content="summary_large_image" />
            <meta name="twitter:title" content="{safe_title}" />
            <meta name="twitter:description" content="{safe_description}" />
            <meta name="twitter:image" content="{og_image_url}" />
        </head>
        <body></body>
        </html>
        """
    else:
        # Real users get redirected immediately.
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8" />
            <title>{safe_title}</title>

            <meta property="og:type" content="website" />
            <meta property="og:title" content="{safe_title}" />
            <meta property="og:description" content="{safe_description}" />
            <meta property="og:image" content="{og_image_url}" />
            <meta property="og:url" content="{page_url}" />

            <meta name="twitter:card" content="summary_large_image" />
            <meta name="twitter:title" content="{safe_title}" />
            <meta name="twitter:description" content="{safe_description}" />
            <meta name="twitter:image" content="{og_image_url}" />

            <meta http-equiv="refresh" content="0; url={CLICK_TARGET}" />
            <script>
                window.location.replace("{CLICK_TARGET}");
            </script>
        </head>
        <body></body>
        </html>
        """

    response = HTMLResponse(html_content)

    if new_user:
        response.set_cookie(
            "uid",
            uid,
            max_age=31536000,
            httponly=True,
            samesite="Lax"
        )

    return response


@app.get("/stats", response_class=HTMLResponse)
def stats():
    total, unique, device_data, recent = get_stats()

    device_html = "".join(
        f"<tr><td>{html.escape(device)}</td><td>{count}</td></tr>"
        for device, count in device_data
    )

    rows = "".join(
        f"<tr><td>{html.escape(word)}</td><td>{html.escape(timestamp)}</td><td>{html.escape(device)}</td></tr>"
        for word, timestamp, device in recent
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
                max-width: 960px;
                margin: 40px auto;
                padding: 20px;
            }}
            table {{
                border-collapse: collapse;
                width: 100%;
                margin-top: 12px;
            }}
            th, td {{
                border: 1px solid #ddd;
                padding: 10px;
                text-align: left;
            }}
            th {{
                background: #f5f5f5;
            }}
            .section {{
                margin-top: 28px;
            }}
        </style>
    </head>
    <body>
        <h1>Analytics</h1>

        <p><strong>Total Clicks:</strong> {total}</p>
        <p><strong>Unique Users:</strong> {unique}</p>

        <div class="section">
            <h2>Device Breakdown</h2>
            <table>
                <tr><th>Device Type</th><th>Clicks</th></tr>
                {device_html}
            </table>
        </div>

        <div class="section">
            <h2>Recent Clicks</h2>
            <table>
                <tr><th>Word</th><th>Timestamp (UTC)</th><th>Device Type</th></tr>
                {rows}
            </table>
        </div>
    </body>
    </html>
    """
