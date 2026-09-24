import ipaddress
import socket
from urllib.parse import urlparse

import httpx

MAX_BYTES = 2 * 1024 * 1024
FETCH_TIMEOUT = 15.0
BLOCKED_HOSTS = {
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "::1",
    "metadata.google.internal",
}


class FetchError(Exception):
    pass


def assert_public_url(url: str, allowed_hosts: list[str]) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise FetchError("Only http(s) URLs can be fetched.")
    host = (parsed.hostname or "").lower()
    if not host or host in BLOCKED_HOSTS:
        raise FetchError("Blocked host.")

    allowed = {item.lower() for item in allowed_hosts}
    allowed_bare = {item.removeprefix("www.") for item in allowed}
    if host not in allowed and host.removeprefix("www.") not in allowed_bare:
        raise FetchError(f"Host {host} is not allowlisted for this source.")

    try:
        records = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise FetchError("Could not resolve host.") from exc

    for record in records:
        ip = ipaddress.ip_address(record[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise FetchError("Refusing to fetch a private or reserved address.")


async def fetch_bytes(
    client: httpx.AsyncClient,
    url: str,
    allowed_hosts: list[str],
    *,
    check_dns: bool = True,
) -> bytes:
    if check_dns:
        assert_public_url(url, allowed_hosts)
    response = await client.get(url, timeout=FETCH_TIMEOUT, follow_redirects=True)
    response.raise_for_status()
    if len(response.content) > MAX_BYTES:
        raise FetchError("Response exceeded size limit.")
    return response.content
