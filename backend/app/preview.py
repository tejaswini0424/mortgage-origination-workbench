import io

import pymupdf as fitz
from PIL import Image

def render_page(content, media, number):
    if media == "application/pdf":
        with fitz.open(stream=content, filetype="pdf") as pdf:
            if pdf.needs_pass or not 1 <= number <= min(len(pdf), 30):
                raise ValueError("Page unavailable.")
            page = pdf[number - 1]
            scale = min(2, 1600 / max(page.rect.width, page.rect.height))
            return page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False).tobytes("png")
    if number != 1:
        raise ValueError("Page unavailable.")
    with Image.open(io.BytesIO(content)) as image:
        if image.width * image.height > 16_000_000:
            raise ValueError("Page unavailable.")
        image.thumbnail((1600, 1600))
        output = io.BytesIO()
        image.convert("RGB").save(output, format="PNG")
        return output.getvalue()
