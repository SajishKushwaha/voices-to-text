import re
from dataclasses import dataclass, field
from uuid import uuid4

from rapidfuzz import fuzz, process

from ..config import Settings
from .context_vocabulary_service import ContextVocabulary


@dataclass(frozen=True)
class EntityCorrection:
    original: str
    corrected: str
    category: str
    similarity: int
    requires_confirmation: bool


@dataclass(frozen=True)
class ConfirmationRequest:
    id: str
    field_type: str
    original: str
    suggested: str
    alternatives: list[str]
    confidence: int


@dataclass(frozen=True)
class EntityCorrectionResult:
    text: str
    corrections: list[EntityCorrection] = field(default_factory=list)
    confirmations: list[ConfirmationRequest] = field(default_factory=list)


class EntityCorrectionService:
    _critical_categories = {"name", "city", "hospital", "doctor"}
    _location_markers = {"from", "in", "at", "near", "city", "district"}
    _doctor_markers = {"dr", "doctor"}

    def correct(
        self,
        text: str,
        vocabulary: ContextVocabulary,
        settings: Settings,
    ) -> EntityCorrectionResult:
        corrected_text = text
        corrections: list[EntityCorrection] = []
        confirmations: list[ConfirmationRequest] = []

        corrected_text, alias_corrections = self._apply_aliases(
            corrected_text,
            vocabulary,
        )
        corrections.extend(alias_corrections)

        for category, choices, threshold in [
            ("doctor", vocabulary.doctors, settings.entity_doctor_threshold),
            ("hospital", vocabulary.hospitals, settings.entity_hospital_threshold),
        ]:
            corrected_text, phrase_corrections = self._apply_phrase_matches(
                corrected_text,
                category,
                choices,
                threshold,
            )
            corrections.extend(phrase_corrections)
            confirmations.extend(
                self._confirmation(
                    correction,
                    choices,
                    settings.confirmation_alternative_count,
                )
                for correction in phrase_corrections
            )

        words = re.findall(r"\b[\w'-]+\b", corrected_text)
        replacements: dict[str, EntityCorrection] = {}

        for index, word in enumerate(words):
            normalized = word.lower()
            previous = words[index - 1].lower() if index > 0 else ""
            category, choices, threshold = self._choices_for_word(
                word=word,
                previous=previous,
                vocabulary=vocabulary,
                settings=settings,
            )
            if not choices or normalized in {choice.lower() for choice in choices}:
                continue

            match = process.extractOne(word, choices, scorer=fuzz.ratio)
            if not match:
                continue

            suggestion, score, _index = match
            similarity = round(score)
            if similarity < threshold:
                continue

            requires_confirmation = category in self._critical_categories
            correction = EntityCorrection(
                original=word,
                corrected=suggestion,
                category=category,
                similarity=similarity,
                requires_confirmation=requires_confirmation,
            )
            replacements[word] = correction
            corrections.append(correction)

            if requires_confirmation:
                confirmations.append(
                    self._confirmation(
                        correction,
                        choices,
                        settings.confirmation_alternative_count,
                    )
                )

        for original, correction in replacements.items():
            corrected_text = re.sub(
                rf"\b{re.escape(original)}\b",
                correction.corrected,
                corrected_text,
                count=1,
                flags=re.IGNORECASE,
            )

        for correction in alias_corrections:
            if correction.requires_confirmation:
                choices = self._category_choices(correction.category, vocabulary)
                confirmations.append(
                    self._confirmation(
                        correction,
                        choices,
                        settings.confirmation_alternative_count,
                    )
                )

        return EntityCorrectionResult(
            text=corrected_text,
            corrections=self._deduplicate_corrections(corrections),
            confirmations=self._deduplicate_confirmations(confirmations),
        )

    def _apply_aliases(
        self,
        text: str,
        vocabulary: ContextVocabulary,
    ) -> tuple[str, list[EntityCorrection]]:
        updated = text
        corrections: list[EntityCorrection] = []

        for alias, canonical in sorted(
            vocabulary.aliases.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        ):
            category = self._category_for_term(canonical, vocabulary)
            next_text, count = re.subn(
                rf"\b{re.escape(alias)}\b",
                canonical,
                updated,
                flags=re.IGNORECASE,
            )
            if count:
                corrections.append(
                    EntityCorrection(
                        original=alias,
                        corrected=canonical,
                        category=category,
                        similarity=100,
                        requires_confirmation=category in self._critical_categories,
                    )
                )
            updated = next_text

        return updated, corrections

    def _choices_for_word(
        self,
        word: str,
        previous: str,
        vocabulary: ContextVocabulary,
        settings: Settings,
    ) -> tuple[str, list[str], int]:
        if previous in self._location_markers:
            return "city", vocabulary.cities, settings.entity_location_threshold

        if previous in self._doctor_markers:
            return "name", vocabulary.names, settings.entity_name_threshold

        medical_match = process.extractOne(
            word,
            vocabulary.medical_terms,
            scorer=fuzz.ratio,
        )
        if medical_match and medical_match[1] >= settings.entity_medical_threshold:
            return "medical", vocabulary.medical_terms, settings.entity_medical_threshold

        if word[:1].isupper() and len(word) >= 4:
            return "name", vocabulary.names, settings.entity_name_threshold

        return "", [], 101

    def _apply_phrase_matches(
        self,
        text: str,
        category: str,
        choices: list[str],
        threshold: int,
    ) -> tuple[str, list[EntityCorrection]]:
        updated = text
        corrections: list[EntityCorrection] = []

        for choice in sorted(choices, key=lambda value: len(value.split()), reverse=True):
            word_count = len(choice.split())
            if word_count < 2:
                continue

            pattern = rf"\b[\w'-]+(?:\s+[\w'-]+){{{word_count - 1}}}\b"
            candidates = list(re.finditer(pattern, updated))
            if not candidates:
                continue

            best = max(
                candidates,
                key=lambda match: fuzz.ratio(match.group(0), choice),
            )
            original = best.group(0)
            similarity = round(fuzz.ratio(original, choice))
            if similarity < threshold or original.lower() == choice.lower():
                continue

            updated = f"{updated[:best.start()]}{choice}{updated[best.end():]}"
            corrections.append(
                EntityCorrection(
                    original=original,
                    corrected=choice,
                    category=category,
                    similarity=similarity,
                    requires_confirmation=True,
                )
            )

        return updated, corrections

    def _category_for_term(
        self,
        term: str,
        vocabulary: ContextVocabulary,
    ) -> str:
        term_lower = term.lower()
        categories = {
            "name": vocabulary.names,
            "city": vocabulary.cities,
            "hospital": vocabulary.hospitals,
            "doctor": vocabulary.doctors,
            "medical": vocabulary.medical_terms,
        }
        for category, choices in categories.items():
            if term_lower in {choice.lower() for choice in choices}:
                return category

        return "medical"

    def _category_choices(
        self,
        category: str,
        vocabulary: ContextVocabulary,
    ) -> list[str]:
        return {
            "name": vocabulary.names,
            "city": vocabulary.cities,
            "hospital": vocabulary.hospitals,
            "doctor": vocabulary.doctors,
            "medical": vocabulary.medical_terms,
        }.get(category, [])

    def _confirmation(
        self,
        correction: EntityCorrection,
        choices: list[str],
        alternative_count: int,
    ) -> ConfirmationRequest:
        alternatives = [
            match[0]
            for match in process.extract(
                correction.original,
                choices,
                scorer=fuzz.ratio,
                limit=alternative_count,
            )
        ]
        if correction.corrected not in alternatives:
            alternatives.insert(0, correction.corrected)
        if correction.original not in alternatives:
            alternatives.append(correction.original)

        return ConfirmationRequest(
            id=uuid4().hex,
            field_type=correction.category,
            original=correction.original,
            suggested=correction.corrected,
            alternatives=list(dict.fromkeys(alternatives)),
            confidence=correction.similarity,
        )

    def _deduplicate_corrections(
        self,
        corrections: list[EntityCorrection],
    ) -> list[EntityCorrection]:
        return list(
            {
                (
                    correction.original.lower(),
                    correction.corrected.lower(),
                    correction.category,
                ): correction
                for correction in corrections
            }.values()
        )

    def _deduplicate_confirmations(
        self,
        confirmations: list[ConfirmationRequest],
    ) -> list[ConfirmationRequest]:
        return list(
            {
                (
                    confirmation.original.lower(),
                    confirmation.suggested.lower(),
                    confirmation.field_type,
                ): confirmation
                for confirmation in confirmations
            }.values()
        )
