# Invoice OCR Validator

A local Python CLI application that processes invoice images using Tesseract OCR, extracts structured invoice data, validates required fields and financial calculations, stores valid invoices in SQLite, and generates JSON reports for records requiring manual review.

## Features

- OCR extraction using Tesseract and pytesseract.
- Invoice field extraction using label-based parsing.
- Required-field and financial arithmetic validation.
- Date normalization to ISO `YYYY-MM-DD`.
- Monetary value handling using Python `Decimal`.
- Duplicate invoice detection.
- SQLite persistence with source-scan traceability.
- JSON reports for extracted records and manual review.
- Automated tests using pytest.

## Requirements

- Python 3.10+
- Tesseract OCR executable
- Python packages listed in `requirements.txt`

## Installation

### Ubuntu / Debian

```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr

python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

### macOS

```bash
brew install tesseract

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

### Windows

1. Install Tesseract OCR using the UB Mannheim Windows builds.
2. Add the Tesseract installation directory to the Windows PATH environment variable.
3. Open a new CMD terminal and verify the installation:

```cmd
tesseract --version
```

4. Create and activate a virtual environment:

```cmd
python -m venv venv
venv\Scripts\activate
```

5. Install the Python dependencies:

```cmd
python -m pip install -r requirements.txt
```

If Tesseract is installed but not on PATH, add its location for the current PowerShell session before running the CLI:

```powershell
$env:PATH = "C:\Program Files\Tesseract-OCR;$env:PATH"
tesseract --version
.\venv\Scripts\python.exe -m src.main --input input --output output --db invoices.sqlite3
```

## Input Fixtures

Place the four supplied invoice images inside the `input/` directory:

- [invoice-101.png](https://thenightmarketer.com/client/hiring/fixtures/invoice-101.png)
- [invoice-102.png](https://thenightmarketer.com/client/hiring/fixtures/invoice-102.png)
- [invoice-101-copy.png](https://thenightmarketer.com/client/hiring/fixtures/invoice-101-copy.png)
- [invoice-103-review.png](https://thenightmarketer.com/client/hiring/fixtures/invoice-103-review.png)

The application performs OCR on the images found in the input directory. It does not hardcode the expected fixture results.

## Running the Application

From the project root:

```bash
python -m src.main --input input --output output --db invoices.sqlite3
```

The application generates:

| Output | Description |
|---|---|
| `output/raw_ocr/` | Raw OCR text files |
| `output/extracted_records.json` | Processing results for all source images |
| `output/needs_review.json` | Records requiring manual review |
| `output/extracted_records.csv` | Tabular report with extracted fields and validation reasons |
| `invoices.sqlite3` | SQLite database containing invoice and source-scan records |

Run the same command again to verify repeatability and duplicate handling.

Invoice records use a unique identity based on invoice number and normalized vendor name. If that identity already exists but the date, currency, or amounts differ, the incoming scan is retained and marked `needs_review` rather than silently discarded. Source scans are upserted using the input filename and SHA-256 content hash, rather than a machine-specific absolute path.

The connection setup reads and executes `database/schema.sql`; it does not rewrite or clean existing scan rows on connection.

## Running Tests

Install dependencies if not already installed:

```bash
python -m pip install -r requirements.txt
```

Run the automated test suite:

```bash
python -m pytest -q
```

The tests use controlled OCR text and in-memory SQLite. They do not depend on the local Tesseract version or fixture-image OCR output.

## Data and Validation Decisions

- Dates are normalized to ISO `YYYY-MM-DD`.
- Monetary values are parsed using `Decimal` and serialized as decimal strings.
- SQLite stores monetary values as TEXT to avoid binary floating-point precision issues.
- A valid invoice requires an invoice number, vendor, date, currency, subtotal, tax, and total.
- The financial validation allows a one-cent rounding tolerance.
- Duplicate invoice identity is `(invoice_number, normalized vendor name)`.
- Invoice numbers are not assumed to be globally unique across vendors.
- Source scans retain their original traceability and link to the corresponding invoice when valid.
- Missing or unrecognized values are sent to manual review rather than guessed.
- Numeric dates using `/` or `-` are interpreted as `DD/MM/YYYY` or `DD-MM-YYYY`; ISO `YYYY-MM-DD` and English month names are also supported. This day-first convention matches the supplied fixtures.
- Ambiguous monetary amounts are sent to manual review rather than interpreted using an assumed locale.
- Currency recognition is limited to INR, USD, EUR, and GBP.

## Relevant Technical Experience

I have not yet personally resolved a Python/database issue in a SQL-backed project. My closest relevant technical problem was in my skin-lesion classification project using the MILK10k dataset: combining clinical images, dermoscopic images, and patient metadata in one Python training pipeline while addressing class imbalance.

**My contribution:** I handled image preprocessing, metadata cleaning and integration, categorical encoding, numerical normalization, stratified train/validation preparation, and model implementation and evaluation. I implemented a dual-input EfficientNetV2-S model combining both image types with metadata, and used image augmentation and class-weighted loss to address imbalance. Broader project coordination and team-level decisions were separate from my individual implementation and experiments.

**Verification:** I checked the merged data and confirmed 5,164 lesions had both image types, then checked the stratified split and evaluated validation loss, accuracy, and macro F1. The best reported validation accuracy was 75.94%, with macro F1 of 0.2572, highlighting remaining performance issues for underrepresented classes.

**Data storage:** The project used MILK10k images and CSV ground-truth/metadata files; it did not use a SQL database. This assignment CLI uses SQLite.

## Application Answers

1. **Name and role:** Farhan Khan — Junior Python Developer
2. **City/locality and office attendance:** Okhla, Delhi; yes, I can commute to the Wazirpur/Shalimar Bagh office full-time.
3. **Compensation and availability:** Current/last CTC: ₹4,80,000 per annum (approximately ₹40,000/month). Expected monthly salary: as per company standards; negotiable. The advertised ₹20,000–₹30,000/month range is discussable. Notice period: immediate. Earliest joining: immediately/as soon as possible.
4. **Experience and project:** 8 months of professional development experience, excluding internships. Relevant project: AI-based skin cancer detection for the ISIC challenge using MILK10k. Personal contribution and data storage are described above.

## Limitations and Future Improvements

- The extractor uses label-based regular expressions, so unusual invoice layouts and OCR errors may require manual review.
- Handwritten text and low-resolution scans may reduce OCR accuracy.
- Vendor extraction currently uses a conservative first-line heuristic.
- Production use could benefit from vendor-specific templates and confidence-aware extraction.
- Add human correction after extraction and before approval: retain original OCR text, store corrected values with reviewer and timestamp, and link corrections to `source_scans`.
- Add bounded retries around transient image/OCR failures in `process_directory`; ambiguous fields should go to review, not be retried as if they were transient errors.
- Image preprocessing such as deskewing, denoising, and contrast enhancement could improve OCR results.
- Additional improvements could include structured logging, schema migrations, and stronger concurrency handling.

## Sample Fixture Results

The existing `output/` directory contains a run of the four supplied images. Tesseract is installed at `C:\Program Files\Tesseract-OCR\tesseract.exe`; it may need to be added to PATH in a new shell as shown above. The OCR fixtures are processed at runtime; their answers are not hardcoded.

| Image | Sample result |
|---|---|
| `invoice-101.png` | Valid TNM-101 invoice |
| `invoice-101-copy.png` | Valid duplicate of TNM-101 |
| `invoice-102.png` | Valid TNM-102 invoice |
| `invoice-103-review.png` | Needs review |

The sample TNM-103 record is flagged for two reasons:

1. The invoice date was missing or unrecognized.
2. The subtotal and tax add up to 1180.00, while the printed total is 1170.00.

### Observed Sample Counts

The existing sample output and database contain:

- Images processed: 4
- Valid source records: 3
- Records requiring manual review: 1
- Unique valid invoices in SQLite: 2
- Source scans in SQLite: 4
- Automated tests: 10 passed in the project virtual environment
- Repeat-import behavior: covered by the automated tests

The two TNM-101 images remain separately traceable as source scans while sharing one invoice record.

## Candidate Completion Details

- Actual time spent: approximately 1.5–2 hours.
- Environment used for this implementation: Windows, Python, SQLite, Tesseract OCR.
- AI use: GitHub Copilot assisted with implementation and review.