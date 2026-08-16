from browsrrr.urls import normalize_url


def test_normalizes_domain_to_https():
    assert normalize_url("example.com") == "https://example.com"


def test_normalizes_localhost_with_port():
    assert normalize_url("localhost:8000") == "https://localhost:8000"


def test_keeps_existing_http_url():
    assert normalize_url("https://example.com") == "https://example.com"


def test_searches_for_free_text():
    assert normalize_url("hello world") == "https://duckduckgo.com/?q=hello+world"


def test_defaults_to_blank():
    assert normalize_url("   ") == "about:blank"