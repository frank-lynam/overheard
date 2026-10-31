"""The case-system seam: the mock reads the seeded database; a real system of record replaces it later."""

from typing import Protocol

from overheard.data.models import Case


class CaseBackend(Protocol):
    def case(self, case_id: str) -> Case | None: ...
    def by_phone(self, phone: str) -> list[Case]: ...
    def search(self, text: str) -> list[Case]: ...
