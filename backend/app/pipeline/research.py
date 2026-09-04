from pydantic import BaseModel, field_validator, model_validator

from app.agents.errors import ResearchAgentError
from app.agents.research import ResearchAgent
from app.domain.models import PaperCandidate, QualityDecision, ResearchAnalysis
from app.llm.client import LlmClient
from app.llm.errors import LlmClientError
from app.quality import ResearchQualityGate


class ResearchPipelineItem(BaseModel):
    """One candidate after Research Agent and Research Quality Gate.

    Success: analysis and decision are set, error is None.
    ResearchAgent failure: error is set, analysis and decision are None.
    """

    candidate: PaperCandidate
    analysis: ResearchAnalysis | None = None
    decision: QualityDecision | None = None
    error: str | None = None

    @field_validator("error", mode="before")
    @classmethod
    def empty_error_to_none(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @model_validator(mode="after")
    def consistent_outcome(self) -> "ResearchPipelineItem":
        failed = self.error is not None
        if failed:
            if self.analysis is not None or self.decision is not None:
                raise ValueError("failed items cannot include analysis or decision")
            return self
        if self.analysis is None or self.decision is None:
            raise ValueError("successful items require analysis and decision")
        return self


class ResearchPipeline:
    """PaperCandidate → Research Agent → Quality Gate. In-memory results only."""

    def __init__(
        self,
        llm: LlmClient,
        quality_gate: ResearchQualityGate | None = None,
    ) -> None:
        self._research_agent = ResearchAgent(llm)
        self._quality_gate = quality_gate or ResearchQualityGate()

    def process_candidates(
        self, candidates: list[PaperCandidate]
    ) -> list[ResearchPipelineItem]:
        items: list[ResearchPipelineItem] = []
        for candidate in candidates:
            try:
                analysis = self._research_agent.analyze(candidate)
            except (ResearchAgentError, LlmClientError) as exc:
                items.append(ResearchPipelineItem(candidate=candidate, error=str(exc)))
                continue
            decision = self._quality_gate.evaluate(candidate, analysis)
            items.append(
                ResearchPipelineItem(
                    candidate=candidate,
                    analysis=analysis,
                    decision=decision,
                )
            )
        return items
