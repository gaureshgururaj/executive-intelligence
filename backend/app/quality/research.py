from app.domain.models import PaperCandidate, QualityDecision, ResearchAnalysis

_REASON_RELEVANCE = "Relevance score below threshold"
_REASON_FINDINGS = "Analysis has no key findings"


class ResearchQualityGate:
    """Deterministic publication gate for research papers. First failed rule wins.

    Order: relevance → key findings. Empty practical_implications do not reject.
    """

    def __init__(self, min_relevance_score: float = 0.5) -> None:
        if not 0.0 <= min_relevance_score <= 1.0:
            raise ValueError("min_relevance_score must be between 0 and 1")
        self._min_relevance_score = min_relevance_score

    def evaluate(
        self, candidate: PaperCandidate, analysis: ResearchAnalysis
    ) -> QualityDecision:
        _ = candidate
        if analysis.relevance_score < self._min_relevance_score:
            return QualityDecision(accepted=False, reason=_REASON_RELEVANCE)
        if not analysis.key_findings:
            return QualityDecision(accepted=False, reason=_REASON_FINDINGS)
        return QualityDecision(accepted=True, reason=None)
