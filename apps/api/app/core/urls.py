import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "utm_id",
    "ref",
    "fbclid",
    "gclid",
}


def canonicalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    scheme = parsed.scheme.lower() if parsed.scheme else "https"
    if scheme == "http":
        scheme = "https"
    host = (parsed.hostname or "").lower().removeprefix("www.")
    if parsed.port and parsed.port not in {80, 443}:
        host = f"{host}:{parsed.port}"
    path = parsed.path.rstrip("/") or "/"
    kept = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in TRACKING_PARAMS
    ]
    query = urlencode(kept)
    return urlunparse((scheme, host, path, "", query, ""))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def strip_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", text).strip()
