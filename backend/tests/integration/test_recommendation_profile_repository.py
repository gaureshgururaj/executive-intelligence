import uuid
from unittest.mock import MagicMock

from sqlalchemy import inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.domain.models import RecommendationProfile
from app.repositories import RecommendationProfileRepository

PROFILE_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
OTHER_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")


def _profile(**overrides: object) -> RecommendationProfile:
    payload: dict[str, object] = {
        "id": PROFILE_ID,
        "name": "Applied LLMs",
        "interests": ["language models", "speech"],
    }
    payload.update(overrides)
    return RecommendationProfile.model_validate(payload)


def test_recommendation_profiles_table_uses_postgres_types(
    postgres_engine: Engine,
) -> None:
    columns = {
        column["name"]: column
        for column in inspect(postgres_engine).get_columns("recommendation_profiles")
    }
    assert "UUID" in str(columns["id"]["type"]).upper()
    assert "JSON" in str(columns["interests"]["type"]).upper()
    assert getattr(columns["created_at"]["type"], "timezone", False) is True
    assert getattr(columns["updated_at"]["type"], "timezone", False) is True
    unique_constraints = inspect(postgres_engine).get_unique_constraints(
        "recommendation_profiles"
    )
    unique_indexes = [
        tuple(index["column_names"])
        for index in inspect(postgres_engine).get_indexes("recommendation_profiles")
        if index["unique"]
    ]
    unique_names = {tuple(item["column_names"]) for item in unique_constraints}
    unique_names |= set(unique_indexes)
    assert ("name",) in unique_names


def test_save_persists_a_new_profile(db_session: Session) -> None:
    repo = RecommendationProfileRepository(db_session)
    stored = repo.save(_profile())
    assert stored.name == "Applied LLMs"
    assert stored.interests == ["language models", "speech"]
    assert stored.id is not None
    assert stored.created_at is not None
    assert stored.updated_at is not None


def test_persisted_interests_preserve_order(db_session: Session) -> None:
    repo = RecommendationProfileRepository(db_session)
    stored = repo.save(_profile(interests=["speech", "language models", "planning"]))
    fetched = repo.get_by_id(stored.id)
    assert fetched is not None
    assert fetched.interests == ["speech", "language models", "planning"]


def test_get_by_id_returns_stored_profile(db_session: Session) -> None:
    repo = RecommendationProfileRepository(db_session)
    saved = repo.save(_profile())
    assert repo.get_by_id(saved.id) == saved


def test_get_by_name_returns_stored_profile(db_session: Session) -> None:
    repo = RecommendationProfileRepository(db_session)
    saved = repo.save(_profile())
    assert repo.get_by_name("Applied LLMs") == saved


def test_missing_profile_lookups_return_none(db_session: Session) -> None:
    repo = RecommendationProfileRepository(db_session)
    assert repo.get_by_id(PROFILE_ID) is None
    assert repo.get_by_name("Missing") is None


def test_list_all_returns_empty_when_no_profiles(db_session: Session) -> None:
    repo = RecommendationProfileRepository(db_session)
    assert repo.list_all() == []


def test_list_all_orders_by_name_then_id(db_session: Session) -> None:
    repo = RecommendationProfileRepository(db_session)
    repo.save(_profile(name="Zebra", interests=["planning"]))
    repo.save(_profile(id=OTHER_ID, name="Alpha", interests=["speech"]))
    assert [profile.name for profile in repo.list_all()] == ["Alpha", "Zebra"]


def test_save_same_name_updates_existing_row(db_session: Session) -> None:
    repo = RecommendationProfileRepository(db_session)
    first = repo.save(_profile(interests=["language models"]))
    second = repo.save(
        _profile(id=OTHER_ID, interests=["speech", "planning"]),
    )
    assert second.id == first.id
    assert second.created_at == first.created_at
    assert second.interests == ["speech", "planning"]
    assert second.updated_at >= first.updated_at
    assert repo.get_by_name("Applied LLMs") == second
    assert len(repo.list_all()) == 1


def test_save_does_not_commit(db_session: Session) -> None:
    db_session.commit = MagicMock()
    repo = RecommendationProfileRepository(db_session)
    stored = repo.save(_profile())
    db_session.commit.assert_not_called()
    assert repo.get_by_id(stored.id) == stored


def test_two_names_create_two_rows(db_session: Session) -> None:
    repo = RecommendationProfileRepository(db_session)
    first = repo.save(_profile(name="Applied LLMs"))
    second = repo.save(
        _profile(id=OTHER_ID, name="Research systems", interests=["planning"])
    )
    assert first.id != second.id
    assert {profile.name for profile in repo.list_all()} == {
        "Applied LLMs",
        "Research systems",
    }


def test_empty_interests_persist(db_session: Session) -> None:
    repo = RecommendationProfileRepository(db_session)
    stored = repo.save(_profile(interests=[]))
    fetched = repo.get_by_id(stored.id)
    assert fetched is not None
    assert fetched.interests == []
