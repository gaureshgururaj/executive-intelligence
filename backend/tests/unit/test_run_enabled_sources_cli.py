import importlib.util
from pathlib import Path
from uuid import uuid4

from app.config import Settings
from app.pipeline import SourceRunResult

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "run_enabled_sources.py"
_SPEC = importlib.util.spec_from_file_location("run_enabled_sources", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
_CLI = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_CLI)


def _result(*, error: str | None = None) -> SourceRunResult:
    return SourceRunResult(
        source_id=uuid4(),
        source_name="OpenAI News",
        source_url="https://openai.com/news/rss.xml",
        processed=1,
        skipped=0,
        persisted=1,
        accepted=1,
        rejected=0,
        failed=0,
        error=error,
    )


def test_ingest_max_articles_defaults_to_three() -> None:
    assert Settings.model_fields["ingest_max_articles"].default == 3


def test_exit_code_for_zero_sources_is_zero() -> None:
    assert _CLI.exit_code_for([]) == 0


def test_exit_code_for_one_success_is_zero() -> None:
    assert _CLI.exit_code_for([_result()]) == 0


def test_exit_code_for_several_successes_is_zero() -> None:
    assert _CLI.exit_code_for([_result(), _result(), _result()]) == 0


def test_exit_code_for_any_source_error_is_one() -> None:
    assert _CLI.exit_code_for([_result(error="feed timeout")]) == 1


def test_exit_code_for_mixed_success_and_source_error_is_one() -> None:
    assert _CLI.exit_code_for([_result(), _result(error="rollback")]) == 1
