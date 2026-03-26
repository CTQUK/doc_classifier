from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Set

from doc_classifier.config import ClassifierConfig
from doc_classifier.models import ExtractionResult


class BaseExtractor(ABC):

    def __init__(self, config: ClassifierConfig) -> None:
        self.config = config

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def supported_groups(self) -> Set[str]:
        ...

    @abstractmethod
    def extract(self, filepath: str) -> ExtractionResult:
        ...

    def handles(self, format_group: str) -> bool:
        return format_group in self.supported_groups
