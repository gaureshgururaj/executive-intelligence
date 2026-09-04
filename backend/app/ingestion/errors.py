class RssFetchError(Exception):
    """Raised when an RSS feed cannot be fetched or parsed at the feed level."""


class ArxivFetchError(Exception):
    """Raised when an arXiv query cannot be fetched or parsed at the feed level."""
