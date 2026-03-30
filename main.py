from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from urllib.parse import quote
import html

app = FastAPI()

# Replace this with your real public URL after deployment.
# Example: https://your-app-name.onrender.com
BASE_URL = "https://whatsapp-preview-generator.onrender.com"

# Fixed public image for testing WhatsApp preview
FIXED_IMAGE_URL = "https://upload.wikimedia.org/wikipedia/commons/a/a9/Example.jpg"


@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>WhatsApp Preview Demo</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 700px;
                margin: 50px auto;
                padding: 20px;
                line-height: 1.5;
            }
            h1 {
                margin-bottom: 8px;
            }
            p {
                color: #444;
            }
            .row {
                display: flex;
                gap: 10px;
                margin-top: 20px;
                flex-wrap: wrap;
            }
            input[type="text"] {
                flex: 1;
                min-width: 240px;
                padding: 12px;
                font-size: 16px;
                border: 1px solid #ccc;
                border-radius: 8px;
            }
            button {
                padding: 12px 16px;
                font-size: 16px;
                border: none;
                border-radius: 8px;
                background: #25D366;
                color: white;
                cursor: pointer;
            }
            button:hover {
                opacity: 0.95;
            }
            .note {
                margin-top: 24px;
                padding: 12px 14px;
                border-radius: 8px;
                background: #f5f5f5;
                font-size: 14px;
            }
            .small {
                margin-top: 16px;
                font-size: 13px;
                color: #666;
                word-break: break-word;
            }
        </style>
    </head>
    <body>
        <h1>WhatsApp Preview Demo</h1>
        <p>Type a word, then share a public link to WhatsApp. The preview comes from the shared URL's Open Graph tags.</p>

        <form action="/share" method="get">
            <div class="row">
                <input
                    type="text"
                    name="word"
                    placeholder="Enter a word"
                    required
                />
                <button type="submit">Share to WhatsApp</button>
            </div>
        </form>

        <div class="note">
            This demo shares a URL like <code>/p/yourword</code>. That page includes
            Open Graph metadata so WhatsApp can build a preview card.
        </div>

        <div class="small">
            After deployment, make sure BASE_URL matches your real public domain.
        </div>
    </body>
    </html>
    """


@app.get("/share")
def share(word: str = Query(..., min_length=1)):
    clean_word = word.strip()
    encoded_word = quote(clean_word)
    preview_url = f"{BASE_URL}/p/{encoded_word}"

    # This opens WhatsApp share with the public preview URL
    whatsapp_text = quote(f"Check this out: {preview_url}")
    return RedirectResponse(url=f"https://wa.me/?text={whatsapp_text}")


@app.get("/p/{word}", response_class=HTMLResponse)
def preview_page(word: str, request: Request):
    clean_word = word.strip()
    safe_word = html.escape(clean_word)

    page_url = str(request.url)
    title = f"Word preview: {safe_word}"
    description = f"This is a demo WhatsApp preview for the word '{safe_word}'."

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>{title}</title>

        <!-- Open Graph tags used by WhatsApp / link preview consumers -->
        <meta property="og:type" content="website" />
        <meta property="og:title" content="{title}" />
        <meta property="og:description" content="{description}" />
        <meta property="og:url" content="{page_url}" />
        <meta property="og:image" content="{FIXED_IMAGE_URL}" />

        <!-- Optional extras -->
        <meta name="twitter:card" content="summary_large_image" />
        <meta name="twitter:title" content="{title}" />
        <meta name="twitter:description" content="{description}" />
        <meta name="twitter:image" content="{FIXED_IMAGE_URL}" />
    </head>
    <body style="font-family: Arial, sans-serif; max-width: 700px; margin: 50px auto; padding: 20px;">
        <h1>{safe_word}</h1>
        <p>This page exists mainly so WhatsApp can generate a link preview.</p>
        <img
            src="{FIXED_IMAGE_URL}"
            alt="Preview image"
            style="max-width: 100%; height: auto; border-radius: 10px;"
        />
        <p style="margin-top: 20px; color: #666;">
            Shared URL: {html.escape(page_url)}
        </p>
    </body>
    </html>
    """