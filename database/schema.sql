PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_number TEXT NOT NULL,
    vendor_normalized TEXT NOT NULL,
    vendor TEXT NOT NULL,
    invoice_date TEXT NOT NULL,
    currency TEXT NOT NULL,
    subtotal TEXT NOT NULL,
    tax TEXT NOT NULL,
    total TEXT NOT NULL,
    UNIQUE(invoice_number, vendor_normalized)
);

CREATE TABLE IF NOT EXISTS source_scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER,
    source_filename TEXT NOT NULL,
    source_path TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    ocr_text_path TEXT,
    import_status TEXT NOT NULL,
    review_reasons TEXT,
    UNIQUE(source_path, sha256),
    FOREIGN KEY(invoice_id) REFERENCES invoices(id)
);
