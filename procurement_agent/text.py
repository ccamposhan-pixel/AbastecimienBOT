from __future__ import annotations

import re
import unicodedata

from .config import STOPWORDS


def strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def normalize_key(value: object) -> str:
    text = strip_accents(str(value or "")).lower().strip()
    text = re.sub(r"[_\-./]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def normalize_text(value: object) -> str:
    text = normalize_key(value)
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    tokens = [token for token in text.split() if token and token not in STOPWORDS]
    return " ".join(tokens)


def compact_key(value: object) -> str:
    return re.sub(r"\s+", "", normalize_key(value))
