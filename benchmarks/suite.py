"""Reproducible comparison across paired synthetic mortgage fixtures."""

import argparse
import io
import json
import os
import random
from collections import Counter
from time import perf_counter

import pymupdf as fitz
from PIL import Image, ImageFilter

from backend.app.extraction import SCHEMAS, TITLES, extract, vision_candidates, vision_image_edge
from backend.app.layout import extract_layout
from .run import values_for

CONDITIONS = ("plain", "split_columns", "scanned", "blurred_scan", "rotated_scan", "missing_field", "contradiction")
LOCAL_MODES = ("rules", "layout", "layout_verified")
VISION_MODES = ("vision", "verified")

def vision_available():
    return bool(os.getenv("VISION_ENDPOINT") and os.getenv("VISION_MODEL"))

def create_fixture(kind, values, condition):
    omit = next(iter(values)) if condition == "missing_field" else None
    conflict = next(iter(values)) if condition == "contradiction" else None
    with fitz.open() as pdf:
        page = pdf.new_page()
        page.insert_text((58, 64), TITLES[kind], fontsize=18)
        page.insert_text((58, 88), "SYNTHETIC RESEARCH FIXTURE", fontsize=11)
        y = 127
        for key, label in SCHEMAS[kind].items():
            if key == omit:
                continue
            if condition == "split_columns":
                page.insert_text((58, y), label + ":", fontsize=13)
                page.insert_text((285, y), values[key], fontsize=13)
            else:
                page.insert_text((58, y), f"{label}: {values[key]}", fontsize=13)
            y += 27
        if conflict:
            page.insert_text((58, y), f"{SCHEMAS[kind][conflict]}: Fictional Alternate Name", fontsize=13)
        if condition in {"scanned", "blurred_scan", "rotated_scan"}:
            pixels = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            image = Image.frombytes("RGB", (pixels.width, pixels.height), pixels.samples)
            if condition == "blurred_scan":
                image = image.filter(ImageFilter.GaussianBlur(1.9))
            if condition == "rotated_scan":
                image = image.rotate(4, fillcolor="white")
            result = io.BytesIO()
            image.save(result, format="PNG")
            return result.getvalue(), "image/png", omit, conflict
        return pdf.tobytes(), "application/pdf", omit, conflict

def run_suite(seed, modes, conditions=CONDITIONS, repetitions=1, progress=None):
    rng = random.Random(seed)
    fixtures = []
    for condition in conditions:
        for _ in range(repetitions):
            values = values_for(f"Fictional Borrower {rng.randrange(10000,99999)}")
            for kind, expected in values.items():
                content, media, omit, conflict = create_fixture(kind, expected, condition)
                truth = {key: value for key, value in expected.items() if key not in {omit, conflict}}
                fixtures.append((condition, kind, content, media, truth, conflict))
    report = {"seed": seed, "repetitions": repetitions, "fixture_count": len(fixtures), "modes": {},
              "vision_model": os.getenv("VISION_MODEL") if set(modes) & set(VISION_MODES) else None,
              "vision_image_edge": vision_image_edge() if set(modes) & set(VISION_MODES) else None,
              "vision_json_schema": os.getenv("VISION_JSON_SCHEMA") == "1" if set(modes) & set(VISION_MODES) else None}
    proposals = {}
    for mode in modes:
        report["modes"][mode] = evaluate_mode(mode, fixtures, conditions, proposals, progress)
    return report

def evaluate_mode(mode, fixtures, conditions, proposals, progress):
    totals = {condition: Counter() for condition in conditions}
    confusion = {condition: Counter() for condition in conditions}
    for index, (condition, expected_kind, content, media, truth, conflict) in enumerate(fixtures):
        if progress:
            progress()
        model_ms = 0.0
        page = 0
        def propose(text, image):
            nonlocal model_ms, page
            page += 1
            key = (index, page)
            if key not in proposals:
                began = perf_counter()
                try:
                    response = vision_candidates(text, image)
                except Exception as error:
                    response = error
                proposals[key] = (response, (perf_counter() - began) * 1000)
            else:
                model_ms += proposals[key][1]
            response = proposals[key][0]
            if isinstance(response, Exception):
                row["provider_errors"] += 1
                raise response
            return response
        row = totals[condition]
        start = perf_counter()
        try:
            if mode.startswith("layout"):
                kind, fields = extract_layout(content, media, verify=mode == "layout_verified")
            else:
                kind, fields = extract(content, media, mode, propose=propose)
        except Exception:
            kind, fields = "unknown", []
            row["processing_errors"] += 1
        row["elapsed_ms"] += (perf_counter() - start) * 1000 + model_ms
        confusion[condition][expected_kind, kind] += 1
        emitted = {field["key"]: field for field in fields if field["value"]}
        flagged = {field["key"] for field in fields if field.get("conflict")}
        correct = {key for key, field in emitted.items() if key in truth and field["value"] == truth[key]}
        row.update(documents=1, correct_types=int(expected_kind == kind), expected=len(truth), correct=len(correct),
                   emitted=len(emitted), supported=sum(key in truth for key in emitted),
                   evidence=sum(emitted[key]["page"] == 1 and bool(emitted[key]["source"]) for key in correct),
                   review_fields=len(set(truth) - set(emitted)) + len(flagged),
                   true_conflicts=int(conflict is not None), detected_conflicts=int(conflict in flagged),
                   flagged_conflicts=len(flagged))
    return {condition: summarize(totals[condition], confusion[condition]) for condition in conditions}

def summarize(row, matrix):
    def divide(a, b):
        return a / b if b else None
    f1s = []
    for kind in SCHEMAS:
        tp = matrix[kind, kind]
        errors = sum(count for (expected, predicted), count in matrix.items()
                     if (expected == kind) != (predicted == kind))
        f1s.append(divide(2 * tp, 2 * tp + errors) or 0)
    return {
        **dict(row), "processing_errors": row["processing_errors"], "provider_errors": row["provider_errors"],
        "unsupported": row["emitted"] - row["supported"],
        "field_accuracy": divide(row["correct"], row["expected"]),
        "coverage": divide(row["supported"], row["expected"]),
        "unsupported_rate": divide(row["emitted"] - row["supported"], row["emitted"]),
        "evidence_page_accuracy": divide(row["evidence"], row["correct"]),
        "conflict_precision": divide(row["detected_conflicts"], row["flagged_conflicts"]),
        "conflict_recall": divide(row["detected_conflicts"], row["true_conflicts"]),
        "macro_f1": sum(f1s) / len(f1s), "mean_ms": divide(row["elapsed_ms"], row["documents"]),
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=81)
    parser.add_argument("--repetitions", type=int, choices=range(1, 11), default=1)
    parser.add_argument("--vision", action="store_true")
    args = parser.parse_args()
    if args.vision and not vision_available():
        parser.error("Set VISION_ENDPOINT and VISION_MODEL first.")
    print(json.dumps(run_suite(args.seed, LOCAL_MODES + VISION_MODES if args.vision else LOCAL_MODES,
                               repetitions=args.repetitions), indent=2))
