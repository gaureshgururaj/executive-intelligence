import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import RecommendationProfileRow
from app.domain.models import RecommendationProfile


class StoredRecommendationProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    interests: list[str]
    created_at: datetime
    updated_at: datetime


def _apply(row: RecommendationProfileRow, profile: RecommendationProfile) -> None:
    row.name = profile.name
    row.interests = list(profile.interests)
    row.updated_at = datetime.now(UTC)


class RecommendationProfileRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, profile: RecommendationProfile) -> StoredRecommendationProfile:
        row = self._session.scalar(
            select(RecommendationProfileRow).where(
                RecommendationProfileRow.name == profile.name
            )
        )
        if row is None:
            row = RecommendationProfileRow()
            _apply(row, profile)
            self._session.add(row)
        else:
            _apply(row, profile)
        self._session.flush()
        return StoredRecommendationProfile.model_validate(row)

    def get_by_id(self, profile_id: uuid.UUID) -> StoredRecommendationProfile | None:
        row = self._session.scalar(
            select(RecommendationProfileRow).where(
                RecommendationProfileRow.id == profile_id
            )
        )
        if row is None:
            return None
        return StoredRecommendationProfile.model_validate(row)

    def get_by_name(self, name: str) -> StoredRecommendationProfile | None:
        row = self._session.scalar(
            select(RecommendationProfileRow).where(
                RecommendationProfileRow.name == name
            )
        )
        if row is None:
            return None
        return StoredRecommendationProfile.model_validate(row)

    def list_all(self) -> list[StoredRecommendationProfile]:
        rows = self._session.scalars(
            select(RecommendationProfileRow).order_by(
                RecommendationProfileRow.name.asc(),
                RecommendationProfileRow.id.asc(),
            )
        )
        return [StoredRecommendationProfile.model_validate(row) for row in rows]
