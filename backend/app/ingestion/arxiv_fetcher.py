import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import feedparser

from app.ingestion.errors import ArxivFetchError

_DEFAULT_TIMEOUT_SECONDS = 30.0
_USER_AGENT = "executive-intelligence/0.1"
ARXIV_API_URL = "https://export.arxiv.org/api/query"


@dataclass(frozen=True)
class RawArxivEntry:
    """Parsed arXiv Atom item. Usability is not decided here."""

    raw_id: str | None
    title: str | None
    summary: str | None
    published_parsed: time.struct_time | None
    updated_parsed: time.struct_time | None
    authors: list[str]
    paper_url: str | None
    pdf_url: str | None
    categories: list[str]


def _require_positive_max_results(max_results: int) -> None:
    if max_results <= 0:
        raise ValueError("max_results must be greater than 0")


def build_arxiv_query_url(query: str, max_results: int) -> str:
    _require_positive_max_results(max_results)
    params = {
        "search_query": query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    return f"{ARXIV_API_URL}?{urlencode(params)}"


def _default_fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(
            request, timeout=_DEFAULT_TIMEOUT_SECONDS
        ) as response:
            status = getattr(response, "status", 200)
            if status >= 400:
                raise ArxivFetchError(f"arXiv returned HTTP {status}: {url}")
            body = response.read()
    except ArxivFetchError:
        raise
    except urllib.error.HTTPError as exc:
        raise ArxivFetchError(f"arXiv returned HTTP {exc.code}: {url}") from exc
    except Exception as exc:
        raise ArxivFetchError(f"Failed to fetch arXiv results: {url}") from exc
    return body


def _as_optional_str(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def _parsed_time(value: object) -> time.struct_time | None:
    if isinstance(value, time.struct_time):
        return value
    return None


def _author_names(entry: Mapping[str, Any]) -> list[str]:
    names: list[str] = []
    for author in entry.get("authors") or []:
        if isinstance(author, Mapping):
            name = author.get("name")
        else:
            name = author
        if name is None:
            continue
        names.append(name if isinstance(name, str) else str(name))
    if names:
        return names
    single = entry.get("author")
    if single is None:
        return []
    return [single if isinstance(single, str) else str(single)]


def _categories(entry: Mapping[str, Any]) -> list[str]:
    terms: list[str] = []
    for tag in entry.get("tags") or []:
        if not isinstance(tag, Mapping):
            continue
        term = tag.get("term")
        if term is None:
            continue
        terms.append(term if isinstance(term, str) else str(term))
    return terms


def _urls(entry: Mapping[str, Any]) -> tuple[str | None, str | None]:
    paper_url: str | None = None
    pdf_url: str | None = None
    for link in entry.get("links") or []:
        if not isinstance(link, Mapping):
            continue
        href = _as_optional_str(link.get("href"))
        if not href:
            continue
        rel = link.get("rel")
        title = link.get("title")
        type_ = link.get("type")
        rel_text = rel.lower() if isinstance(rel, str) else ""
        title_text = title.lower() if isinstance(title, str) else ""
        type_text = type_.lower() if isinstance(type_, str) else ""
        if type_text == "application/pdf" or title_text == "pdf":
            pdf_url = href
            continue
        if paper_url is None and (
            rel_text in {"alternate", ""} or type_text == "text/html"
        ):
            paper_url = href
    if paper_url is None:
        paper_url = _as_optional_str(entry.get("link"))
    return paper_url, pdf_url


def _raw_get(entry: Mapping[str, Any], key: str) -> object | None:
    if isinstance(entry, dict) and dict.__contains__(entry, key):
        return dict.__getitem__(entry, key)
    return None


def _to_raw_entry(entry: Mapping[str, Any]) -> RawArxivEntry:
    paper_url, pdf_url = _urls(entry)
    return RawArxivEntry(
        raw_id=_as_optional_str(entry.get("id")),
        title=_as_optional_str(entry.get("title")),
        summary=_as_optional_str(entry.get("summary")),
        published_parsed=_parsed_time(_raw_get(entry, "published_parsed")),
        updated_parsed=_parsed_time(_raw_get(entry, "updated_parsed")),
        authors=_author_names(entry),
        paper_url=paper_url,
        pdf_url=pdf_url,
        categories=_categories(entry),
    )


class ArxivFetcher:
    """Fetches an arXiv Atom document and returns parsed entries.

    Individual entry usability is not decided here.
    """

    def __init__(self, fetch: Callable[[str], bytes] | None = None) -> None:
        self._fetch = fetch or _default_fetch

    def fetch_entries(self, query: str, max_results: int) -> list[RawArxivEntry]:
        url = build_arxiv_query_url(query, max_results)
        try:
            body = self._fetch(url)
        except ArxivFetchError:
            raise
        except Exception as exc:
            raise ArxivFetchError(f"Failed to fetch arXiv results: {url}") from exc

        if not body.strip():
            raise ArxivFetchError(f"Empty arXiv response: {url}")

        parsed = feedparser.parse(body)
        raw_entries = list(parsed.entries or [])
        if not raw_entries:
            version = parsed.get("version") or ""
            if parsed.bozo or not version:
                detail = ""
                bozo_exception = parsed.get("bozo_exception")
                if parsed.bozo and bozo_exception is not None:
                    detail = f" ({bozo_exception})"
                raise ArxivFetchError(f"Unparseable arXiv feed: {url}{detail}")
            return []

        if len(raw_entries) > max_results:
            raw_entries = raw_entries[:max_results]
        return [_to_raw_entry(entry) for entry in raw_entries]
