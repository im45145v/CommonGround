"""Signed reward receipts using ECDSA P-256 / SHA-256.

Format: ``<base64url(json payload)>.<base64url(DER ECDSA signature)>``.
The private key never leaves the station. Phones get only the public key
(base64 X.509 SubjectPublicKeyInfo, directly usable by Android's ``X509EncodedKeySpec``)
so they can verify receipts offline but cannot mint them.
"""
import base64
import json
import os
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def load_or_create_key(path: str | None) -> ec.EllipticCurvePrivateKey:
    """Load the station private key (PEM) from ``path``, creating it (mode 0600) on first run.
    ``path=None`` gives an ephemeral key (tests / in-memory DB)."""
    if not path:
        return ec.generate_private_key(ec.SECP256R1())
    p = Path(path)
    if p.exists():
        key = serialization.load_pem_private_key(p.read_bytes(), password=None)
        if not isinstance(key, ec.EllipticCurvePrivateKey) or key.curve.name != "secp256r1":
            raise ValueError(f"{path} is not an ECDSA P-256 private key")
        return key
    p.parent.mkdir(parents=True, exist_ok=True)
    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(pem)
    return key


def public_key_b64(key) -> str:
    der = key.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    return base64.b64encode(der).decode()


def load_public_key(b64: str):
    return serialization.load_der_public_key(base64.b64decode(b64))


def sign(private_key, payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    sig = private_key.sign(raw, ec.ECDSA(hashes.SHA256()))
    return f"{_b64(raw)}.{_b64(sig)}"


def verify(public_key, token: str):
    """Return the payload dict if the signature is valid, else None. Accepts a public or private key."""
    try:
        if hasattr(public_key, "public_key"):
            public_key = public_key.public_key()
        raw_b64, sig_b64 = token.split(".")
        raw = _unb64(raw_b64)
        public_key.verify(_unb64(sig_b64), raw, ec.ECDSA(hashes.SHA256()))
        payload = json.loads(raw)
        return payload if isinstance(payload, dict) else None
    except (InvalidSignature, ValueError, TypeError, KeyError):
        return None


def station_id(key) -> str:
    """Stable audience id of a station: first 16 hex chars of SHA-256 over its public key (SPKI DER).
    Phones derive the same value from the public key they stored at pairing."""
    import hashlib
    pub = key.public_key() if hasattr(key, "public_key") else key
    der = pub.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    return hashlib.sha256(der).hexdigest()[:16]
