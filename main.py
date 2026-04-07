from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from urllib.parse import quote
import html
import sqlite3
import uuid
from datetime import datetime

app = FastAPI()

BASE_URL = "https://whatsapp-preview-generator.onrender.com"
IMAGE_URL = "https://upload.wikimedia.org/wikipedia/commons/a/a9/Example.jpg"
CLICK_TARGET = "https://partner-sandbox-tracking.deriv.com/click?a=2676&o=1&c=3&link_id=1"

DB_FILE = "clicks.db"


# -----------------------
# DB SETUP
# -----------------------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clicks (
            id TEXT,
            word TEXT,
            uid TEXT,
            timestamp TEXT
        )
    """)

    conn.commit()
    conn.close()


init_db()


def record_click(word: str, uid: str):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO clicks (id, word, uid, timestamp)
        VALUES (?, ?, ?, ?)
    """, (str(uuid.uuid4()), word, uid, datetime.utcnow().isoformat()))

    conn.commit()
    conn.close()


# -----------------------
# ROUTES
# -----------------------

@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <h1>WhatsApp Preview Generator</h1>
    <form action="/share">
        <input name="word" placeholder="Enter a word" required />
        <button type="submit">Share to WhatsApp</button>
    </form>
    <br/>
    <a href="/stats">View Stats</a>
    """


@app.get("/share")
def share(word: str = Query(...)):
    preview_url = f"{BASE_URL}/p/{quote(word.strip())}"
    return RedirectResponse(f"https://wa.me/?text={quote(preview_url)}")


@app.get("/p/{word}", response_class=HTMLResponse)
def preview(word: str, request: Request):
    clean_word = word.strip()
    safe_word = html.escape(clean_word)

    # 🔥 Get or create anonymous user ID
    uid = request.cookies.get("uid")
    is_new_user = False

    if not uid:
        uid = str(uuid.uuid4())
        is_new_user = True

    # 🔥 Record click
    record_click(clean_word, uid)

    # OG metadata
    page_url = str(request.url)

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{safe_word}</title>

        <meta property="og:title" content="{safe_word}" />
        <meta property="og:description" content="Discover {safe_word} like never before." />
        <meta property="og:image" content="{IMAGE_URL}" />
        <meta property="og:url" content="{page_url}" />

        <!-- Instant redirect -->
        <meta http-equiv="refresh" content="0; url={CLICK_TARGET}" />
        <script>
            window.location.href = "{CLICK_TARGET}";
        </script>
    </head>
    <body>
        Redirecting...
    </body>
    </html>
    """

    response = HTMLResponse(content=html_content)

    # 🍪 Set cookie ONLY if new
    if is_new_user:
        response.set_cookie(
            key="uid",
            value=uid,
            max_age=60 * 60 * 24 * 365  # 1 year
        )

    return response


@app.get("/stats", response_class=HTMLResponse)
def stats():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Total clicks
    cursor.execute("SELECT COUNT(*) FROM clicks")
    total_clicks = cursor.fetchone()[0]

    # Unique users
    cursor.execute("SELECT COUNT(DISTINCT uid) FROM clicks")
    unique_users = cursor.fetchone()[0]

    # Recent clicks
    cursor.execute("""
        SELECT word, timestamp
        FROM clicks
        ORDER BY timestamp DESC
        LIMIT 20
    """)
    rows = cursor.fetchall()

    conn.close()

    table_rows = "".join(
        f"<tr><td>{html.escape(word)}</td><td>{timestamp}</td></tr>"
        for word, timestamp in rows
    )

    return f"""
    <h1>Analytics</h1>

    <p><b>Total Clicks:</b> {total_clicks}</p>
    <p><b>Unique Users:</b> {unique_users}</p>

    <h2>Recent Clicks</h2>
    <table border="1" cellpadding="10">
        <tr><th>Word</th><th>Timestamp (UTC)</th></tr>
        {table_rows}
    </table>
    """
