import argparse
import csv
import json
import sys
from pathlib import Path
from PIL import Image
import pytesseract

from src.extractor import extract_invoice_fields, json_safe_record
from src.validator import validate_invoice
from src.db import InvoiceConflictError, connect, save_valid_invoice, record_source

SUPPORTED_IMAGES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}

def process_directory(input_dir, output_dir, db_path):
    input_dir, output_dir = Path(input_dir), Path(output_dir)
    raw_dir = output_dir / "raw_ocr"
    raw_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    results = []
    connection = connect(db_path)
    try:
        for image_path in sorted(p for p in input_dir.iterdir()
                                 if p.is_file() and p.suffix.lower() in SUPPORTED_IMAGES):
            text_path = raw_dir / f"{image_path.stem}.txt"
            try:
                with Image.open(image_path) as image:
                    ocr_text = pytesseract.image_to_string(image, config="--psm 6")
                text_path.write_text(ocr_text, encoding="utf-8")
                record = extract_invoice_fields(ocr_text)
                is_valid, reasons = validate_invoice(record)
                invoice_id = None
                if is_valid:
                    try:
                        invoice_id = save_valid_invoice(connection, record)
                    except InvoiceConflictError as exc:
                        invoice_id = exc.invoice_id
                        is_valid = False
                        reasons.append(str(exc))
                status = "valid" if is_valid else "needs_review"
                record_source(connection, invoice_id, image_path, text_path,
                              status, reasons)
                results.append({
                    "source_filename": image_path.name,
                    "status": status,
                    "record": json_safe_record(record),
                    "validation": {"valid": is_valid, "reasons": reasons},
                    "database_invoice_id": invoice_id,
                    "raw_ocr_file": text_path.relative_to(output_dir).as_posix(),
                })
            except Exception as exc:
                # A corrupt/unreadable image must not stop the remaining files.
                results.append({
                    "source_filename": image_path.name,
                    "status": "needs_review",
                    "record": None,
                    "validation": {
                        "valid": False,
                        "reasons": [f"Image processing failed: {type(exc).__name__}: {exc}"],
                    },
                    "database_invoice_id": None,
                    "raw_ocr_file": str(text_path.relative_to(output_dir))
                        if text_path.exists() else None,
                })
                try:
                    record_source(connection, None, image_path, None,
                                  "needs_review", results[-1]["validation"]["reasons"])
                except Exception as source_error:
                    reason = (
                        f"Could not record source scan: "
                        f"{type(source_error).__name__}: {source_error}"
                    )
                    results[-1]["validation"]["reasons"].append(reason)
                    print(f"{image_path.name}: {reason}", file=sys.stderr)
            connection.commit()
    finally:
        connection.close()

    (output_dir / "extracted_records.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    review = [item for item in results if item["status"] == "needs_review"]
    (output_dir / "needs_review.json").write_text(
        json.dumps(review, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    csv_path = output_dir / "extracted_records.csv"
    csv_fields = (
        "source_filename", "status", "invoice_number", "vendor", "invoice_date",
        "currency", "subtotal", "tax", "total", "validation_valid",
        "review_reasons", "database_invoice_id", "raw_ocr_file",
    )
    with csv_path.open("w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=csv_fields)
        writer.writeheader()
        for item in results:
            record = item["record"] or {}
            writer.writerow({
                "source_filename": item["source_filename"],
                "status": item["status"],
                **record,
                "validation_valid": item["validation"]["valid"],
                "review_reasons": "; ".join(item["validation"]["reasons"]),
                "database_invoice_id": item["database_invoice_id"],
                "raw_ocr_file": item["raw_ocr_file"],
            })
    print(f"Processed {len(results)} image(s); {len(review)} need review.")
    print(
        f"Reports: {output_dir / 'extracted_records.json'}, "
        f"{output_dir / 'needs_review.json'}, and {csv_path}"
    )

def main():
    parser = argparse.ArgumentParser(description="OCR, validate and import invoice scans.")
    parser.add_argument("--input", default="input", help="Directory containing invoice images")
    parser.add_argument("--output", default="output", help="Directory for OCR text and JSON reports")
    parser.add_argument("--db", default="invoices.sqlite3", help="SQLite database path")
    args = parser.parse_args()
    process_directory(args.input, args.output, args.db)

if __name__ == "__main__":
    main()
