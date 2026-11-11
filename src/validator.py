from decimal import Decimal

REQUIRED_FIELDS = (
    "invoice_number", "vendor", "invoice_date", "currency",
    "subtotal", "tax", "total",
)

def validate_invoice(record: dict, tolerance=Decimal("0.01")) -> tuple[bool, list[str]]:
    reasons = []
    for field in REQUIRED_FIELDS:
        if record.get(field) in (None, ""):
            reasons.append(f"Missing or unrecognized required field: {field}")

    amounts = (record.get("subtotal"), record.get("tax"), record.get("total"))
    if all(value is not None for value in amounts):
        if any(not isinstance(value, Decimal) for value in amounts):
            reasons.append("Amounts must be Decimal values")
        elif abs(record["subtotal"] + record["tax"] - record["total"]) > tolerance:
            reasons.append("Subtotal + tax does not equal total")

    if record.get("currency") and record["currency"] not in {"INR", "USD", "EUR", "GBP"}:
        reasons.append("Unsupported or ambiguous currency")

    return not reasons, reasons
