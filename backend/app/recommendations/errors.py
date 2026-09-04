class RecommendationProfileNotFoundError(Exception):
    """Raised when a recommendation is requested for an unknown profile."""

    def __init__(self, profile_id: object) -> None:
        self.profile_id = profile_id
        super().__init__(f"Recommendation profile not found: {profile_id}")
