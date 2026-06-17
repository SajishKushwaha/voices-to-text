import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PdfExtractionResult:
    extracted_text: str
    data: dict[str, Any]
    confidence: float
    used_ocr: bool
    warnings: list[str]


TEST_PATTERNS: list[dict[str, Any]] = [
    {"name": "Hemoglobin", "aliases": ["hemoglobin", "hb"], "unit": "g/dL", "low": 12, "high": 17.5, "critical_low": 7, "critical_high": 20},
    {"name": "WBC", "aliases": ["wbc", "white blood cells", "white blood cell"], "unit": "10^3/uL", "low": 4, "high": 11, "critical_low": 2, "critical_high": 30},
    {"name": "RBC", "aliases": ["rbc", "red blood cells", "red blood cell"], "unit": "10^6/uL", "low": 4.2, "high": 5.9, "critical_low": 2.5, "critical_high": 7},
    {"name": "Platelet Count", "aliases": ["platelet count", "platelets"], "unit": "10^3/uL", "low": 150, "high": 450, "critical_low": 50, "critical_high": 1000},
    {"name": "Blood Sugar", "aliases": ["blood sugar", "glucose", "fasting glucose"], "unit": "mg/dL", "low": 70, "high": 140, "critical_low": 50, "critical_high": 300},
    {"name": "HbA1c", "aliases": ["hba1c", "hb a1c", "glycated hemoglobin"], "unit": "%", "low": 4, "high": 5.7, "critical_low": None, "critical_high": 10},
    {"name": "Creatinine", "aliases": ["creatinine"], "unit": "mg/dL", "low": 0.6, "high": 1.3, "critical_low": None, "critical_high": 5},
    {"name": "Urea", "aliases": ["urea", "blood urea"], "unit": "mg/dL", "low": 15, "high": 40, "critical_low": None, "critical_high": 100},
    {"name": "Sodium", "aliases": ["sodium", "na+"], "unit": "mmol/L", "low": 135, "high": 145, "critical_low": 120, "critical_high": 160},
    {"name": "Potassium", "aliases": ["potassium", "k+"], "unit": "mmol/L", "low": 3.5, "high": 5.1, "critical_low": 2.8, "critical_high": 6.5},
    {"name": "Cholesterol", "aliases": ["cholesterol", "total cholesterol"], "unit": "mg/dL", "low": None, "high": 200, "critical_low": None, "critical_high": 300},
    {"name": "Triglycerides", "aliases": ["triglycerides", "tg"], "unit": "mg/dL", "low": None, "high": 150, "critical_low": None, "critical_high": 500},
    {"name": "HDL", "aliases": ["hdl"], "unit": "mg/dL", "low": 40, "high": None, "critical_low": 25, "critical_high": None},
    {"name": "LDL", "aliases": ["ldl"], "unit": "mg/dL", "low": None, "high": 100, "critical_low": None, "critical_high": 190},
    {"name": "ALT", "aliases": ["alt", "sgpt"], "unit": "U/L", "low": 7, "high": 56, "critical_low": None, "critical_high": 500},
    {"name": "AST", "aliases": ["ast", "sgot"], "unit": "U/L", "low": 10, "high": 40, "critical_low": None, "critical_high": 500},
    {"name": "Bilirubin", "aliases": ["bilirubin", "total bilirubin"], "unit": "mg/dL", "low": 0.1, "high": 1.2, "critical_low": None, "critical_high": 10},
    {"name": "TSH", "aliases": ["tsh", "thyroid stimulating hormone"], "unit": "uIU/mL", "low": 0.4, "high": 4.5, "critical_low": 0.01, "critical_high": 20},
    {"name": "T3", "aliases": ["t3", "triiodothyronine"], "unit": "ng/dL", "low": 80, "high": 180, "critical_low": None, "critical_high": None},
    {"name": "T4", "aliases": ["t4", "thyroxine"], "unit": "ug/dL", "low": 4.5, "high": 12.5, "critical_low": None, "critical_high": None},
]


class PdfExtractionService:
    def extract(self, pdf_path: Path) -> PdfExtractionResult:
        warnings: list[str] = []
        used_ocr = False
        text = self._extract_with_pdfplumber(pdf_path, warnings)

        if len(text.strip()) < 120:
            ocr_text = self._extract_with_ocr(pdf_path, warnings)
            if ocr_text.strip():
                text = ocr_text
                used_ocr = True

        data = self._extract_structured_data(text)
        confidence = self._confidence_score(data, text, used_ocr)
        if not text.strip():
            warnings.append("No extractable text found in PDF.")

        return PdfExtractionResult(
            extracted_text=text,
            data=data,
            confidence=confidence,
            used_ocr=used_ocr,
            warnings=warnings,
        )

    def _extract_with_pdfplumber(self, pdf_path: Path, warnings: list[str]) -> str:
        try:
            import pdfplumber
        except ImportError:
            warnings.append("pdfplumber is not installed.")
            return ""

        try:
            with pdfplumber.open(pdf_path) as pdf:
                pages = [page.extract_text(x_tolerance=1, y_tolerance=3) or "" for page in pdf.pages]
            return "\n".join(pages).strip()
        except Exception as error:
            warnings.append(f"pdfplumber extraction failed: {error}")
            return ""

    def _extract_with_ocr(self, pdf_path: Path, warnings: list[str]) -> str:
        try:
            from pdf2image import convert_from_path
            import pytesseract
        except ImportError:
            warnings.append("OCR fallback requires pdf2image and pytesseract.")
            return ""

        try:
            images = convert_from_path(str(pdf_path), dpi=200, fmt="png")
            return "\n".join(pytesseract.image_to_string(image) for image in images).strip()
        except Exception as error:
            warnings.append(f"OCR fallback failed: {error}")
            return ""

    def _extract_structured_data(self, text: str) -> dict[str, Any]:
        normalized = normalize_text(text)
        patient = {
            "patientName": find_field(normalized, ["patient name", "name"]),
            "patientId": find_field(normalized, ["patient id", "patient no", "uhid", "mrn"]),
            "age": find_field(normalized, ["age"]),
            "gender": find_field(normalized, ["gender", "sex"]),
            "dateOfBirth": find_field(normalized, ["date of birth", "dob"]),
            "reportDate": find_field(normalized, ["report date", "date"]),
        }

        tests = extract_tests(normalized)
        known_names = {test["name"].lower() for test in tests}
        for biomarker in extract_additional_biomarkers(normalized, known_names):
            tests.append(biomarker)

        critical_alerts = [
            f"{test['name']} is critical at {test['value']} {test.get('unit') or ''}".strip()
            for test in tests
            if test.get("critical")
        ]

        return {
            **patient,
            "tests": tests,
            "criticalAlerts": critical_alerts,
        }

    def _confidence_score(self, data: dict[str, Any], text: str, used_ocr: bool) -> float:
        field_count = sum(1 for key in ["patientName", "age", "gender", "reportDate"] if data.get(key))
        test_count = len(data.get("tests", []))
        base = 0.25
        score = base + min(field_count * 0.08, 0.32) + min(test_count * 0.045, 0.38)
        if used_ocr:
            score -= 0.08
        if len(text.strip()) < 120:
            score -= 0.12
        return round(max(0.05, min(score, 0.98)), 2)


def normalize_text(text: str) -> str:
    return re.sub(r"[ \t]+", " ", text.replace("\r", "\n"))


def find_field(text: str, labels: list[str]) -> str:
    for label in labels:
        pattern = re.compile(
            rf"\b{re.escape(label)}\b\s*[:\-]?\s*([A-Za-z0-9 .,/+-]+)",
            re.IGNORECASE,
        )
        match = pattern.search(text)
        if match:
            value = match.group(1).split("\n", 1)[0].strip(" :-")
            return value[:80]
    return ""


def extract_tests(text: str) -> list[dict[str, Any]]:
    tests: list[dict[str, Any]] = []
    for definition in TEST_PATTERNS:
        value_match = find_test_value(text, definition["aliases"])
        if not value_match:
            continue

        value, raw_unit = value_match
        low = definition.get("low")
        high = definition.get("high")
        abnormal = is_abnormal(value, low, high)
        critical = is_critical(value, definition.get("critical_low"), definition.get("critical_high"))
        tests.append(
            {
                "name": definition["name"],
                "value": value,
                "unit": raw_unit or definition.get("unit") or "",
                "referenceRange": format_range(low, high),
                "category": categorize_test(definition["name"]),
                "abnormal": abnormal,
                "critical": critical,
            }
        )
    return tests


def find_test_value(text: str, aliases: list[str]) -> tuple[float, str] | None:
    unit_pattern = r"([A-Za-z/%^0-9.µμ]+(?:/[A-Za-z0-9]+)?)?"
    for alias in aliases:
        pattern = re.compile(
            rf"\b{re.escape(alias)}\b\s*[:\-]?\s*([<>]?\s*\d+(?:\.\d+)?)\s*{unit_pattern}",
            re.IGNORECASE,
        )
        match = pattern.search(text)
        if not match:
            continue
        raw_value = match.group(1).replace(" ", "")
        value_match = re.search(r"\d+(?:\.\d+)?", raw_value)
        if value_match:
            return float(value_match.group(0)), (match.group(2) or "").strip()
    return None


def extract_additional_biomarkers(text: str, known_names: set[str]) -> list[dict[str, Any]]:
    biomarkers: list[dict[str, Any]] = []
    line_pattern = re.compile(
        r"^([A-Za-z][A-Za-z /()\-]{2,40})\s+([<>]?\d+(?:\.\d+)?)\s*([A-Za-z/%^0-9.µμ]*)",
        re.MULTILINE,
    )
    for match in line_pattern.finditer(text):
        name = " ".join(match.group(1).split()).strip()
        if name.lower() in known_names or len(biomarkers) >= 12:
            continue
        try:
            value = float(re.search(r"\d+(?:\.\d+)?", match.group(2)).group(0))  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            continue
        biomarkers.append(
            {
                "name": name,
                "value": value,
                "unit": match.group(3).strip(),
                "referenceRange": "",
                "category": "Additional Biomarkers",
                "abnormal": False,
                "critical": False,
            }
        )
    return biomarkers


def is_abnormal(value: float, low: float | None, high: float | None) -> bool:
    if low is not None and value < low:
        return True
    if high is not None and value > high:
        return True
    return False


def is_critical(value: float, low: float | None, high: float | None) -> bool:
    if low is not None and value < low:
        return True
    if high is not None and value > high:
        return True
    return False


def format_range(low: float | None, high: float | None) -> str:
    if low is not None and high is not None:
        return f"{low}-{high}"
    if low is not None:
        return f">= {low}"
    if high is not None:
        return f"<= {high}"
    return ""


def categorize_test(name: str) -> str:
    lower = name.lower()
    if lower in {"alt", "ast", "bilirubin"}:
        return "Liver Function Tests"
    if lower in {"tsh", "t3", "t4"}:
        return "Thyroid Tests"
    if lower in {"cholesterol", "triglycerides", "hdl", "ldl"}:
        return "Lipid Profile"
    if lower in {"hemoglobin", "wbc", "rbc", "platelet count"}:
        return "Complete Blood Count"
    if lower in {"creatinine", "urea", "sodium", "potassium"}:
        return "Renal and Electrolytes"
    if lower in {"blood sugar", "hba1c"}:
        return "Diabetes Markers"
    return "Additional Biomarkers"
