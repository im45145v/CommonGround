"""Signed reward receipts.

Format: ``<base64url(json payload)>.<base64url(HMAC-SHA256(payload))>``.
The phone receives the HMAC key at pairing time, so it can verify receipts offline.
(Symmetric signing: anyone holding the key can mint receipts. See README limitations.)
"""
import base64
import hashlib
import hmac
import json


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def sign(secret: str, payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    mac = hmac.new(secret.encode(), raw, hashlib.sha256).digest()
    return f"{_b64(raw)}.{_b64(mac)}"


def verify(secret: str, token: str):
    """Return the payload dict if the signature is valid, else None."""
    try:
        raw_b64, mac_b64 = token.split(".")
        raw = _unb64(raw_b64)
        expected = hmac.new(secret.encode(), raw, hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _unb64(mac_b64)):
            return None
        payload = json.loads(raw)
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None
