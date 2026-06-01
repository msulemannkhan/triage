"""Abstract customer repository — the enrichment data source.

The customer store is mocked/static by scope, so this stays an in-memory
interface (it never becomes a live DB). Returning ``None`` for an unknown
customer lets the enricher fall back to safe defaults.
"""

from abc import ABC, abstractmethod

from triage.conversations.models.schemas import Customer


class CustomerRepository(ABC):
    @abstractmethod
    def get(self, customer_id: str) -> Customer | None:
        """Return the customer, or ``None`` if not found."""
