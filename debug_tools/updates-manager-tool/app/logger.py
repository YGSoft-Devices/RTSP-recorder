from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from typing import Dict, Iterable


REDACT_HEADERS = {"authorization", "x-api-key"}


def redact_headers(headers: Dict[str, str]) -> Dict[str, str]:
    redacted = {}
    for k, v in headers.items():
        if k.lower() in REDACT_HEADERS:
            redacted[k] = "***REDACTED***"
        else:
            redacted[k] = v
    return redacted


def setup_logger(name: str, log_path: str, level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(level)
    handler = RotatingFileHandler(log_path, maxBytes=2_000_000, backupCount=5, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


def sanitize_message(msg: str, secrets: Iterable[str] | None = None) -> str:
    if not secrets:
        return msg
    for secret in secrets:
        if secret:
            msg = msg.replace(secret, "***REDACTED***")
    return msg
