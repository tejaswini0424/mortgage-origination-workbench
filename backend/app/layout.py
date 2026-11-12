"""Spatial extraction from a page's rendered image and positioned words."""

import io
from collections import defaultdict

import pymupdf
from PIL import Image, ImageOps

from .extraction import SCHEMAS, TITLES, normalize, tesseract

def ocr_rows(image):
    pytesseract = tesseract()
    data = pytesseract.image_to_data(ImageOps.grayscale(image), output_type=pytesseract.Output.DICT, timeout=20)
    return [(left, top, left + width, top + height, value) for left, top, width, height, value in
            zip(data["left"], data["top"], data["width"], data["height"], data["text"]) if value.strip()]

def line_groups(words):
    groups = []
    for word in sorted(words, key=lambda w: (w[1] + w[3]) / 2):
        center = (word[1] + word[3]) / 2
        if groups and abs(center - groups[-1][0]) <= max(3, (word[3] - word[1]) * 0.55):
            groups[-1][1].append(word)
        else:
            groups.append((center, [word]))
    for _, row in groups:
        ordered = sorted(row, key=lambda word: word[0])
        yield " ".join(w[4] for w in ordered), [
            min(w[0] for w in row), min(w[1] for w in row), max(w[2] for w in row), max(w[3] for w in row)]

def read_layout(content, media):
    if media == "application/pdf":
        with pymupdf.open(stream=content, filetype="pdf") as document:
            if document.needs_pass or not 1 <= len(document) <= 30:
                raise ValueError("Use an unlocked PDF with 1 to 30 pages.")
            for page in document:
                words = [tuple(row[:5]) for row in page.get_text("words")]
                if not words:
                    scale = min(2, 1600 / max(page.rect.width, page.rect.height))
                    pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
                    words = ocr_rows(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
                    words = [tuple(v / scale for v in word[:4]) + (word[4],) for word in words]
                yield list(line_groups(words))
    else:
        with Image.open(io.BytesIO(content)) as image:
            if image.width * image.height > 16_000_000:
                raise ValueError("Image exceeds the 16 megapixel limit.")
            original_width = image.width
            image.thumbnail((1600, 1600))
            scale = image.width / original_width
            words = [tuple(v / scale for v in word[:4]) + (word[4],) for word in ocr_rows(image)]
            yield list(line_groups(words))

def extract_layout(content, media, verify=False, forced_kind=None):
    pages = list(read_layout(content, media))
    kind = forced_kind or next((key for key, title in TITLES.items()
                 if any(title in line.upper() for rows in pages for line, _ in rows)), "unknown")
    matches = defaultdict(list)
    for page, rows in enumerate(pages, 1):
        for line, box in rows:
            for key, label in SCHEMAS.get(kind, {}).items():
                if not line.casefold().startswith(label.casefold() + ":"):
                    continue
                try:
                    value = normalize(key, line[len(label) + 1:])
                except ValueError:
                    continue
                matches[key].append(dict(key=key, value=value, page=page, source=line, box=box, reviewed=False))
    fields = []
    for key in SCHEMAS.get(kind, {}):
        options = matches[key]
        conflict = len({field["value"].casefold() for field in options}) > 1
        if options and (not verify or not conflict):
            fields.append(options[0])
        else:
            fields.append(dict(key=key, value="", page=0, source="", reviewed=False, conflict=conflict))
    return kind, fields
