from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.domain.models import PaperCandidate
from app.ingestion.arxiv import ingest_arxiv
from app.ingestion.arxiv_fetcher import ArxivFetcher
from app.llm.client import LlmClient
from app.pipeline.research import ResearchPipeline, ResearchPipelineItem
from app.quality import ResearchQualityGate
from app.repositories.papers import PaperRepository, StoredPaper


@dataclass(frozen=True)
class ResearchIngestionItemResult:
    item: ResearchPipelineItem | None
    stored: StoredPaper | None
    skipped: bool = False


def _arxiv_fields_unchanged(candidate: PaperCandidate, stored: StoredPaper) -> bool:
    return (
        candidate.title == stored.title
        and candidate.abstract == stored.abstract
        and candidate.updated_at == stored.arxiv_updated_at
    )


class ResearchIngestion:
    """arXiv → ResearchPipeline → PaperRepository. Does not commit."""

    def __init__(
        self,
        llm: LlmClient,
        quality_gate: ResearchQualityGate | None = None,
    ) -> None:
        self._pipeline = ResearchPipeline(llm, quality_gate)

    def run(
        self,
        query: str,
        session: Session,
        *,
        max_results: int,
        fetcher: ArxivFetcher | None = None,
    ) -> list[ResearchIngestionItemResult]:
        candidates = ingest_arxiv(query, max_results=max_results, fetcher=fetcher)
        repository = PaperRepository(session)
        known = repository.get_by_arxiv_ids(
            [candidate.arxiv_id for candidate in candidates]
        )

        to_process: list[PaperCandidate] = []
        skipped_by_id: dict[str, StoredPaper] = {}
        for candidate in candidates:
            stored = known.get(candidate.arxiv_id)
            if stored is not None and _arxiv_fields_unchanged(candidate, stored):
                skipped_by_id[candidate.arxiv_id] = stored
            else:
                to_process.append(candidate)

        processed_by_id = {
            item.candidate.arxiv_id: item
            for item in self._pipeline.process_candidates(to_process)
        }

        results: list[ResearchIngestionItemResult] = []
        for candidate in candidates:
            if candidate.arxiv_id in skipped_by_id:
                results.append(
                    ResearchIngestionItemResult(
                        item=None,
                        stored=skipped_by_id[candidate.arxiv_id],
                        skipped=True,
                    )
                )
                continue
            item = processed_by_id[candidate.arxiv_id]
            if item.error is not None:
                results.append(
                    ResearchIngestionItemResult(item=item, stored=None, skipped=False)
                )
            else:
                assert item.analysis is not None
                assert item.decision is not None
                stored = repository.save(item.candidate, item.analysis, item.decision)
                results.append(
                    ResearchIngestionItemResult(item=item, stored=stored, skipped=False)
                )
        return results
