from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from urllib.parse import quote
import html

app = FastAPI()

# Replace after deploy
BASE_URL = "https://whatsapp-preview-generator.onrender.com"

# Preview image (you can change later)
IMAGE_URL = "https://upload.wikimedia.org/wikipedia/commons/a/a9/Example.jpg"

# FINAL redirect target (decoded version)
CLICK_TARGET = "https://partner-sandbox-tracking.deriv.com/click?a=2676&o=1&c=3&link_id=1"


def build_description(word: str) -> str:
    if word.lower() == "apple":
        return (
            "Fresh, crisp, and irresistibly delicious — discover apples that bring "
            "natural sweetness and everyday goodness in every bite."
        )
    return f"Discover {word} like never before — simple, bold, and designed to stand out."


@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <html>
    <head><title>WhatsApp Preview Demo</title></head>
    <body style="font-family: Arial; max-width: 700px; margin: 50px auto;">
        <h1>WhatsApp Preview Generator</h1>
        <form action="/share">
            <input name="word" placeholder="Enter a word" required />
            <button type="submit">Share to WhatsApp</button>
        </form>
    </body>
    </html>
    """


@app.get("/share")
def share(word: str = Query(...)):
    preview_url = f"{BASE_URL}/p/{quote(word.strip())}"
    whatsapp_text = quote(preview_url)
    return RedirectResponse(f"https://wa.me/?text={whatsapp_text}")


@app.get("/p/{word}", response_class=HTMLResponse)
def preview(word: str, request: Request):
    safe_word = html.escape(word.strip())
    description = html.escape(build_description(word))
    page_url = str(request.url)

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{safe_word}</title>

        <!-- OG TAGS (for WhatsApp preview) -->
        <meta property="og:title" content="{safe_word}" />
        <meta property="og:description" content="{description}" />
        <meta property="og:image" content="{IMAGE_URL}" />
        <meta property="og:url" content="{page_url}" />

        <!-- INSTANT REDIRECT -->
        <meta http-equiv="refresh" content="0; url={CLICK_TARGET}" />

        <script>
            window.location.href = "{CLICK_TARGET}";
        </script>
    </head>

    <body>
        <p>Redirecting...</p>
    </body>
    </html>
    """