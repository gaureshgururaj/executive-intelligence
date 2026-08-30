import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

import feedparser

from app.ingestion.errors import RssFetchError

_DEFAULT_TIMEOUT_SECONDS = 30.0
_USER_AGENT = "executive-intelligence/0.1"


@dataclass(frozen=True)
class RawFeedEntry:
    """Parsed RSS/Atom item. Presence of a usable URL or title is not decided here."""

    link: str | None
    title: str | None
    summary: str | None
    published_parsed: time.struct_time | None


def _default_fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(
            request, timeout=_DEFAULT_TIMEOUT_SECONDS
        ) as response:
            status = getattr(response, "status", 200)
            if status >= 400:
                raise RssFetchError(f"RSS feed returned HTTP {status}: {url}")
            body = response.read()
    except RssFetchError:
        raise
    except urllib.error.HTTPError as exc:
        raise RssFetchError(f"RSS feed returned HTTP {exc.code}: {url}") from exc
    except Exception as exc:
        raise RssFetchError(f"Failed to fetch RSS feed: {url}") from exc
    return body


def _as_optional_str(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def _to_raw_entry(entry: Mapping[str, Any]) -> RawFeedEntry:
    published = entry.get("published_parsed") or entry.get("updated_parsed")
    if published is not None and not isinstance(published, time.struct_time):
        published = None
    return RawFeedEntry(
        link=_as_optional_str(entry.get("link")),
        title=_as_optional_str(entry.get("title")),
        summary=_as_optional_str(entry.get("summary") or entry.get("description")),
        published_parsed=published,
    )


class RssFetcher:
    """Fetches an RSS/Atom document and returns parsed entries.

    Individual entry usability is not decided here.
    """

    def __init__(self, fetch: Callable[[str], bytes] | None = None) -> None:
        self._fetch = fetch or _default_fetch

    def fetch_entries(self, feed_url: str) -> list[RawFeedEntry]:
        try:
            body = self._fetch(feed_url)
        except RssFetchError:
            raise
        except Exception as exc:
            raise RssFetchError(f"Failed to fetch RSS feed: {feed_url}") from exc

        if not body.strip():
            raise RssFetchError(f"Empty RSS response: {feed_url}")

        parsed = feedparser.parse(body)
        raw_entries = list(parsed.entries or [])
        if not raw_entries:
            version = parsed.get("version") or ""
            if parsed.bozo or not version:
                detail = ""
                bozo_exception = parsed.get("bozo_exception")
                if parsed.bozo and bozo_exception is not None:
                    detail = f" ({bozo_exception})"
                raise RssFetchError(f"Unparseable RSS feed: {feed_url}{detail}")
            return []

        return [_to_raw_entry(entry) for entry in raw_entries]
