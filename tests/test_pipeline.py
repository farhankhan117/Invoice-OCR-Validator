from decimal import Decimal
import csv
import json
from pathlib import Path
import sqlite3

from PIL import Image

from src.main import process_directory
from src.validator import validate_invoice
from src.db import SCHEMA, record_source, save_valid_invoice
from src.extractor import _amount, _date, extract_invoice_fields

VALID = {
    "invoice_number": "INV-101",
    "vendor": "Acme Supplies",
    "invoice_date": "2026-10-20",
    "currency": "INR",
    "subtotal": Decimal("1000.00"),
    "tax": Decimal("180.00"),
    "total": Decimal("1180.00"),
}

def test_valid_field_validation():
    valid, reasons = validate_invoice(VALID)
    assert valid is True
    assert reasons == []

def test_duplicate_repeated_import():
    connection = sqlite3.connect(":memory:")
    connection.executescript(SCHEMA)
    first_id = save_valid_invoice(connection, VALID)
    second_id = save_valid_invoice(connection, VALID)
    count = connection.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]
    assert first_id == second_id
    assert count == 1

def test_repeated_scan_import_is_idempotent_and_traceable(tmp_path):
    connection = sqlite3.connect(":memory:")
    connection.executescript(SCHEMA)
    invoice_id = save_valid_invoice(connection, VALID)
    first_scan = tmp_path / "invoice-101.png"
    first_scan.write_bytes(b"synthetic first scan")
    relocated_scan = tmp_path / "another-input-dir" / "invoice-101.png"
    relocated_scan.parent.mkdir()
    relocated_scan.write_bytes(first_scan.read_bytes())
    copy_scan = tmp_path / "invoice-101-copy.png"
    copy_scan.write_bytes(b"synthetic duplicate scan")

    record_source(connection, invoice_id, first_scan, None, "valid")
    record_source(connection, invoice_id, relocated_scan, None, "valid")
    record_source(connection, invoice_id, copy_scan, None, "valid")

    assert connection.execute("SELECT COUNT(*) FROM invoices").fetchone()[0] == 1
    scans = connection.execute(
        "SELECT source_filename, invoice_id FROM source_scans ORDER BY source_filename"
    ).fetchall()
    assert scans == [
        ("invoice-101-copy.png", invoice_id),
        ("invoice-101.png", invoice_id),
    ]

def test_incomplete_ambiguous_input():
    extracted = extract_invoice_fields(
        "ACME SUPPLIES\nInvoice No: INV-103\nDate: unclear\nSubtotal: 100.00"
    )
    valid, reasons = validate_invoice(extracted)
    assert valid is False
    assert any("invoice_date" in reason for reason in reasons)
    assert any("total" in reason for reason in reasons)

def test_numeric_date_uses_documented_day_month_year_convention():
    assert _date("01/10/2026") == "2026-10-01"
    assert _date("01/02/2026") == "2026-02-01"
    assert _date("13/02/2026") == "2026-02-13"
    assert _date("2026-10-01") == "2026-10-01"

def test_day_first_fixture_date_validates_and_deduplicates():
    duplicate = extract_invoice_fields("""Invoice: INV-101
Vendor: Acme Supplies
Date: 01/10/2026
Currency: INR
Subtotal: 1000.00
Tax: 180.00
Total: 1180.00
""")
    valid, reasons = validate_invoice(duplicate)
    assert valid is True
    assert reasons == []
    assert duplicate["invoice_date"] == "2026-10-01"
    connection = sqlite3.connect(":memory:")
    connection.executescript(SCHEMA)
    original = {**VALID, "invoice_date": "2026-10-01"}
    assert save_valid_invoice(connection, original) == save_valid_invoice(connection, duplicate)

def test_amount_locale_normalization_and_ambiguity():
    assert _amount("1,200.50") == Decimal("1200.50")
    assert _amount("1.200,50") == Decimal("1200.50")
    assert _amount("1.200") is None
    assert _amount("1,20O") is None

def test_unreadable_image_does_not_stop_directory_processing(tmp_path, monkeypatch):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    (input_dir / "00-broken.png").write_bytes(b"not an image")
    Image.new("RGB", (1, 1)).save(input_dir / "01-valid.png")
    monkeypatch.setattr(
        "src.main.pytesseract.image_to_string",
        lambda image, config: """Invoice: INV-101
Vendor: Acme
Date: 2026-10-20
Currency: INR
Subtotal: 100.00
Tax: 18.00
Total: 118.00
""",
    )
    output_dir = tmp_path / "output"

    process_directory(input_dir, output_dir, tmp_path / "invoices.sqlite3")

    results = json.loads((output_dir / "extracted_records.json").read_text(encoding="utf-8"))
    assert [item["status"] for item in results] == ["needs_review", "valid"]
    assert "Image processing failed" in results[0]["validation"]["reasons"][0]
    assert (output_dir / "raw_ocr" / "01-valid.txt").read_text(encoding="utf-8").startswith(
        "Invoice: INV-101"
    )
    with (output_dir / "extracted_records.csv").open(
        encoding="utf-8-sig", newline=""
    ) as csv_file:
        rows = list(csv.DictReader(csv_file))
    assert len(rows) == 2
    assert rows[1]["raw_ocr_file"] == "raw_ocr/01-valid.txt"


def test_conflicting_invoice_values_are_sent_to_review(tmp_path, monkeypatch):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    Image.new("RGB", (1, 1)).save(input_dir / "invoice-first.png")
    Image.new("RGB", (1, 1)).save(input_dir / "invoice-conflict.png")
    texts = {
        "invoice-first.png": """Invoice: INV-201
Vendor: Acme Supplies
Date: 20/10/2026
Currency: INR
Subtotal: 100.00
Tax: 18.00
Total: 118.00
""",
        "invoice-conflict.png": """Invoice: INV-201
Vendor: Acme Supplies
Date: 20/10/2026
Currency: INR
Subtotal: 200.00
Tax: 36.00
Total: 236.00
""",
    }
    monkeypatch.setattr(
        "src.main.pytesseract.image_to_string",
        lambda image, config: texts[Path(image.filename).name],
    )
    output_dir = tmp_path / "output"
    db_path = tmp_path / "invoices.sqlite3"

    process_directory(input_dir, output_dir, db_path)

    results = json.loads((output_dir / "extracted_records.json").read_text(encoding="utf-8"))
    assert [item["status"] for item in results] == ["valid", "needs_review"]
    assert "conflicting values" in results[1]["validation"]["reasons"][0]
    with sqlite3.connect(db_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM invoices").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM source_scans").fetchone()[0] == 2


def test_fixture_style_extraction():
    text = """SYNTHETIC TEST INVOICE
Invoice: TNM-101
Vendor: Acme Office Supplies
Date: 2026-10-01
Currency: INR
Subtotal: 1,200.50
Tax: 216.09
Total: 1,416.59
"""
    record = extract_invoice_fields(text)
    assert record["invoice_number"] == "TNM-101"
    assert record["vendor"] == "Acme Office Supplies"
    assert record["invoice_date"] == "2026-10-01"
    assert record["subtotal"] == Decimal("1200.50")
    assert record["total"] == Decimal("1416.59")
