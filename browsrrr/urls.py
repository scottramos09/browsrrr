from urllib.parse import quote_plus, urlparse


def normalize_url(text: str) -> str:
    text = text.strip()
    if not text:
        return "about:blank"

    if text.startswith(("about:", "file:", "chrome:")):
        return text

    parsed = urlparse(text)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return text

    if " " not in text and ("." in text or text.startswith("localhost")):
        return f"https://{text}"

    return f"https://duckduckgo.com/?q={quote_plus(text)}"