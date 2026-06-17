import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class PostProcessingResult:
    raw_text: str
    cleaned_text: str
    corrections: list[str] = field(default_factory=list)


class MedicalTextPostProcessor:
    def __init__(self) -> None:
        self._medical_terms = {
            r"\bhemoglobin\b|\bhaemoglobin\b|\bhemo globin\b": "Hemoglobin",
            r"\bhb\s*a\s*1\s*c\b|\bhba\s*one\s*c\b|\bhb one c\b|\bhba1 see\b": "HbA1c",
            r"\bcreatinine\b|\bcreatine\b|\bcretinine\b": "Creatinine",
            r"\bplatelets?\b|\bplatlet\b|\bplate let\b": "Platelet",
            r"\bw\s*b\s*c\b|\bdouble u b c\b|\bwhite blood cell[s]?\b": "WBC",
            r"\br\s*b\s*c\b|\bred blood cell[s]?\b": "RBC",
            r"\bsodium\b|\bsodiam\b": "Sodium",
            r"\bpotassium\b|\bpotasium\b": "Potassium",
            r"\bcholesterol\b|\bcholestrol\b": "Cholesterol",
            r"\btriglycerides?\b|\btri glycerides?\b|\btry glyceride[s]?\b": "Triglycerides",
            r"\bt\s*s\s*h\b|\btea\s*s\s*h\b": "TSH",
            r"\bt\s*3\b|\btea three\b": "T3",
            r"\bt\s*4\b|\btea four\b": "T4",
            r"\bdiabetes\b|\bdiabetis\b|\bdiabetic\b": "Diabetes",
            r"\bhypertension\b|\bhyper tension\b|\bhigh blood pressure\b": "Hypertension",
            r"\bcardiology\b|\bcardiologie\b": "Cardiology",
            r"\bneurology\b|\bneuro logy\b": "Neurology",
            r"\bgastroenterology\b|\bgastro enterology\b": "Gastroenterology",
            r"\bprescriptions?\b|\bpriscription\b": "Prescription",
            r"\bconsultations?\b|\bconsulting\b": "Consultation",
            r"\badmissions?\b": "Admission",
            r"\bdischarges?\b": "Discharge",
        }
        self._common_replacements = {
            r"\bpatient is having\b": "patient has",
            r"\breport is showing\b": "report shows",
            r"\bblood sugar\b": "blood glucose",
            r"\bbp\b": "blood pressure",
        }

    def process(self, text: str) -> PostProcessingResult:
        raw_text = text.strip()
        cleaned = self._normalize_whitespace(raw_text)
        cleaned = self._remove_duplicate_words(cleaned)

        corrections: list[str] = []
        cleaned, corrections = self._apply_replacements(
            cleaned,
            self._medical_terms,
            corrections,
        )
        cleaned, corrections = self._apply_replacements(
            cleaned,
            self._common_replacements,
            corrections,
        )
        cleaned = self._fix_punctuation(cleaned)
        cleaned = self._capitalize_sentences(cleaned)

        return PostProcessingResult(
            raw_text=raw_text,
            cleaned_text=cleaned,
            corrections=corrections,
        )

    def _apply_replacements(
        self,
        text: str,
        replacements: dict[str, str],
        corrections: list[str],
    ) -> tuple[str, list[str]]:
        updated = text
        for pattern, replacement in replacements.items():
            next_text, count = re.subn(
                pattern,
                replacement,
                updated,
                flags=re.IGNORECASE,
            )
            if count:
                corrections.append(replacement)
            updated = next_text

        return updated, corrections

    def _normalize_whitespace(self, text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    def _remove_duplicate_words(self, text: str) -> str:
        return re.sub(
            r"\b(\w+)(\s+\1\b)+",
            r"\1",
            text,
            flags=re.IGNORECASE,
        )

    def _fix_punctuation(self, text: str) -> str:
        if not text:
            return text

        text = re.sub(r"\s+([,.;:?!])", r"\1", text)
        text = re.sub(r"([,.;:?!])([^\s])", r"\1 \2", text)
        if text[-1] not in ".?!":
            text += "."
        return text

    def _capitalize_sentences(self, text: str) -> str:
        if not text:
            return text

        def capitalize_match(match: re.Match[str]) -> str:
            prefix = match.group(1)
            letter = match.group(2)
            return f"{prefix}{letter.upper()}"

        text = text[0].upper() + text[1:]
        return re.sub(r"(^|[.!?]\s+)([a-z])", capitalize_match, text)
