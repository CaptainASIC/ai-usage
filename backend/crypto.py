"""
Credential encryption module for Reckoner.

Uses Fernet symmetric encryption (AES-128-CBC + HMAC-SHA256) to protect
credentials at rest in the SQLite database.

Key derivation:
- When RECKONER_PASSWORD is set, the encryption key is derived from it
  using PBKDF2-HMAC-SHA256 with a fixed salt (stable across restarts).
- When no password is set, a random key is generated at startup.
  Credentials encrypted with a random key are only readable until the
  process restarts — acceptable for local/dev use.
"""

import base64
import json
import logging
import os
import secrets

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

logger = logging.getLogger(__name__)

# Stable salt so the derived key is consistent across restarts.
# This doesn't need to be secret — it prevents rainbow-table attacks on the KDF.
_SALT = b"reckoner-credential-store-v1"

_PASSWORD = os.getenv("RECKONER_PASSWORD", "").strip()


def _derive_key(password: str) -> bytes:
    """Derive a Fernet key from a password using PBKDF2.

    Args:
        password: The password to derive from.

    Returns:
        bytes: A 32-byte URL-safe base64-encoded Fernet key.
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_SALT,
        iterations=480_000,
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))


def _get_fernet() -> Fernet:
    """Get the Fernet instance for encryption/decryption.

    Returns:
        Fernet: Configured encryption instance.
    """
    if _PASSWORD:
        key = _derive_key(_PASSWORD)
    else:
        # No password — use a per-process random key.
        # Credentials saved without a password won't survive restarts.
        if not hasattr(_get_fernet, "_ephemeral_key"):
            _get_fernet._ephemeral_key = Fernet.generate_key()  # type: ignore[attr-defined]
            logger.warning(
                "No RECKONER_PASSWORD set — using ephemeral encryption key. "
                "Credentials will not survive process restarts."
            )
        key = _get_fernet._ephemeral_key  # type: ignore[attr-defined]
    return Fernet(key)


def encrypt(plaintext: str) -> str:
    """Encrypt a plaintext string and return a base64-encoded ciphertext.

    Args:
        plaintext: The string to encrypt.

    Returns:
        str: Base64-encoded encrypted string, prefixed with 'enc:'.
    """
    f = _get_fernet()
    token = f.encrypt(plaintext.encode())
    return "enc:" + token.decode()


def decrypt(ciphertext: str) -> str:
    """Decrypt a ciphertext string. Handles both encrypted and legacy plaintext.

    If the value doesn't start with 'enc:', it's treated as legacy plaintext
    (pre-encryption migration) and returned as-is.

    Args:
        ciphertext: The encrypted string (prefixed with 'enc:') or legacy plaintext.

    Returns:
        str: The decrypted plaintext.
    """
    if not ciphertext.startswith("enc:"):
        # Legacy plaintext — return as-is for migration compatibility.
        return ciphertext

    f = _get_fernet()
    try:
        token = ciphertext[4:].encode()
        return f.decrypt(token).decode()
    except InvalidToken:
        logger.error(
            "Failed to decrypt credentials — encryption key may have changed. "
            "Re-enter credentials via settings or restart with the correct RECKONER_PASSWORD."
        )
        return "{}"
