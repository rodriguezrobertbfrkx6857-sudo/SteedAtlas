import hashlib
import hmac
import ipaddress
import socket
import time
from urllib.parse import urlsplit

from fastapi import HTTPException

from app.config import get_settings


def public_url(url, allowed_hosts=()):
    """No redirects permitted by callers. Resolve every destination before use."""
    u = urlsplit(url)
    if u.scheme != "https" or not u.hostname or u.username or u.password or u.port not in (None, 443):
        raise HTTPException(422, "UNSAFE_URL")
    if u.hostname not in allowed_hosts:
        raise HTTPException(422, "HOST_NOT_ALLOWLISTED")
    for info in socket.getaddrinfo(u.hostname, 443):
        if not ipaddress.ip_address(info[4][0]).is_global:
            raise HTTPException(422, "PRIVATE_ADDRESS_DENIED")
    return url


def _ticket_key() -> bytes:
    secret = str(get_settings().SECRET_KEY or "")
    return hashlib.sha256(("steedatlas-media-ticket:" + secret).encode("utf-8")).digest()


def issue_media_ticket(identity: str, owner: str, ttl_seconds: int = 3600) -> str:
    """Signed, expiring grant for private media playback without a bearer header.

    The ticket binds the artifact identity and its owner, so it cannot be replayed
    against another artifact or another account.
    """
    expires = int(time.time()) + max(60, int(ttl_seconds))
    payload = f"{identity}:{owner}:{expires}".encode("utf-8")
    signature = hmac.new(_ticket_key(), payload, hashlib.sha256).hexdigest()
    return f"{expires}.{signature}"


def verify_media_ticket(identity: str, owner: str, ticket: str, tolerance_seconds: int = 0) -> bool:
    raw = str(ticket or "").strip()
    if "." not in raw:
        return False
    expires_raw, _, signature = raw.partition(".")
    try:
        expires = int(expires_raw)
    except ValueError:
        return False
    if expires + max(0, int(tolerance_seconds)) < time.time():
        return False
    payload = f"{identity}:{owner}:{expires}".encode("utf-8")
    expected = hmac.new(_ticket_key(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
