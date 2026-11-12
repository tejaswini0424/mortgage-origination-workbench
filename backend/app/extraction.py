import base64
import io
import json
import os
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pymupdf as fitz
import httpx
from PIL import Image, ImageChops, ImageOps

SCHEMAS = {
    "pay_stub": {"employee_name": "Employee Name", "pay_period_end": "Pay Period End", "gross_pay": "Gross Pay"},
    "bank_statement": {"account_holder": "Account Holder", "statement_end": "Statement End", "ending_balance": "Ending Balance"},
    "identity": {"full_name": "Full Name", "expiration_date": "Expiration Date"},
    "purchase_agreement": {"buyer_name": "Buyer Name", "purchase_price": "Purchase Price", "agreement_date": "Agreement Date"},
}
TITLES = {"pay_stub": "PAY STUB", "bank_statement": "BANK STATEMENT", "identity": "IDENTITY DOCUMENT", "purchase_agreement": "PURCHASE AGREEMENT"}
AMOUNTS = {"gross_pay", "ending_balance", "purchase_price"}
DATES = {"pay_period_end", "statement_end", "expiration_date", "agreement_date"}
NAMES = {"employee_name", "account_holder", "full_name", "buyer_name"}

def normalize(key, value):
    value = value.strip()
    if not value:
        raise ValueError("Enter a field value.")
    if key in AMOUNTS:
        try:
            amount = Decimal(value.replace("$", "").replace(",", ""))
            if not amount.is_finite() or abs(amount) > 1_000_000_000 or (amount < 0 and key != "ending_balance"):
                raise ValueError
            return str(amount.quantize(Decimal("0.01")))
        except (InvalidOperation, ValueError):
            raise ValueError("Enter a valid amount.") from None
    if key in DATES:
        try:
            return date.fromisoformat(value).isoformat()
        except ValueError:
            raise ValueError("Enter a date in YYYY-MM-DD format.") from None
    return " ".join(value.split())

def tesseract():
    import pytesseract
    windows_path = Path("C:/Program Files/Tesseract-OCR/tesseract.exe")
    executable = os.getenv("TESSERACT_CMD") or (str(windows_path) if os.name == "nt" and windows_path.is_file() else None)
    if executable:
        pytesseract.pytesseract.tesseract_cmd = executable
    return pytesseract

def ocr(image):
    return tesseract().image_to_string(image, timeout=20)

def read_pages(content, media, use_ocr, render):
    if media == "application/pdf":
        with fitz.open(stream=content, filetype="pdf") as pdf:
            if pdf.needs_pass or not 1 <= len(pdf) <= 30:
                raise ValueError("Use an unlocked PDF with 1 to 30 pages.")
            for page in pdf:
                text = page.get_text()
                image = None
                if render or (use_ocr and not text.strip()):
                    scale = min(2, 1500 / max(page.rect.width, page.rect.height))
                    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
                    image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                if use_ocr and not text.strip():
                    text = ocr(image)
                yield text, image
    else:
        with Image.open(io.BytesIO(content)) as image:
            if image.width * image.height > 16_000_000:
                raise ValueError("Image exceeds the 16 megapixel limit.")
            image.thumbnail((1800, 1800))
            image = image.convert("RGB")
            yield ocr(image) if use_ocr else "", image if render else None

def vision_image_edge():
    return max(256, min(2000, int(os.getenv("VISION_IMAGE_EDGE", "1024"))))

def vision_response_format():
    if os.getenv("VISION_JSON_SCHEMA") != "1":
        return {"type": "json_object"}
    properties = {key: {"type": "string", "maxLength": 96}
                  for fields in SCHEMAS.values() for key in fields}
    return {"type": "json_schema", "json_schema": {"name": "mortgage_fields", "schema": {
        "type": "object",
        "properties": {"kind": {"enum": [*SCHEMAS, "unknown"]},
                       "fields": {"type": "object", "properties": properties, "additionalProperties": False}},
        "required": ["kind", "fields"], "additionalProperties": False,
    }}}

def vision_candidates(text, image):
    model = os.environ["VISION_MODEL"]
    buffer = io.BytesIO()
    gray = ImageOps.grayscale(image)
    border = ImageChops.invert(gray).point(lambda value: 255 if value > 42 else 0).getbbox()
    if border:
        left, top, right, bottom = border
        image = image.crop((max(0, left - 20), max(0, top - 20), min(image.width, right + 20), min(image.height, bottom + 20)))
    else:
        image = image.copy()
    edge = vision_image_edge()
    image.thumbnail((edge, edge))
    image.save(buffer, format="JPEG")
    encoded = base64.b64encode(buffer.getvalue()).decode()
    headers = {"Authorization": f"Bearer {os.environ['VISION_API_KEY']}"} if os.getenv("VISION_API_KEY") else {}
    keys = "; ".join(f"{kind}: {', '.join(fields)}" for kind, fields in SCHEMAS.items())
    response = httpx.post(os.environ["VISION_ENDPOINT"], headers=headers, timeout=60, json={
        "model": model, "temperature": 0, "max_tokens": 140,
        "response_format": vision_response_format(), "messages": [
            {"role": "system", "content": "Read the image and OCR. Return JSON with kind and fields. "
             "Use these kind and field names: " + keys + ". Field values are copied from the page. Omit absent or ambiguous values."},
            {"role": "user", "content": [
                {"type": "text", "text": text[:12000]},
                {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + encoded}},
            ]},
        ],
    })
    response.raise_for_status()
    try:
        result = json.loads(response.json()["choices"][0]["message"]["content"])
    except (KeyError, TypeError, IndexError, ValueError) as error:
        raise ValueError("The vision endpoint returned invalid JSON.") from error
    if not isinstance(result, dict):
        raise ValueError("The vision endpoint returned an invalid result.")
    kind = re.sub(r"[^a-z0-9]+", "_", str(result.get("kind", "")).casefold()).strip("_")
    if kind == "identity_document":
        kind = "identity"
    fields = result.get("fields", result)
    return kind if kind in SCHEMAS else "unknown", fields if isinstance(fields, dict) else {}

def proposed_fields(kind, pages, proposals):
    fields = []
    for key, label in SCHEMAS.get(kind, {}).items():
        candidate = dict(key=key, value="", source="", page=0, reviewed=False)
        for page, ((text, _), (_, fields_by_key)) in enumerate(zip(pages, proposals), 1):
            raw = fields_by_key.get(key)
            if not isinstance(raw, str):
                continue
            label_pattern = re.escape(label) + r"\s*:\s*"
            try:
                value = normalize(key, re.sub("^" + label_pattern, "", raw.strip(), flags=re.I))
            except ValueError:
                continue
            source = ""
            for line in text.splitlines():
                match = re.fullmatch(label_pattern + "(.+)", line.strip(), re.I)
                if match:
                    try:
                        if normalize(key, match.group(1)) == value:
                            source = line.strip()
                            break
                    except ValueError:
                        continue
            candidate.update(value=value, source=source, page=page)
            break
        fields.append(candidate)
    return fields

def extract(content, media, mode="verified", forced_kind=None, propose=vision_candidates):
    vision = mode in {"vision", "verified"} and bool(os.getenv("VISION_ENDPOINT") and os.getenv("VISION_MODEL"))
    pages = list(read_pages(content, media, mode != "text", vision))
    if vision:
        try:
            proposals = [propose(text, image) for text, image in pages]
        except (httpx.HTTPError, ValueError):
            if mode == "vision":
                raise
            proposals = []
        predicted = forced_kind or next((kind for kind, _ in proposals if kind != "unknown"), "unknown")
        model_fields = proposed_fields(predicted, pages, proposals)
        if mode == "vision":
            return predicted, model_fields
        from .layout import extract_layout
        layout_kind, corroborated = extract_layout(content, media, verify=True, forced_kind=forced_kind)
        if layout_kind == predicted:
            candidates = {field["key"]: field for field in model_fields}
            for field in corroborated:
                proposal = candidates.get(field["key"])
                if field["value"] and proposal and proposal["value"] and proposal["value"].casefold() != field["value"].casefold():
                    field.update(value="", page=0, source="", conflict=True)
                    field.pop("box", None)
        return layout_kind, corroborated
    kind = forced_kind or next((key for key, title in TITLES.items()
                               if any(title in text.upper() for text, _ in pages)), "unknown")
    fields = []
    for key, label in SCHEMAS.get(kind, {}).items():
        candidates = []
        for index, (text, _) in enumerate(pages, 1):
            candidates.extend((index, line.strip()) for line in text.splitlines())
        field = dict(key=key, value="", source="", page=0, reviewed=False)
        for index, line in candidates:
            match = re.fullmatch(re.escape(label) + r"\s*:\s*(.+)", line, re.I)
            if match:
                try:
                    value = normalize(key, match.group(1))
                except ValueError:
                    continue
                field.update(value=value, source=line[:500], page=index)
                break
        fields.append(field)
    return kind, fields
