import re

STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "of",
        "and",
        "or",
        "for",
        "in",
        "on",
        "to",
        "with",
    }
)

_TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Lowercase, split on non-alphanumeric characters, drop stopwords."""
    return [token for token in _TOKEN.findall(text.lower()) if token not in STOPWORDS]
