from app.domain.models import ArticleCandidate, QualityDecision, TrendAnalysis

_REASON_RELEVANCE = "Relevance score below threshold"
_REASON_CONTENT = "Insufficient usable content"
_REASON_KEY_POINTS = "Analysis has no key points"


class QualityGate:
    """Deterministic publication gate. First failed rule wins.

    Order: relevance → usable content → key points.
    """

    def __init__(self, min_relevance_score: float = 0.5) -> None:
        if not 0.0 <= min_relevance_score <= 1.0:
            raise ValueError("min_relevance_score must be between 0 and 1")
        self._min_relevance_score = min_relevance_score

    def evaluate(
        self, candidate: ArticleCandidate, analysis: TrendAnalysis
    ) -> QualityDecision:
        if analysis.relevance_score < self._min_relevance_score:
            return QualityDecision(accepted=False, reason=_REASON_RELEVANCE)
        if candidate.excerpt is None and not analysis.key_points:
            return QualityDecision(accepted=False, reason=_REASON_CONTENT)
        if not analysis.key_points:
            return QualityDecision(accepted=False, reason=_REASON_KEY_POINTS)
        return QualityDecision(accepted=True, reason=None)
