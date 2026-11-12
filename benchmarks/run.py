import argparse
import json
import random

import pymupdf as fitz

from backend.app.extraction import TITLES, SCHEMAS, extract

def fixture(kind, values, layout=0, omit=None):
    with fitz.open() as pdf:
        page = pdf.new_page()
        x, y = ((60, 75), (115, 175), (85, 290))[layout]
        lines = [TITLES[kind], "SYNTHETIC RESEARCH FIXTURE"]
        lines.extend(f"{label}: {values[key]}" for key, label in SCHEMAS[kind].items() if key != omit)
        page.insert_text((x, y), "\n".join(lines), fontsize=14 if layout == 2 else 12)
        return pdf.tobytes()

def values_for(name):
    return {
        "pay_stub": {"employee_name": name, "pay_period_end": "2026-09-30", "gross_pay": "3500.00"},
        "bank_statement": {"account_holder": name, "statement_end": "2026-09-30", "ending_balance": "15000.00"},
        "identity": {"full_name": name, "expiration_date": "2032-01-01"},
        "purchase_agreement": {"buyer_name": name, "purchase_price": "325000.00", "agreement_date": "2026-10-01"},
    }

def evaluate(mode, seed):
    rng = random.Random(seed)
    groups = {}
    for layout, condition in [(1, "held_out_layout"), (2, "missing_field")]:
        rows = groups[condition] = dict(documents=0, correct_types=0, expected=0, correct=0, emitted=0, unsupported=0)
        for i in range(4):
            name = f"Fictional Borrower {rng.randrange(10000,99999)}"
            for kind, values in values_for(name).items():
                omit = next(iter(values)) if condition == "missing_field" else None
                expected = {key: value for key, value in values.items() if key != omit}
                detected, fields = extract(fixture(kind, values, layout, omit), "application/pdf", mode)
                emitted = {f["key"]: f["value"] for f in fields if f["value"]}
                rows["documents"] += 1
                rows["correct_types"] += detected == kind
                rows["expected"] += len(expected)
                rows["correct"] += sum(expected.get(k) == v for k, v in emitted.items())
                rows["emitted"] += len(emitted)
                rows["unsupported"] += sum(k not in expected for k in emitted)
        rows["field_accuracy"] = rows["correct"] / rows["expected"]
        rows["coverage"] = (rows["emitted"] - rows["unsupported"]) / rows["expected"]
    return {"mode": mode, "seed": seed, "conditions": groups}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["text", "rules", "vision", "verified"], default="rules")
    parser.add_argument("--seed", type=int, default=81)
    args = parser.parse_args()
    import os
    if args.mode == "vision" and not (os.getenv("VISION_MODEL") and os.getenv("VISION_ENDPOINT")):
        parser.error("Set VISION_MODEL and VISION_ENDPOINT to evaluate vision extraction.")
    print(json.dumps(evaluate(args.mode, args.seed), indent=2))
