from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from urllib.parse import quote
import html

app = FastAPI()

# Replace this after deployment
BASE_URL = "https://whatsapp-preview-generator.onrender.com"

# Fixed preview image for testing
IMAGE_URL = "https://upload.wikimedia.org/wikipedia/commons/a/a9/Example.jpg"

# Final destination when image is clicked
CLICK_TARGET = (
    "https://partner-adgen.deriv.ai/share/ad/"
    "1a55f725-3936-4ffd-8521-44adcc925810"
    "?ref=https%3A%2F%2Fpartner-sandbox-tracking.deriv.com%2Fclick"
    "%3Fa%3D2676%26o%3D1%26c%3D3%26link_id%3D1"
)


def build_ad_description(word: str) -> str:
    word_lower = word.lower().strip()

    if word_lower == "apple":
        return (
            "Fresh, crisp, and irresistibly delicious — discover apples that bring "
            "natural sweetness, everyday goodness, and a bite of pure refreshment."
        )

    return (
        f"Discover {word} like never before — bold, eye-catching, and designed to "
        f"stand out. A simple idea, presented with premium appeal."
    )


@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>WhatsApp Ad Preview Demo</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 720px;
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
        </style>
    </head>
    <body>
        <h1>WhatsApp Ad Preview Demo</h1>
        <p>Enter a word, then share it to WhatsApp with a preview card.</p>

        <form action="/share" method="get">
            <div class="row">
                <input type="text" name="word" placeholder="Enter a word" required />
                <button type="submit">Share to WhatsApp</button>
            </div>
        </form>

        <div class="note">
            The shared page will show a preview title, description, and image.
            Clicking the image will redirect to your target ad link.
        </div>
    </body>
    </html>
    """


@app.get("/share")
def share(word: str = Query(..., min_length=1)):
    clean_word = word.strip()
    preview_url = f"{BASE_URL}/p/{quote(clean_word)}"
    whatsapp_text = quote(preview_url)
    return RedirectResponse(url=f"https://wa.me/?text={whatsapp_text}")


@app.get("/p/{word}", response_class=HTMLResponse)
def preview_page(word: str, request: Request):
    clean_word = word.strip()
    safe_word = html.escape(clean_word)
    description = build_ad_description(clean_word)
    safe_description = html.escape(description)
    page_url = str(request.url)

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>{safe_word}</title>

        <meta property="og:type" content="website" />
        <meta property="og:title" content="{safe_word}" />
        <meta property="og:description" content="{safe_description}" />
        <meta property="og:url" content="{page_url}" />
        <meta property="og:image" content="{IMAGE_URL}" />

        <meta name="twitter:card" content="summary_large_image" />
        <meta name="twitter:title" content="{safe_word}" />
        <meta name="twitter:description" content="{safe_description}" />
        <meta name="twitter:image" content="{IMAGE_URL}" />

        <style>
            body {{
                font-family: Arial, sans-serif;
                max-width: 720px;
                margin: 50px auto;
                padding: 20px;
                line-height: 1.5;
            }}
            h1 {{
                margin-bottom: 10px;
            }}
            p {{
                color: #444;
                margin-bottom: 24px;
            }}
            .image-link {{
                display: inline-block;
                text-decoration: none;
            }}
            img {{
                max-width: 100%;
                height: auto;
                border-radius: 12px;
                cursor: pointer;
                box-shadow: 0 4px 16px rgba(0,0,0,0.12);
            }}
            .hint {{
                font-size: 14px;
                color: #666;
                margin-top: 12px;
            }}
        </style>
    </head>
    <body>
        <h1>{safe_word}</h1>
        <p>{safe_description}</p>

        <a class="image-link" href="{CLICK_TARGET}">
            <img src="{IMAGE_URL}" alt="{safe_word}" />
        </a>

        <div class="hint">Tap the image to continue.</div>
    </body>
    </html>
    """