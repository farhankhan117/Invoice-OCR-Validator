import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

def _label_value(text: str, label: str):
    match = re.search(rf"(?im)^\s*(?:{label})\s*:\s*(.*?)\s*$", text)
    return match.group(1).strip() if match else None

def _amount(value):
    if not value or re.search(r"[?□]", value):
        return None
    match = re.search(r"[-+]?\s*\d[\d.,]*", value)
    if not match:
        return None

    currency_marker = r"(?:INR|USD|EUR|GBP|RS\.?|₹|\$|€|£)"
    prefix, suffix = value[:match.start()].strip(), value[match.end():].strip()
    if any(part and not re.fullmatch(currency_marker, part, re.IGNORECASE)
           for part in (prefix, suffix)):
        return None

    token = match.group(0).replace(" ", "")
    sign = ""
    if token[:1] in "+-":
        sign, token = token[0], token[1:]

    if "," in token and "." in token:
        decimal_separator = "." if token.rfind(".") > token.rfind(",") else ","
        grouping_separator = "," if decimal_separator == "." else "."
        integer, fraction = token.rsplit(decimal_separator, 1)
        if not re.fullmatch(rf"\d{{1,3}}(?:{re.escape(grouping_separator)}\d{{3}})+|\d+", integer):
            return None
        if not re.fullmatch(r"\d{1,2}", fraction):
            return None
        token = integer.replace(grouping_separator, "") + "." + fraction
    elif "," in token or "." in token:
        separator = "," if "," in token else "."
        if token.count(separator) > 1:
            if not re.fullmatch(rf"\d{{1,3}}(?:{re.escape(separator)}\d{{3}})+", token):
                return None
            token = token.replace(separator, "")
        else:
            integer, fraction = token.split(separator)
            if len(fraction) == 3 and 1 <= len(integer) <= 3:
                return None
            if not integer.isdigit() or not re.fullmatch(r"\d{1,2}", fraction):
                return None
            token = integer + "." + fraction
    elif not token.isdigit():
        return None

    try:
        return Decimal(sign + token).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None

def _date(value):
    if not value or "[" in value or "]" in value:
        return None
    value = value.strip()

    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y",
                "%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return None

def extract_invoice_fields(ocr_text: str) -> dict:
    invoice_raw = _label_value(ocr_text, r"Invoice(?:\s*(?:No|Number|#))?")
    vendor_raw = _label_value(ocr_text, r"Vendor")
    date_raw = _label_value(ocr_text, r"(?:Invoice\s*)?Date")
    currency_raw = _label_value(ocr_text, r"Currency")
    return {
        "invoice_number": invoice_raw.split()[0].strip(",:;") if invoice_raw else None,
        "vendor": vendor_raw.strip() if vendor_raw else None,
        "invoice_date": _date(date_raw),
        "currency": currency_raw.upper() if currency_raw else None,
        "subtotal": _amount(_label_value(ocr_text, r"Sub\s*total")),
        "tax": _amount(_label_value(ocr_text, r"Tax|VAT|GST")),
        "total": _amount(_label_value(ocr_text, r"Total")),
    }

def json_safe_record(record: dict) -> dict:
    return {key: str(value) if isinstance(value, Decimal) else value
            for key, value in record.items()}
