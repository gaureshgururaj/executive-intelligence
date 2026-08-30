from app.agents.errors import TrendAgentError
from app.agents.trend import TrendAgent
from app.ingestion import ingest_rss
from app.ingestion.fetcher import RssFetcher
from app.llm.client import LlmClient
from app.pipeline.results import PipelineItem
from app.quality import QualityGate


class TrendPipeline:
    """RSS → Trend Agent → Quality Gate. In-memory results only."""

    def __init__(
        self,
        llm: LlmClient,
        quality_gate: QualityGate | None = None,
    ) -> None:
        self._trend_agent = TrendAgent(llm)
        self._quality_gate = quality_gate or QualityGate()

    def run(
        self, feed_url: str, fetcher: RssFetcher | None = None
    ) -> list[PipelineItem]:
        items: list[PipelineItem] = []
        for candidate in ingest_rss(feed_url, fetcher=fetcher):
            try:
                analysis = self._trend_agent.analyze(candidate)
            except TrendAgentError as exc:
                items.append(PipelineItem(candidate=candidate, error=str(exc)))
                continue
            decision = self._quality_gate.evaluate(candidate, analysis)
            items.append(
                PipelineItem(
                    candidate=candidate,
                    analysis=analysis,
                    decision=decision,
                )
            )
        return items
