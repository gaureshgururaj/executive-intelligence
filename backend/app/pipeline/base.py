from abc import ABC, abstractmethod


class Pipeline(ABC):
    """Orchestrates RSS → Trend Agent → Quality Gate → persistence.

    Ingestion is not implemented in this skeleton.
    """

    @abstractmethod
    def run(self) -> None:
        raise NotImplementedError
