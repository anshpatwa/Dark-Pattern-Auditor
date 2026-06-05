"""Tests for the SSRF guard. These use IP literals / localhost so they need no network."""

import pytest

from dpa.security import UnsafeURLError, ensure_public_url


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com",
        "file:///etc/passwd",
        "javascript:alert(1)",
        "http://localhost/admin",
        "http://127.0.0.1:8000",
        "http://0.0.0.0",
        "http://169.254.169.254/latest/meta-data/",  # cloud metadata
        "http://10.0.0.5",
        "http://192.168.1.1",
        "https://[::1]/",
    ],
)
def test_blocks_unsafe_urls(url):
    with pytest.raises(UnsafeURLError):
        ensure_public_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "http://8.8.8.8",
        "https://1.1.1.1/dns-query",
    ],
)
def test_allows_public_ip_literals(url):
    # Public IP literals require no DNS, so this is hermetic.
    assert ensure_public_url(url) == url


def test_missing_host_is_rejected():
    with pytest.raises(UnsafeURLError):
        ensure_public_url("http://")
