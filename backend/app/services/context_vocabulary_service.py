import json
from dataclasses import dataclass
from pathlib import Path

from ..config import Settings


@dataclass(frozen=True)
class ContextVocabulary:
    names: list[str]
    cities: list[str]
    hospitals: list[str]
    doctors: list[str]
    medical_terms: list[str]
    aliases: dict[str, str]

    @property
    def all_terms(self) -> list[str]:
        return list(
            dict.fromkeys(
                self.names
                + self.cities
                + self.hospitals
                + self.doctors
                + self.medical_terms
            )
        )


class ContextVocabularyService:
    def load(self, settings: Settings) -> ContextVocabulary:
        if not settings.context_vocabulary_path.exists():
            raise ValueError(
                f"Context vocabulary not found at {settings.context_vocabulary_path}."
            )

        try:
            data = json.loads(settings.context_vocabulary_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError("Context vocabulary could not be loaded.") from error

        return ContextVocabulary(
            names=self._list(data, "names"),
            cities=self._list(data, "cities"),
            hospitals=self._list(data, "hospitals"),
            doctors=self._list(data, "doctors"),
            medical_terms=self._list(data, "medical_terms"),
            aliases={
                str(key).strip().lower(): str(value).strip()
                for key, value in data.get("aliases", {}).items()
                if str(key).strip() and str(value).strip()
            },
        )

    def recognition_prompt(self, vocabulary: ContextVocabulary) -> str:
        return (
            "Important context vocabulary. Preserve exact spelling when spoken. "
            f"Known people: {', '.join(vocabulary.names)}. "
            f"Known cities and states: {', '.join(vocabulary.cities)}. "
            f"Known hospitals: {', '.join(vocabulary.hospitals)}. "
            f"Known doctors: {', '.join(vocabulary.doctors)}. "
            f"Medical terms: {', '.join(vocabulary.medical_terms)}."
        )

    def hotwords(self, vocabulary: ContextVocabulary) -> str:
        return " ".join(vocabulary.all_terms)

    def _list(self, data: dict, key: str) -> list[str]:
        return [
            str(item).strip()
            for item in data.get(key, [])
            if str(item).strip()
        ]
