"""SSRF-safe fetching of public web pages.

* Only http/https, default ports 80/443, no credentials in URLs.
* Hostnames are resolved and EVERY resolved address must be public (no loopback, private,
  link-local, multicast, reserved, CGNAT or unspecified ranges); the connection is then
  pinned to a vetted IP so DNS cannot change between check and connect.
* Optional domain allow-list. Redirects are followed manually (max 3) and re-validated.
* Timeouts, 5 MB body cap, HTML/text content types only.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import httpx

MAX_BYTES = 5 * 1024 * 1024
MAX_REDIRECTS = 3
ALLOWED_TYPES = ("text/html", "text/plain", "application/xhtml+xml")


class FetchBlocked(ValueError):
    pass


@dataclass
class Fetched:
    url: str
    final_url: str
    content_type: str
    body: bytes


def _public(ip: str) -> bool:
    a: ipaddress.IPv4Address | ipaddress.IPv6Address = ipaddress.ip_address(ip)
    if isinstance(a, ipaddress.IPv6Address) and a.ipv4_mapped:
        a = a.ipv4_mapped
    return not (
        a.is_private
        or a.is_loopback
        or a.is_link_local
        or a.is_multicast
        or a.is_reserved
        or a.is_unspecified
        or (a.version == 4 and a in ipaddress.ip_network("100.64.0.0/10"))
    )


def validate_url(url: str, allowed_domains: list[str] | None = None) -> tuple[str, str]:
    """Return (host, vetted_ip) or raise FetchBlocked."""
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"}:
        raise FetchBlocked("Only http(s) URLs are allowed")
    if parts.username or parts.password:
        raise FetchBlocked("Credentials in URLs are not allowed")
    host = (parts.hostname or "").rstrip(".").lower()
    if not host:
        raise FetchBlocked("URL has no host")
    if parts.port not in {None, 80, 443}:
        raise FetchBlocked("Only ports 80 and 443 are allowed")
    if allowed_domains and not any(host == d or host.endswith("." + d) for d in allowed_domains):
        raise FetchBlocked("Domain is not on the allow-list")
    try:
        infos = socket.getaddrinfo(
            host, parts.port or (443 if parts.scheme == "https" else 80), type=socket.SOCK_STREAM
        )
    except socket.gaierror as exc:
        raise FetchBlocked("Host could not be resolved") from exc
    ips = sorted({str(i[4][0]) for i in infos})
    if not ips or not all(_public(ip) for ip in ips):
        raise FetchBlocked("Host resolves to a non-public address")
    return host, ips[0]


def fetch(
    url: str,
    *,
    allowed_domains: list[str] | None = None,
    timeout: float = 10.0,
    transport: httpx.BaseTransport | None = None,
) -> Fetched:
    current = url
    for _ in range(MAX_REDIRECTS + 1):
        host, ip = validate_url(current, allowed_domains)
        parts = urlsplit(current)
        # Connect to the vetted IP; keep Host header / SNI for the real name.
        pinned = parts._replace(netloc=f"[{ip}]" if ":" in ip else ip).geturl()
        with httpx.Client(
            timeout=timeout,
            follow_redirects=False,
            transport=transport,
            headers={"User-Agent": "SourceAtlas/0.1 (research fetcher)"},
        ) as c:
            req = c.build_request("GET", pinned, headers={"Host": host}, extensions={"sni_hostname": host})
            resp = c.send(req, stream=True)
            try:
                if resp.is_redirect:
                    loc = resp.headers.get("location")
                    if not loc:
                        raise FetchBlocked("Redirect without location")
                    current = urljoin(current, loc)
                    continue
                if resp.status_code != 200:
                    raise FetchBlocked(f"Upstream returned HTTP {resp.status_code}")
                ctype = resp.headers.get("content-type", "").split(";")[0].strip().lower()
                if ctype not in ALLOWED_TYPES:
                    raise FetchBlocked(f"Content type {ctype or 'unknown'} is not allowed")
                body = b""
                for chunk in resp.iter_bytes():
                    body += chunk
                    if len(body) > MAX_BYTES:
                        raise FetchBlocked("Page exceeds the size limit")
                return Fetched(url, current, ctype, body)
            finally:
                resp.close()
    raise FetchBlocked("Too many redirects")


def searxng(base_url: str, query: str, *, limit: int = 5, timeout: float = 10.0) -> list[dict[str, str]]:
    """Query a self-hosted SearXNG instance (JSON API). Results are candidates only; each
    URL is still validated by :func:`fetch` before ingestion."""
    r = httpx.get(base_url.rstrip("/") + "/search", params={"q": query, "format": "json"}, timeout=timeout)
    r.raise_for_status()
    return [
        {
            "title": str(x.get("title", ""))[:300],
            "url": str(x.get("url", "")),
            "snippet": str(x.get("content", ""))[:500],
        }
        for x in r.json().get("results", [])[:limit]
        if x.get("url")
    ]
