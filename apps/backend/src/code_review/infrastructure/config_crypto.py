"""配置敏感字段加解密工具（AES-256-GCM）。"""

import base64
import hashlib
import os
import logging

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger(__name__)

# PBKDF2 参数
_PBKDF2_SALT = b"code-review-config-salt-v1"
_PBKDF2_ITERATIONS = 100_000

# AES-GCM nonce 长度
_NONCE_LEN = 12


def _derive_key(secret_key: str) -> bytes:
    """从 SECRET_KEY 派生 AES-256 密钥。"""
    return hashlib.pbkdf2_hmac(
        "sha256",
        secret_key.encode("utf-8"),
        _PBKDF2_SALT,
        _PBKDF2_ITERATIONS,
    )


def encrypt(plaintext: str, secret_key: str) -> str:
    """AES-256-GCM 加密，返回 base64(nonce || ciphertext_with_tag)。

    空字符串不加密，原样返回。
    """
    if not plaintext:
        return ""
    key = _derive_key(secret_key)
    nonce = os.urandom(_NONCE_LEN)
    aesgcm = AESGCM(key)
    ct = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.b64encode(nonce + ct).decode("utf-8")


def decrypt(ciphertext: str, secret_key: str) -> str:
    """AES-256-GCM 解密。

    空字符串不解密，原样返回。
    解密失败时记录日志并返回原文（可能是未加密的历史数据）。
    """
    if not ciphertext:
        return ""
    try:
        key = _derive_key(secret_key)
        raw = base64.b64decode(ciphertext)
        nonce = raw[:_NONCE_LEN]
        ct = raw[_NONCE_LEN:]
        aesgcm = AESGCM(key)
        return aesgcm.decrypt(nonce, ct, None).decode("utf-8")
    except Exception as e:
        logger.warning("Failed to decrypt config value, returning raw: %s", e)
        return ciphertext


MASK = "********"


def mask_value(value: str) -> str:
    """敏感字段脱敏。"""
    if not value:
        return ""
    return MASK
