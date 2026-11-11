import sqlite3
import hashlib
from pathlib import Path

SCHEMA = (Path(__file__).resolve().parent.parent / "database" / "schema.sql").read_text(
    encoding="utf-8"
)


class InvoiceConflictError(ValueError):
    def __init__(self, invoice_id, differing_fields):
        self.invoice_id = invoice_id
        self.differing_fields = differing_fields
        fields = ", ".join(differing_fields)
        super().__init__(
            f"Existing invoice number/vendor has conflicting values: {fields}"
        )

def connect(db_path):
    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA)
    return connection

def _normalize_vendor(vendor):
    return " ".join(vendor.casefold().split())

def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def save_valid_invoice(connection, record):
    vendor_key = _normalize_vendor(record["vendor"])
    values = (
        record["invoice_date"],
        record["currency"],
        str(record["subtotal"]),
        str(record["tax"]),
        str(record["total"]),
    )
    connection.execute(
        """INSERT INTO invoices
        (invoice_number, vendor_normalized, vendor, invoice_date, currency,
         subtotal, tax, total)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(invoice_number, vendor_normalized) DO NOTHING""",
        (record["invoice_number"], vendor_key, record["vendor"],
         record["invoice_date"], record["currency"], str(record["subtotal"]),
         str(record["tax"]), str(record["total"]))
    )
    row = connection.execute(
        """SELECT id, invoice_date, currency, subtotal, tax, total
        FROM invoices WHERE invoice_number=? AND vendor_normalized=?""",
        (record["invoice_number"], vendor_key)
    ).fetchone()
    existing_values = row[1:]
    field_names = ("invoice_date", "currency", "subtotal", "tax", "total")
    differing_fields = [
        field for field, existing, incoming in zip(field_names, existing_values, values)
        if existing != str(incoming)
    ]
    if differing_fields:
        raise InvoiceConflictError(row[0], differing_fields)
    return row[0]

def record_source(connection, invoice_id, source_path, ocr_text_path,
                  status, reasons=None):
    path = Path(source_path)
    digest = _sha256(path)
    source_key = path.name
    raw_text_key = (Path("raw_ocr") / Path(ocr_text_path).name).as_posix() if ocr_text_path else None
    connection.execute(
        """INSERT INTO source_scans
        (invoice_id, source_filename, source_path, sha256, ocr_text_path,
         import_status, review_reasons)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_path, sha256) DO UPDATE SET
          invoice_id=excluded.invoice_id,
          ocr_text_path=excluded.ocr_text_path,
          import_status=excluded.import_status,
          review_reasons=excluded.review_reasons""",
        (invoice_id, path.name, source_key, digest, raw_text_key,
         status, "; ".join(reasons or []))
    )
