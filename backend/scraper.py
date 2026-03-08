"""Fetches webpage content as raw HTML."""

import logging
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


class ScraperError(Exception):
    """Raised when scraping fails."""

    pass


def fetch(url: str, timeout: int = DEFAULT_TIMEOUT, headers: dict | None = None) -> str:
    """
    Fetch webpage content as raw HTML.

    Args:
        url: The website URL to fetch.
        timeout: Request timeout in seconds.
        headers: Optional request headers. Defaults to browser-like headers.

    Returns:
        Raw HTML string of the webpage.

    Raises:
        ScraperError: On timeout, HTTP errors, or connection failure.
    """
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise ScraperError(f"Invalid URL: {url}")

    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504],
    )
    session.mount("https://", HTTPAdapter(max_retries=retries))
    session.mount("http://", HTTPAdapter(max_retries=retries))

    request_headers = {**DEFAULT_HEADERS, **(headers or {})}

    try:
        response = session.get(url, headers=request_headers, timeout=timeout)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or "utf-8"
        return response.text
    except requests.exceptions.Timeout:
        raise ScraperError(f"Request timed out after {timeout}s: {url}")
    except requests.exceptions.HTTPError as e:
        raise ScraperError(f"HTTP error {e.response.status_code}: {url}")
    except requests.exceptions.ConnectionError:
        raise ScraperError(f"Connection failed: {url}")
    except requests.exceptions.RequestException as e:
        raise ScraperError(f"Request failed: {e}")
