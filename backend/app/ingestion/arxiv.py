from app.domain.models import PaperCandidate
from app.ingestion.arxiv_fetcher import ArxivFetcher
from app.ingestion.arxiv_normalize import normalize_arxiv_entry

DEFAULT_ARXIV_QUERY = "cat:cs.AI OR cat:cs.LG OR cat:cs.CL"


def ingest_arxiv(
    query: str,
    *,
    max_results: int,
    fetcher: ArxivFetcher | None = None,
) -> list[PaperCandidate]:
    """Fetch an arXiv query and return validated paper candidates.

    Skips unusable entries. Does not rank or persist results.
    """
    if max_results <= 0:
        raise ValueError("max_results must be greater than 0")
    active_fetcher = fetcher or ArxivFetcher()
    candidates: list[PaperCandidate] = []
    for entry in active_fetcher.fetch_entries(query, max_results):
        candidate = normalize_arxiv_entry(entry)
        if candidate is not None:
            candidates.append(candidate)
    return candidates
