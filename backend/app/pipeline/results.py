from pydantic import BaseModel, field_validator, model_validator

from app.domain.models import ArticleCandidate, QualityDecision, TrendAnalysis


class PipelineItem(BaseModel):
    """One candidate after Trend Agent and Quality Gate.

    Success: analysis and decision are set, error is None.
    TrendAgent failure: error is set, analysis and decision are None.
    """

    candidate: ArticleCandidate
    analysis: TrendAnalysis | None = None
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
    def consistent_outcome(self) -> "PipelineItem":
        failed = self.error is not None
        if failed:
            if self.analysis is not None or self.decision is not None:
                raise ValueError("failed items cannot include analysis or decision")
            return self
        if self.analysis is None or self.decision is None:
            raise ValueError("successful items require analysis and decision")
        return self
